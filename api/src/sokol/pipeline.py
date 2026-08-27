"""SOKOL API — Parallel auto-detection pipeline.

Spawns independent background jobs for each detection type (YOLO, faces, plates, ASR).
Each job updates the jobs table with progress, and the UI polls for status.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member, require_platform_admin
from .audit import append_audit
from .chunk_jobs import chunk_messages
from .db import get_session_factory
from .jobs import emit_progress
from .media import sniff_image_mime
from .plate_parse import PLATE_DETECT_PATH, parse_plate_service_payload
from .ufdr_extract import ensure_media_on_disk

router = APIRouter(prefix="/detect", tags=["detect"])

MEDIA_CACHE = Path("/data/media-cache")
# Host network (Linux/WSL): localhost. Bridge (Docker Desktop Windows): service DNS.
VISION_URL = os.getenv("SOKOL_VISION_URL", os.getenv("SOKOL_VISION_API_URL", "http://localhost:8007"))
FACE_URL = os.getenv("SOKOL_FACE_URL", "http://localhost:8011")
PLATE_URL = os.getenv("SOKOL_PLATE_URL", os.getenv("SOKOL_PLATE_API_URL", "http://localhost:8010"))
ASR_URL = os.getenv("SOKOL_ASR_URL", os.getenv("SOKOL_ASR_API_URL", "http://localhost:8009"))
OCR_URL = os.getenv("SOKOL_OCR_URL", os.getenv("SOKOL_OCR_API_URL", "http://localhost:8008"))


# ── Models ─────────────────────────────────────────────────────────────────
class PipelineResult(BaseModel):
    jobs_launched: int
    job_ids: dict[str, str]
    skipped: dict[str, str] = {}
    warnings: list[str] = []
    mode: str = "sample"
    image_count: int = 0
    audio_count: int = 0
    missing_files: int = 0


class JobStatus(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: float
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────
PREFERRED_IMAGE = ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic")


def _find_media_file(media_hash: str, case_id: str | None = None) -> Optional[Path]:
    if MEDIA_CACHE.exists():
        direct = MEDIA_CACHE / media_hash
        if direct.is_file() and direct.stat().st_size > 0:
            return direct
        for ext in [".jpg", ".jpeg", ".png", ".webp"]:
            candidate = MEDIA_CACHE / f"{media_hash}{ext}"
            if candidate.exists():
                return candidate
    if not case_id:
        return None
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT storage_ref FROM media WHERE hash = :h"),
            {"h": media_hash},
        ).mappings().first()
        ref = row["storage_ref"] if row else {}
        if isinstance(ref, str):
            try:
                ref = json.loads(ref)
            except json.JSONDecodeError:
                ref = {}
        return ensure_media_on_disk(db, case_id, media_hash, ref)


def _list_case_media(db, case_id: str, mime_prefix: str) -> list[dict]:
    rows = (
        db.execute(
            text("""
            SELECT DISTINCT m.hash, m.mime_type, m.storage_ref
            FROM media m
            LEFT JOIN (SELECT media_hash FROM messages WHERE case_id = :cid AND media_hash IS NOT NULL) msg
              ON msg.media_hash = m.hash
            LEFT JOIN (SELECT media_hash FROM artifacts WHERE case_id = :cid AND media_hash IS NOT NULL) art
              ON art.media_hash = m.hash
            WHERE (msg.media_hash IS NOT NULL OR art.media_hash IS NOT NULL)
              AND (
                m.mime_type LIKE :prefix
                OR m.mime_type = 'application/octet-stream'
              )
        """),
            {"cid": case_id, "prefix": f"{mime_prefix}%"},
        )
        .mappings()
        .all()
    )
    out = []
    for r in rows:
        ref = r["storage_ref"] or {}
        if isinstance(ref, str):
            try:
                ref = json.loads(ref)
            except json.JSONDecodeError:
                ref = {}
        out.append({"hash": r["hash"], "mime_type": r["mime_type"] or "", "storage_ref": ref})
    return out


def _get_case_images(db, case_id: str) -> list[str]:
    return [r["hash"] for r in _list_case_media(db, case_id, "image/")]


def _get_case_audios(db, case_id: str) -> list[str]:
    return [r["hash"] for r in _list_case_media(db, case_id, "audio/")]


def _select_and_extract(
    db,
    case_id: str,
    items: list[dict],
    *,
    mode: str,
    limit: int,
    preferred_mimes: tuple[str, ...],
) -> tuple[list[str], int]:
    """Prefer real image/audio MIME, extract from UFDR, drop hashes with no file."""
    preferred = [i for i in items if (i["mime_type"] or "").lower() in preferred_mimes]
    rest = [i for i in items if i not in preferred]
    ordered = preferred + rest
    selected: list[str] = []
    missing = 0
    cap = None if mode == "all" else limit
    max_attempts = None if mode == "all" else max(limit * 10, 200)
    attempts = 0
    for item in ordered:
        if cap is not None and len(selected) >= cap:
            break
        if max_attempts is not None and attempts >= max_attempts:
            break
        attempts += 1
        path = ensure_media_on_disk(db, case_id, item["hash"], item["storage_ref"])
        if path is None:
            missing += 1
            continue
        sniffed = sniff_image_mime(path)
        if sniffed and (item["mime_type"] or "").startswith("application/"):
            db.execute(
                text("UPDATE media SET mime_type = :m WHERE hash = :h"),
                {"m": sniffed, "h": item["hash"]},
            )
        selected.append(item["hash"])
    db.commit()
    return selected, missing


def _open_face_pendencias(case_id: str, stored: int) -> None:
    """Create Pendências (Indicator) for unlabeled faces so the review queue is usable."""
    factory = get_session_factory()
    with factory() as db:
        user_id = db.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        if not user_id:
            return
        unlabeled = db.execute(
            text("""
                SELECT COUNT(*) FROM face_embeddings
                WHERE case_id = :cid AND (label IS NULL OR label = '')
            """),
            {"cid": case_id},
        ).scalar() or 0
        if unlabeled == 0:
            return
        existing = db.execute(
            text("""
                SELECT 1 FROM pendencias
                WHERE case_id = :cid AND title LIKE 'Rostos sem identificação%'
                  AND status = 'open'
                LIMIT 1
            """),
            {"cid": case_id},
        ).fetchone()
        if existing:
            return
        db.execute(
            text("""
                INSERT INTO pendencias (id, case_id, title, description, priority, created_by)
                VALUES (gen_random_uuid(), :cid, :title, :descr, 'medium', :uid)
            """),
            {
                "cid": case_id,
                "title": f"Rostos sem identificação ({unlabeled} Indicator)",
                "descr": (
                    f"{stored} embedding(s) novos. Confirme na aba Rostos antes de tratar "
                    "como Fact (ADR-0004)."
                ),
                "uid": user_id,
            },
        )
        db.commit()


# ── Job runners (run in background threads) ────────────────────────────────
def _run_yolo_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run YOLO vision detection on images."""
    try:
        emit_progress(
            job_id,
            "yolo",
            "running",
            0.0,
            f"Detecting objects in {len(image_hashes)} images...",
            case_id=case_id,
        )

        total = len(image_hashes)
        batch_size = 16
        total_dets = 0

        for i in range(0, total, batch_size):
            batch = image_hashes[i : i + batch_size]
            paths = []
            hashes = []
            for h in batch:
                p = _find_media_file(h, case_id)
                if p:
                    paths.append(str(p))
                    hashes.append(h)

            if not paths:
                continue

            try:
                with httpx.Client(timeout=300) as client:
                    resp = client.post(
                        f"{VISION_URL}/detect/batch",
                        json={
                            "image_ids": hashes,
                            "image_paths": paths,
                            "models": ["coco", "firearm", "threat"],
                        },
                    )
                    resp.raise_for_status()
                    results = resp.json().get("results", [])

                factory = get_session_factory()
                with factory() as db:
                    for result in results:
                        for det in result.get("detections", []):
                            if det["confidence"] < 0.25:
                                continue
                            db.execute(
                                text("""
                                    INSERT INTO image_detections (case_id, media_hash, model_name, class_name, class_id, confidence, bbox, pipeline_version)
                                    VALUES (:case_id, :hash, :model, :class, :cls_id, :conf, :bbox, :ver)
                                    ON CONFLICT DO NOTHING
                                """),
                                {
                                    "case_id": case_id,
                                    "hash": result.get("image_id"),
                                    "model": det["model"],
                                    "class": det["class_name"],
                                    "cls_id": det["class_id"],
                                    "conf": det["confidence"],
                                    "bbox": json.dumps(det["bbox"]),
                                    "ver": "yolov8n-v1",
                                },
                            )
                            total_dets += 1
                    db.commit()

                progress = min((i + batch_size) / total, 1.0)
                emit_progress(
                    job_id,
                    "yolo",
                    "running",
                    progress,
                    f"Batch {i // batch_size + 1}: {total_dets} detections",
                )

            except Exception as e:
                emit_progress(
                    job_id,
                    "yolo",
                    "running",
                    min((i + batch_size) / total, 1.0),
                    f"Batch error: {e}",
                )

        emit_progress(
            job_id,
            "yolo",
            "completed",
            1.0,
            f"Done: {total_dets} object detections",
            case_id=case_id,
        )

    except Exception as e:
        emit_progress(job_id, "yolo", "failed", 0.0, str(e), case_id=case_id)


