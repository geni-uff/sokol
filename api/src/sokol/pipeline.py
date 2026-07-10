"""SOKOL API — Parallel auto-detection pipeline.

Spawns independent background jobs for each detection type (YOLO, faces, plates, ASR).
Each job updates the jobs table with progress, and the UI polls for status.
"""

from __future__ import annotations

import asyncio
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory
from .jobs import emit_progress

router = APIRouter(prefix="/detect", tags=["detect"])

MEDIA_CACHE = Path("/data/media-cache")
VISION_URL = "http://localhost:8007"
FACE_URL = "http://localhost:8011"
PLATE_URL = "http://localhost:8010"
ASR_URL = "http://localhost:8009"


# ── Models ─────────────────────────────────────────────────────────────────
class PipelineResult(BaseModel):
    jobs_launched: int
    job_ids: dict[str, str]


class JobStatus(BaseModel):
    job_id: str
    kind: str
    status: str
    progress: float
    message: str


# ── Helpers ────────────────────────────────────────────────────────────────
def _find_media_file(media_hash: str) -> Optional[Path]:
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


def _get_case_images(db, case_id: str) -> list[str]:
    rows = (
        db.execute(
            text("""
            SELECT DISTINCT m.hash
            FROM media m
            LEFT JOIN (SELECT media_hash FROM messages WHERE case_id = :cid AND media_hash IS NOT NULL) msg ON msg.media_hash = m.hash
            LEFT JOIN (SELECT media_hash FROM artifacts WHERE case_id = :cid AND media_hash IS NOT NULL) art ON art.media_hash = m.hash
            WHERE (msg.media_hash IS NOT NULL OR art.media_hash IS NOT NULL)
              AND m.mime_type LIKE 'image/%'
        """),
            {"cid": case_id},
        )
        .mappings()
        .all()
    )
    return [r["hash"] for r in rows]


def _get_case_audios(db, case_id: str) -> list[str]:
    rows = (
        db.execute(
            text("""
            SELECT DISTINCT m.hash
            FROM media m
            LEFT JOIN (SELECT media_hash FROM messages WHERE case_id = :cid AND media_hash IS NOT NULL) msg ON msg.media_hash = m.hash
            LEFT JOIN (SELECT media_hash FROM artifacts WHERE case_id = :cid AND media_hash IS NOT NULL) art ON art.media_hash = m.hash
            WHERE (msg.media_hash IS NOT NULL OR art.media_hash IS NOT NULL)
              AND (m.mime_type LIKE 'audio/%' OR m.mime_type = 'application/octet-stream')
        """),
            {"cid": case_id},
        )
        .mappings()
        .all()
    )
    return [r["hash"] for r in rows]


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
        )

        total = len(image_hashes)
        batch_size = 16
        total_dets = 0

        for i in range(0, total, batch_size):
            batch = image_hashes[i : i + batch_size]
            paths = []
            hashes = []
            for h in batch:
                p = _find_media_file(h)
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
            job_id, "yolo", "completed", 1.0, f"Done: {total_dets} object detections"
        )

    except Exception as e:
        emit_progress(job_id, "yolo", "failed", 0.0, str(e))


