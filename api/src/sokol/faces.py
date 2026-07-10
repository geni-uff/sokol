"""SOKOL API — Face recognition endpoints."""

from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory
from .services.face import detect_faces_bytes

router = APIRouter(prefix="/faces", tags=["faces"])


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

        media = db.execute(
            text("SELECT hash FROM media WHERE case_id = :cid AND hash = :hash"),
            {"cid": case_id, "hash": media_hash},
        ).fetchone()
        if not media:
            raise HTTPException(status_code=404, detail="Media not found")

        import os
        from pathlib import Path

        media_dir = Path("/data/media-cache") / case_id
        media_path = None
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = media_dir / f"{media_hash}{ext}"
            if candidate.exists():
                media_path = candidate
                break

        if not media_path:
            for p in media_dir.rglob(f"{media_hash}.*"):
                if p.is_file():
                    media_path = p
                    break

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
                    AND bbox = :bbox::jsonb
                """),
                {"cid": case_id, "hash": media_hash, "bbox": json.dumps(face["bbox"])},
            ).fetchone()

            if not existing:
                db.execute(
                    text("""
                        INSERT INTO face_embeddings (case_id, media_hash, bbox, embedding, confidence, age, gender)
                        VALUES (:cid, :hash, :bbox::jsonb, :embedding::vector, :conf, :age, :gender)
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
            "faces": [
                {
                    "bbox": f["bbox"],
                    "confidence": f.get("confidence"),
                    "age": f.get("age"),
                    "gender": f.get("gender"),
                }
                for f in result.get("faces", [])
            ],
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

        rows = db.execute(text(query), params).fetchall()
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
        source = db.execute(
            text(
                "SELECT embedding, media_hash, bbox, label FROM face_embeddings WHERE id = :id"
            ),
            {"id": face_id},
        ).fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="Face not found")

        source_embedding = str(source["embedding"])

        rows = db.execute(
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
        ).fetchall()

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