def _run_face_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run face detection and store embeddings."""
    try:
        emit_progress(
            job_id,
            "faces",
            "running",
            0.0,
            f"Detecting faces in {len(image_hashes)} images...",
            case_id=case_id,
        )

        total = len(image_hashes)
        total_stored = 0

        for i, h in enumerate(image_hashes):
            p = _find_media_file(h, case_id)
            if not p:
                continue

            try:
                with httpx.Client(timeout=60) as client:
                    with open(p, "rb") as f:
                        files = {"file": (p.name, f, "image/jpeg")}
                        data = {"image_id": h}
                        resp = client.post(f"{FACE_URL}/detect", files=files, data=data)
                        resp.raise_for_status()
                        result = resp.json()

                faces = result.get("faces", [])
                if faces:
                    factory = get_session_factory()
                    with factory() as db:
                        for face in faces:
                            existing = db.execute(
                                text(
                                    "SELECT id FROM face_embeddings WHERE case_id = :cid AND media_hash = :hash AND bbox = CAST(:bbox AS jsonb)"
                                ),
                                {
                                    "cid": case_id,
                                    "hash": h,
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
                                        "hash": h,
                                        "bbox": json.dumps(face["bbox"]),
                                        "embedding": str(face["embedding"]),
                                        "conf": face.get("confidence"),
                                        "age": face.get("age"),
                                        "gender": face.get("gender"),
                                    },
                                )
                                total_stored += 1
                        db.commit()

                progress = (i + 1) / total
                if (i + 1) % 10 == 0 or i + 1 == total:
                    emit_progress(
                        job_id,
                        "faces",
                        "running",
                        progress,
                        f"Image {i + 1}/{total}: {total_stored} faces stored",
                    )

            except Exception:
                continue

        emit_progress(
            job_id,
            "faces",
            "completed",
            1.0,
            f"Done: {total_stored} face embeddings stored",
            case_id=case_id,
        )
        if total_stored:
            _open_face_pendencias(case_id, total_stored)

    except Exception as e:
        emit_progress(job_id, "faces", "failed", 0.0, str(e), case_id=case_id)


def _run_plate_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run plate detection on images."""
    try:
        emit_progress(
            job_id,
            "plates",
            "running",
            0.0,
            f"Detecting plates in {len(image_hashes)} images...",
            case_id=case_id,
        )

        total = len(image_hashes)
        total_plates = 0

        for i, h in enumerate(image_hashes):
            p = _find_media_file(h, case_id)
            if not p:
                continue

            try:
                with httpx.Client(timeout=60) as client:
                    with open(p, "rb") as f:
                        files = {"file": (p.name, f, "image/jpeg")}
                        resp = client.post(
                            f"{PLATE_URL}{PLATE_DETECT_PATH}", files=files
                        )
                        resp.raise_for_status()
                        result = resp.json()

                plates = parse_plate_service_payload(result)
                if plates:
                    factory = get_session_factory()
                    with factory() as db:
                        for plate in plates:
                            db.execute(
                                text("""
                                    INSERT INTO plate_detections (case_id, media_hash, plate_text, confidence, bbox, created_at)
                                    VALUES (:cid, :hash, :text, :conf, CAST(:bbox AS jsonb), now())
                                    ON CONFLICT DO NOTHING
                                """),
                                {
                                    "cid": case_id,
                                    "hash": h,
                                    "text": plate["plate_text"],
                                    "conf": plate["confidence"],
                                    "bbox": json.dumps(plate["bbox"]),
                                },
                            )
                            total_plates += 1
                        db.commit()

                progress = (i + 1) / total
                if (i + 1) % 10 == 0 or i + 1 == total:
                    emit_progress(
                        job_id,
                        "plates",
                        "running",
                        progress,
                        f"Image {i + 1}/{total}: {total_plates} plates",
                    )

            except Exception as e:
                print(f"[pipeline] plate detect failed hash={h[:12]}: {e}")
                continue

        emit_progress(
            job_id,
            "plates",
            "completed",
            1.0,
            f"Done: {total_plates} plates detected",
            case_id=case_id,
        )

    except Exception as e:
        emit_progress(job_id, "plates", "failed", 0.0, str(e), case_id=case_id)


