"""SOKOL API — Face recognition endpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory
from .services.face import detect_faces_bytes

router = APIRouter(prefix="/faces", tags=["faces"])

MEDIA_CACHE = Path("/data/media-cache")


# ── Models ─────────────────────────────────────────────────────────────────
class FaceEmbedding(BaseModel):
    id: str
    case_id: str
    media_hash: str
    bbox: list[float]
    confidence: Optional[float] = None
    label: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    created_at: str


class FaceSearchResult(BaseModel):
    face_id: str
    case_id: str
    case_name: str
    media_hash: str
    bbox: list[float]
    similarity: float
    label: Optional[str] = None


class FaceSubject(BaseModel):
    subject_id: str
    label: Optional[str] = None
    face_count: int
    representative_face: FaceEmbedding
    faces: list[FaceEmbedding]


# ── Helpers ─────────────────────────────────────────────────────────────────
def _find_media_file(media_hash: str) -> Optional[Path]:
    """Find a media file on disk by hash, searching media-cache."""
    if not MEDIA_CACHE.exists():
        return None
    direct = MEDIA_CACHE / media_hash
    if direct.is_file():
        return direct
    for ext in [".jpg", ".jpeg", ".png", ".webp"]:
        candidate = MEDIA_CACHE / f"{media_hash}{ext}"
        if candidate.exists():
            return candidate
    return None


def _get_case_image_hashes(db, case_id: str) -> list[str]:
    """Get all image hashes linked to a case via messages and artifacts."""
    rows = (
        db.execute(
            text("""
            SELECT DISTINCT m.hash
            FROM media m
            LEFT JOIN (
                SELECT media_hash FROM messages WHERE case_id = :case_id AND media_hash IS NOT NULL
            ) msg ON msg.media_hash = m.hash
            LEFT JOIN (
                SELECT media_hash FROM artifacts WHERE case_id = :case_id AND media_hash IS NOT NULL
            ) art ON art.media_hash = m.hash
            WHERE (msg.media_hash IS NOT NULL OR art.media_hash IS NOT NULL)
              AND m.mime_type LIKE 'image/%'
        """),
            {"case_id": case_id},
        )
        .mappings()
        .all()
    )
    return [r["hash"] for r in rows]


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/detect/{case_id}")
async def detect_faces_in_case(
    case_id: str,
    media_hash: str,
):
    """Detect faces in a media file and store embeddings."""
    factory = get_session_factory()
    with factory() as db:
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        media_path = _find_media_file(media_hash)
        if not media_path:
            raise HTTPException(status_code=404, detail="Media file not found on disk")

        result = await detect_faces_bytes(
            media_path.read_bytes(),
            image_id=media_hash,
        )

        stored = 0
        for face in result.get("faces", []):
            existing = db.execute(
                text("""
                    SELECT id FROM face_embeddings
                    WHERE case_id = :cid AND media_hash = :hash
                    AND bbox = CAST(:bbox AS jsonb)
                """),
                {"cid": case_id, "hash": media_hash, "bbox": json.dumps(face["bbox"])},
            ).fetchone()

            if not existing:
                db.execute(
                    text("""
                        INSERT INTO face_embeddings (case_id, media_hash, bbox, embedding, confidence, age, gender)
                                VALUES (:cid, :hash, CAST(:bbox AS jsonb), CAST(:embedding AS vector), :conf, :age, :gender)
                    """),
                    {
                        "cid": case_id,
                        "hash": media_hash,
                        "bbox": json.dumps(face["bbox"]),
                        "embedding": str(face["embedding"]),
                        "conf": face.get("confidence"),
                        "age": face.get("age"),
                        "gender": face.get("gender"),
                    },
                )
                stored += 1

        db.commit()

        return {
            "faces_detected": result.get("face_count", 0),
            "faces_stored": stored,
            "media_hash": media_hash,
        }


@router.post("/detect_all/{case_id}")
async def detect_faces_all(case_id: str):
    """Detect faces in ALL images of a case (background-friendly batch)."""
    factory = get_session_factory()
    with factory() as db:
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        hashes = _get_case_image_hashes(db, case_id)

        total_detected = 0
        total_stored = 0
        errors = 0
        processed = 0

        for media_hash in hashes:
            processed += 1
            media_path = _find_media_file(media_hash)
            if not media_path:
                errors += 1
                continue

            try:
                result = await detect_faces_bytes(
                    media_path.read_bytes(),
                    image_id=media_hash,
                )
                faces = result.get("faces", [])
                total_detected += len(faces)

                for face in faces:
                    existing = db.execute(
                        text("""
                            SELECT id FROM face_embeddings
                            WHERE case_id = :cid AND media_hash = :hash
                            AND bbox = CAST(:bbox AS jsonb)
                        """),
                        {
                            "cid": case_id,
                            "hash": media_hash,
                            "bbox": json.dumps(face["bbox"]),
                        },
                    ).fetchone()

                    if not existing:
                        db.execute(
                            text("""
                                INSERT INTO face_embeddings (case_id, media_hash, bbox, embedding, confidence, age, gender)
                        VALUES (:cid, :hash, CAST(:bbox AS jsonb), CAST(:embedding AS vector), :conf, :age, :gender)
                            """),
                            {
                                "cid": case_id,
                                "hash": media_hash,
                                "bbox": json.dumps(face["bbox"]),
                                "embedding": str(face["embedding"]),
                                "conf": face.get("confidence"),
                                "age": face.get("age"),
                                "gender": face.get("gender"),
                            },
                        )
                        total_stored += 1
            except Exception:
                errors += 1
                continue

        db.commit()

        return {
            "images_processed": processed,
            "faces_detected": total_detected,
            "faces_stored": total_stored,
            "errors": errors,
        }


@router.get("/{case_id}", response_model=list[FaceEmbedding])
async def list_faces(
    case_id: str,
    label: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """List stored face embeddings for a case."""
    factory = get_session_factory()
    with factory() as db:
        query = "SELECT * FROM face_embeddings WHERE case_id = :cid"
        params = {"cid": case_id, "limit": limit}

        if label:
            query += " AND label = :label"
            params["label"] = label

        query += " ORDER BY created_at DESC LIMIT :limit"

        rows = db.execute(text(query), params).mappings().all()
        return [
            FaceEmbedding(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                media_hash=r["media_hash"],
                bbox=r["bbox"],
                confidence=r["confidence"],
                label=r["label"],
                age=r["age"],
                gender=r["gender"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]


@router.post("/{case_id}/search", response_model=list[FaceSearchResult])
async def search_faces(
    case_id: str,
    face_id: str,
    threshold: float = Query(0.4, ge=0.0, le=1.0),
    limit: int = Query(20, ge=1, le=100),
):
    """Search for similar faces across all cases."""
    factory = get_session_factory()
    with factory() as db:
        source = (
            db.execute(
                text(
                    "SELECT embedding, media_hash, bbox, label FROM face_embeddings WHERE id = :id"
                ),
                {"id": face_id},
            )
            .mappings()
            .fetchone()
        )
        if not source:
            raise HTTPException(status_code=404, detail="Face not found")

        source_embedding = str(source["embedding"])

        rows = (
            db.execute(
                text("""
                SELECT
                    fe.id as face_id,
                    fe.case_id,
                    c.name as case_name,
                    fe.media_hash,
                    fe.bbox,
                    fe.label,
                    1 - (fe.embedding <=> :embedding::vector) as similarity
                FROM face_embeddings fe
                JOIN cases c ON c.id = fe.case_id
                WHERE fe.case_id != :exclude_case_id
                  AND 1 - (fe.embedding <=> :embedding::vector) > :threshold
                ORDER BY fe.embedding <=> :embedding::vector
                LIMIT :limit
            """),
                {
                    "embedding": source_embedding,
                    "exclude_case_id": case_id,
                    "threshold": threshold,
                    "limit": limit,
                },
            )
            .mappings()
            .all()
        )

        return [
            FaceSearchResult(
                face_id=str(r["face_id"]),
                case_id=str(r["case_id"]),
                case_name=r["case_name"],
                media_hash=r["media_hash"],
                bbox=r["bbox"],
                similarity=round(float(r["similarity"]), 4),
                label=r["label"],
            )
            for r in rows
        ]


@router.put("/{face_id}/label")
async def label_face(face_id: str, label: str):
    """Label a face embedding."""
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("UPDATE face_embeddings SET label = :label WHERE id = :id"),
            {"id": face_id, "label": label},
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Face not found")
        return {"ok": True, "label": label}


@router.delete("/{face_id}")
async def delete_face(face_id: str):
    """Delete a face embedding."""
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("DELETE FROM face_embeddings WHERE id = :id"),
            {"id": face_id},
        )
        db.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Face not found")
        return {"ok": True}


@router.get("/{case_id}/subjects", response_model=list[FaceSubject])
async def list_subjects(
    case_id: str,
    threshold: float = Query(0.55, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
):
    """Group faces into unique subjects by label or embedding similarity."""
    factory = get_session_factory()
    with factory() as db:
        rows = (
            db.execute(
                text("""
                SELECT id, case_id, media_hash, bbox, confidence, label, age, gender, created_at, embedding
                FROM face_embeddings
                WHERE case_id = :cid
                ORDER BY created_at DESC
                LIMIT :limit
            """),
                {"cid": case_id, "limit": limit},
            )
            .mappings()
            .all()
        )

        if not rows:
            return []

        faces = []
        for r in rows:
            faces.append(
                {
                    "id": str(r["id"]),
                    "case_id": str(r["case_id"]),
                    "media_hash": r["media_hash"],
                    "bbox": r["bbox"],
                    "confidence": r["confidence"],
                    "label": r["label"],
                    "age": r["age"],
                    "gender": r["gender"],
                    "created_at": str(r["created_at"]),
                    "_embedding": str(r["embedding"]),
                }
            )

        # Group labeled faces first
        subjects: dict[str, dict] = {}
        unlabeled: list[dict] = []

        for f in faces:
            lbl = (f.get("label") or "").strip()
            if lbl:
                key = f"label:{lbl}"
                if key not in subjects:
                    subjects[key] = {
                        "subject_id": key,
                        "label": lbl,
                        "faces": [],
                    }
                subjects[key]["faces"].append(f)
            else:
                unlabeled.append(f)

        # Cluster unlabeled by embedding similarity
        for f in unlabeled:
            emb_str = f["_embedding"]
            matched = False
            for key, subj in subjects.items():
                if key.startswith("label:"):
                    continue
                # Compare with representative face
                rep = subj["faces"][0]
                try:
                    sim = db.execute(
                        text("""
                            SELECT 1 - (CAST(:a AS vector) <=> CAST(:b AS vector)) as sim
                        """),
                        {"a": emb_str, "b": rep["_embedding"]},
                    ).scalar()
                    if sim and sim > threshold:
                        subj["faces"].append(f)
                        matched = True
                        break
                except Exception:
                    continue
            if not matched:
                new_key = f"auto:{f['id']}"
                subjects[new_key] = {
                    "subject_id": new_key,
                    "label": None,
                    "faces": [f],
                }

        result = []
        for key, subj in subjects.items():
            all_faces_data = []
            for ff in subj["faces"]:
                all_faces_data.append(
                    FaceEmbedding(
                        id=ff["id"],
                        case_id=ff["case_id"],
                        media_hash=ff["media_hash"],
                        bbox=ff["bbox"],
                        confidence=ff["confidence"],
                        label=ff["label"],
                        age=ff["age"],
                        gender=ff["gender"],
                        created_at=ff["created_at"],
                    )
                )
            result.append(
                FaceSubject(
                    subject_id=subj["subject_id"],
                    label=subj["label"],
                    face_count=len(all_faces_data),
                    representative_face=all_faces_data[0],
                    faces=all_faces_data,
                )
            )

        result.sort(key=lambda s: s.face_count, reverse=True)
        return result[:limit]