def _run_face_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run face detection and store embeddings."""
    try:
        emit_progress(
            job_id,
            "faces",
            "running",
            0.0,
            f"Detecting faces in {len(image_hashes)} images...",
        )

        total = len(image_hashes)
        total_stored = 0

        for i, h in enumerate(image_hashes):
            p = _find_media_file(h)
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
        )

    except Exception as e:
        emit_progress(job_id, "faces", "failed", 0.0, str(e))


def _run_plate_job(job_id: str, case_id: str, image_hashes: list[str]):
    """Run plate detection on images."""
    try:
        emit_progress(
            job_id,
            "plates",
            "running",
            0.0,
            f"Detecting plates in {len(image_hashes)} images...",
        )

        total = len(image_hashes)
        total_plates = 0

        for i, h in enumerate(image_hashes):
            p = _find_media_file(h)
            if not p:
                continue

            try:
                with httpx.Client(timeout=60) as client:
                    with open(p, "rb") as f:
                        files = {"file": (p.name, f, "image/jpeg")}
                        resp = client.post(f"{PLATE_URL}/api/plate", files=files)
                        resp.raise_for_status()
                        result = resp.json()

                plates = result.get("plates", [])
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
                                    "text": plate.get("plate", ""),
                                    "conf": plate.get("confidence", 0),
                                    "bbox": json.dumps(plate.get("bbox", [])),
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

            except Exception:
                continue

        emit_progress(
            job_id, "plates", "completed", 1.0, f"Done: {total_plates} plates detected"
        )

    except Exception as e:
        emit_progress(job_id, "plates", "failed", 0.0, str(e))


def _run_asr_job(job_id: str, case_id: str, audio_hashes: list[str]):
    """Run ASR transcription on audio files."""
    try:
        emit_progress(
            job_id,
            "asr",
            "running",
            0.0,
            f"Transcribing {len(audio_hashes)} audio files...",
        )

        total = len(audio_hashes)
        total_transcribed = 0

        for i, h in enumerate(audio_hashes):
            p = _find_media_file(h)
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
        )

    except Exception as e:
        emit_progress(job_id, "asr", "failed", 0.0, str(e))


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/pipeline/{case_id}", response_model=PipelineResult)
async def launch_pipeline(case_id: str):
    """Launch parallel detection jobs for a case (YOLO, faces, plates, ASR)."""
    factory = get_session_factory()
    with factory() as db:
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        image_hashes = _get_case_images(db, case_id)
        audio_hashes = _get_case_audios(db, case_id)

    job_ids = {}

    if image_hashes:
        for kind, runner in [
            ("yolo", _run_yolo_job),
            ("faces", _run_face_job),
            ("plates", _run_plate_job),
        ]:
            job_id = str(uuid4())
            job_ids[kind] = job_id
            emit_progress(
                job_id,
                kind,
                "pending",
                0.0,
                f"Queued {kind} detection for {len(image_hashes)} images",
            )
            t = threading.Thread(
                target=runner, args=(job_id, case_id, image_hashes), daemon=True
            )
            t.start()

    if audio_hashes:
        job_id = str(uuid4())
        job_ids["asr"] = job_id
        emit_progress(
            job_id,
            "asr",
            "pending",
            0.0,
            f"Queued ASR for {len(audio_hashes)} audio files",
        )
        t = threading.Thread(
            target=_run_asr_job, args=(job_id, case_id, audio_hashes), daemon=True
        )
        t.start()

    return PipelineResult(jobs_launched=len(job_ids), job_ids=job_ids)


@router.get("/status/{case_id}")
async def pipeline_status(case_id: str):
    """Get status of all detection jobs for a case."""
    from .jobs import _job_events

    pipeline_jobs = {}
    for job_id, events in _job_events.items():
        if events:
            latest = events[-1]
            if latest.get("stage") in ("yolo", "faces", "plates", "asr"):
                pipeline_jobs[job_id] = {
                    "job_id": job_id,
                    "kind": latest.get("stage"),
                    "status": latest.get("status"),
                    "progress": latest.get("progress", 0),
                    "message": latest.get("message", ""),
                }

    return list(pipeline_jobs.values())


@router.get("/status")
async def all_pipeline_status():
    """Get status of all running pipeline jobs."""
    from .jobs import _job_events

    jobs = []
    for job_id, events in _job_events.items():
        if events:
            latest = events[-1]
            stage = latest.get("stage", "")
            if stage in ("yolo", "faces", "plates", "asr"):
                jobs.append(
                    {
                        "job_id": job_id,
                        "kind": stage,
                        "status": latest.get("status"),
                        "progress": latest.get("progress", 0),
                        "message": latest.get("message", ""),
                    }
                )
    return jobs