def _run_asr_job(job_id: str, case_id: str, audio_hashes: list[str]):
    """Run ASR transcription on audio files."""
    try:
        emit_progress(
            job_id,
            "asr",
            "running",
            0.0,
            f"Transcribing {len(audio_hashes)} audio files...",
            case_id=case_id,
        )

        total = len(audio_hashes)
        total_transcribed = 0

        for i, h in enumerate(audio_hashes):
            p = _find_media_file(h, case_id)
            if not p:
                continue

            try:
                with httpx.Client(timeout=120) as client:
                    with open(p, "rb") as f:
                        files = {"file": (p.name, f, "audio/ogg")}
                        resp = client.post(f"{ASR_URL}/api/transcribe", files=files)
                        resp.raise_for_status()
                        result = resp.json()

                segments = result.get("segments", [])
                if segments:
                    full_text = " ".join(s.get("text", "") for s in segments)
                    factory = get_session_factory()
                    with factory() as db:
                        db.execute(
                            text("""
                                INSERT INTO transcriptions (case_id, media_hash, text, segments, language, created_at)
                                VALUES (:cid, :hash, :text, CAST(:segments AS jsonb), :lang, now())
                                ON CONFLICT (case_id, media_hash) DO UPDATE SET text = EXCLUDED.text, segments = EXCLUDED.segments
                            """),
                            {
                                "cid": case_id,
                                "hash": h,
                                "text": full_text,
                                "segments": json.dumps(segments),
                                "lang": result.get("language", "unknown"),
                            },
                        )
                        db.commit()
                        total_transcribed += 1

                progress = (i + 1) / total
                if (i + 1) % 5 == 0 or i + 1 == total:
                    emit_progress(
                        job_id,
                        "asr",
                        "running",
                        progress,
                        f"Audio {i + 1}/{total}: {total_transcribed} transcribed",
                    )

            except Exception:
                continue

        emit_progress(
            job_id,
            "asr",
            "completed",
            1.0,
            f"Done: {total_transcribed} audio transcriptions",
            case_id=case_id,
        )

    except Exception as e:
        emit_progress(job_id, "asr", "failed", 0.0, str(e), case_id=case_id)


def _run_ocr_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run OCR text extraction on document images."""
    try:
        emit_progress(
            job_id,
            "ocr",
            "running",
            0.0,
            f"Extracting text from {len(image_hashes)} images...",
            case_id=case_id,
        )

        total = len(image_hashes)
        total_extracted = 0

        for i, h in enumerate(image_hashes):
            p = _find_media_file(h, case_id)
            if not p:
                continue

            try:
                with httpx.Client(timeout=120) as client:
                    with open(p, "rb") as f:
                        ext = p.suffix.lower()
                        mime_map = {
                            ".jpg": "image/jpeg",
                            ".jpeg": "image/jpeg",
                            ".png": "image/png",
                            ".bmp": "image/bmp",
                        }
                        content_type = mime_map.get(ext, "image/jpeg")
                        files = {"file": (p.name, f, content_type)}
                        resp = client.post(f"{OCR_URL}/api/ocr", files=files)
                        resp.raise_for_status()
                        result = resp.json()

                text_content = result.get("text", "")
                if text_content.strip():
                    lines = result.get("lines", [])
                    factory = get_session_factory()
                    with factory() as db:
                        db.execute(
                            text("""
                                INSERT INTO ocr_results (case_id, media_hash, text, confidence, language, lines, created_at)
                                VALUES (:cid, :hash, :text, :conf, :lang, CAST(:lines AS jsonb), now())
                                ON CONFLICT (case_id, media_hash) DO UPDATE SET text = EXCLUDED.text, lines = EXCLUDED.lines
                            """),
                            {
                                "cid": case_id,
                                "hash": h,
                                "text": text_content,
                                "conf": result.get("confidence", 0),
                                "lang": result.get("language"),
                                "lines": json.dumps(lines),
                            },
                        )
                        db.commit()
                        total_extracted += 1

                progress = (i + 1) / total
                if (i + 1) % 5 == 0 or i + 1 == total:
                    emit_progress(
                        job_id,
                        "ocr",
                        "running",
                        progress,
                        f"Image {i + 1}/{total}: {total_extracted} with text",
                    )

            except Exception:
                continue

        emit_progress(
            job_id,
            "ocr",
            "completed",
            1.0,
            f"Done: {total_extracted} images with extracted text",
            case_id=case_id,
        )

    except Exception as e:
        emit_progress(job_id, "ocr", "failed", 0.0, str(e), case_id=case_id)


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/pipeline/{case_id}", response_model=PipelineResult)
async def launch_pipeline(
    case_id: str,
    mode: str = Query("sample", pattern="^(sample|all)$"),
    sample_images: int = Query(80, ge=1, le=5000),
    sample_audios: int = Query(40, ge=1, le=2000),
):
    """Launch parallel detection jobs. Default is a sample, not the full case."""
    factory = get_session_factory()
    with factory() as db:
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Caso não encontrado")

        image_items = _list_case_media(db, case_id, "image/")
        audio_items = _list_case_media(db, case_id, "audio/")
        image_hashes, img_missing = _select_and_extract(
            db,
            case_id,
            image_items,
            mode=mode,
            limit=sample_images,
            preferred_mimes=PREFERRED_IMAGE,
        )
        audio_hashes, aud_missing = _select_and_extract(
            db,
            case_id,
            audio_items,
            mode=mode,
            limit=sample_audios,
            preferred_mimes=("audio/opus", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav"),
        )

    skipped: dict[str, str] = {}
    warnings: list[str] = []
    job_ids: dict[str, str] = {}
    missing_files = img_missing + aud_missing
    if missing_files:
        warnings.append(f"{missing_files} arquivo(s) sem binário no UFDR/cache")
    if mode == "sample":
        warnings.append(
            f"Modo amostra: {len(image_hashes)} imagem(ns), {len(audio_hashes)} áudio(s)"
        )

    async def _ok(url: str) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{url}/health")
            if resp.status_code != 200:
                return False
            try:
                body = resp.json()
            except Exception:
                return True
            if isinstance(body, dict) and str(body.get("status") or "").lower() in (
                "loading",
                "starting",
            ):
                return False
            return True
        except Exception:
            return False

    image_kinds = [
        ("yolo", VISION_URL, _run_yolo_job),
        ("faces", FACE_URL, _run_face_job),
        ("plates", PLATE_URL, _run_plate_job),
        ("ocr", OCR_URL, _run_ocr_job),
    ]

    if image_hashes:
        for kind, url, runner in image_kinds:
            if not await _ok(url):
                skipped[kind] = f"Serviço {kind} indisponível em {url}"
                continue
            job_id = str(uuid4())
            job_ids[kind] = job_id
            emit_progress(
                job_id,
                kind,
                "pending",
                0.0,
                f"Na fila: {kind} em {len(image_hashes)} imagens",
                case_id=case_id,
            )
            t = threading.Thread(
                target=runner, args=(job_id, case_id, image_hashes), daemon=True
            )
            t.start()
    else:
        warnings.append("Nenhuma imagem extraível no caso para YOLO/faces/placas/OCR")

    if audio_hashes:
        if await _ok(ASR_URL):
            job_id = str(uuid4())
            job_ids["asr"] = job_id
            emit_progress(
                job_id,
                "asr",
                "pending",
                0.0,
                f"Na fila: ASR em {len(audio_hashes)} áudios",
                case_id=case_id,
            )
            t = threading.Thread(
                target=_run_asr_job, args=(job_id, case_id, audio_hashes), daemon=True
            )
            t.start()
        else:
            skipped["asr"] = f"Serviço ASR indisponível em {ASR_URL}"
    else:
        warnings.append("Nenhum áudio extraível no caso para ASR")

    if not job_ids and skipped:
        raise HTTPException(
            status_code=503,
            detail="Nenhum serviço ML disponível: " + "; ".join(skipped.values()),
        )

    return PipelineResult(
        jobs_launched=len(job_ids),
        job_ids=job_ids,
        skipped=skipped,
        warnings=warnings,
        mode=mode,
        image_count=len(image_hashes),
        audio_count=len(audio_hashes),
        missing_files=missing_files,
    )


@router.post("/chunk/{case_id}")
def backfill_chunks(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Build message chunks when ingest skipped them (lexical search backfill)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, UUID(case_id), user.user_id)
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Caso não encontrado")
        try:
            count = chunk_messages(db, UUID(case_id))
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Falha ao gerar chunks: {e}"
            ) from e
    from .cache import cache_delete

    cache_delete(f"sokol:stats:{case_id}")
    return {"chunks_created": count, "case_id": case_id}


class EmbedJobStatus(BaseModel):
    job_id: str | None = None
    status: str
    stage: str | None = None
    done: int = 0
    total: int = 0
    error: str | None = None
    chunks_total: int = 0
    chunks_embedded: int = 0
    events_total: int = 0
    events_embedded: int = 0


def _embed_coverage(db, case_id: UUID) -> dict[str, int]:
    chunks_total = db.execute(
        text("SELECT count(*) FROM chunks WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    chunks_embedded = db.execute(
        text(
            "SELECT count(*) FROM chunks WHERE case_id = :cid AND embedding IS NOT NULL"
        ),
        {"cid": case_id},
    ).scalar() or 0
    events_total = db.execute(
        text("SELECT count(*) FROM events WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    events_embedded = db.execute(
        text(
            "SELECT count(*) FROM events WHERE case_id = :cid AND embedding IS NOT NULL"
        ),
        {"cid": case_id},
    ).scalar() or 0
    return {
        "chunks_total": int(chunks_total),
        "chunks_embedded": int(chunks_embedded),
        "events_total": int(events_total),
        "events_embedded": int(events_embedded),
    }


@router.get("/embed/{case_id}", response_model=EmbedJobStatus)
def embed_status(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Coverage + latest embed job for this case."""
    cid = UUID(case_id)
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, cid, user.user_id)
        cov = _embed_coverage(db, cid)
        row = db.execute(
            text("""
                SELECT id, status, payload, error
                FROM jobs
                WHERE case_id = :cid AND kind = 'embed'
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"cid": cid},
        ).mappings().first()

    status = EmbedJobStatus(**cov, status="idle")
    if not row:
        if cov["chunks_embedded"] or cov["events_embedded"]:
            status.status = "done"
        return status

    payload = row["payload"]
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {}
    if not isinstance(payload, dict):
        payload = {}
    status.job_id = str(row["id"])
    status.status = row["status"]
    status.stage = payload.get("stage")
    status.done = int(payload.get("done") or 0)
    status.total = int(payload.get("total") or 0)
    status.error = row["error"]
    return status


@router.post("/embed/{case_id}", response_model=EmbedJobStatus)
def launch_embed(
    case_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Enqueue a background job to embed chunks + events for the Agent."""
    cid = UUID(case_id)
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, cid, user.user_id)
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Caso não encontrado")

        existing = db.execute(
            text("""
                SELECT id, status, payload, error
                FROM jobs
                WHERE case_id = :cid AND kind = 'embed'
                  AND status IN ('pending', 'running')
                ORDER BY created_at DESC
                LIMIT 1
            """),
            {"cid": cid},
        ).mappings().first()
        cov = _embed_coverage(db, cid)
        if existing:
            payload = existing["payload"] if isinstance(existing["payload"], dict) else {}
            return EmbedJobStatus(
                job_id=str(existing["id"]),
                status=existing["status"],
                stage=payload.get("stage") if isinstance(payload, dict) else None,
                **cov,
            )

        if cov["chunks_embedded"] >= cov["chunks_total"] and cov["events_embedded"] >= cov["events_total"] and cov["events_total"] > 0:
            return EmbedJobStatus(status="done", **cov)

        job_id = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO jobs (id, case_id, kind, payload, status, pipeline_version, created_at, updated_at)
                VALUES (:id, :cid, 'embed', CAST(:payload AS jsonb), 'pending', 'v1', :now, :now)
            """),
            {
                "id": job_id,
                "cid": cid,
                "payload": json.dumps({"stage": "queued", "done": 0, "total": 0}),
                "now": now,
            },
        )
        append_audit(
            db,
            case_id=cid,
            actor_user_id=user.user_id,
            action="embed.enqueue",
            payload={"job_id": str(job_id)},
        )
        db.commit()

    from .cache import cache_delete

    cache_delete(f"sokol:stats:{case_id}")
    return EmbedJobStatus(
        job_id=str(job_id),
        status="pending",
        stage="queued",
        **cov,
    )


def _collect_pipeline_jobs(case_id: str | None = None) -> list[dict]:
    from .jobs import _job_events

    pipeline_jobs = {}
    for job_id, events in _job_events.items():
        if not events:
            continue
        latest = events[-1]
        if latest.get("stage") not in ("yolo", "faces", "plates", "asr", "ocr"):
            continue
        if case_id and str(latest.get("case_id") or "") != str(case_id):
            continue
        pipeline_jobs[job_id] = {
            "job_id": job_id,
            "kind": latest.get("stage"),
            "status": latest.get("status"),
            "progress": latest.get("progress", 0),
            "message": latest.get("message", ""),
            "case_id": latest.get("case_id"),
        }
    return list(pipeline_jobs.values())


@router.get("/pipeline/{case_id}")
@router.get("/status/{case_id}")
async def pipeline_status(case_id: str):
    """Get status of detection jobs for this case only."""
    return _collect_pipeline_jobs(case_id)


@router.get("/status")
async def all_pipeline_status(
    user: CurrentUser = Depends(get_current_user),
):
    """Global pipeline jobs — platform admin only. Media tab uses /status/{case_id}."""
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)
    return _collect_pipeline_jobs(None)
