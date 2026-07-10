"""SOKOL API — Plate detection and transcription endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

plates_router = APIRouter(prefix="/plates", tags=["plates"])
transcriptions_router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])


# ── Plates ─────────────────────────────────────────────────────────────────
class PlateResult(BaseModel):
    id: str
    case_id: str
    media_hash: str
    plate_text: str
    confidence: Optional[float] = None
    label: Optional[str] = None
    created_at: str


@plates_router.get("/{case_id}", response_model=list[PlateResult])
def list_plates(
    case_id: str,
    label: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    factory = get_session_factory()
    with factory() as db:
        query = "SELECT * FROM plate_detections WHERE case_id = :cid"
        params: dict = {"cid": case_id, "limit": limit}
        if label:
            query += " AND label = :label"
            params["label"] = label
        query += " ORDER BY created_at DESC LIMIT :limit"
        rows = db.execute(text(query), params).fetchall()
        return [
            PlateResult(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                media_hash=r["media_hash"],
                plate_text=r["plate_text"],
                confidence=r["confidence"],
                label=r["label"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]


@plates_router.put("/{plate_id}/label")
def label_plate(plate_id: str, label: str):
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("UPDATE plate_detections SET label = :label WHERE id = :id"),
            {"id": plate_id, "label": label},
        )
        db.commit()
        if result.rowcount == 0:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Plate not found")
        return {"ok": True, "label": label}


# ── Transcriptions ─────────────────────────────────────────────────────────
class TranscriptionResult(BaseModel):
    id: str
    case_id: str
    media_hash: str
    text: str
    language: Optional[str] = None
    created_at: str


@transcriptions_router.get("/{case_id}", response_model=list[TranscriptionResult])
def list_transcriptions(
    case_id: str,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    factory = get_session_factory()
    with factory() as db:
        if search:
            rows = db.execute(
                text("""
                    SELECT * FROM transcriptions
                    WHERE case_id = :cid
                      AND to_tsvector('portuguese', text) @@ plainto_tsquery('portuguese', :search)
                    ORDER BY created_at DESC LIMIT :limit
                """),
                {"cid": case_id, "search": search, "limit": limit},
            ).fetchall()
        else:
            rows = db.execute(
                text(
                    "SELECT * FROM transcriptions WHERE case_id = :cid ORDER BY created_at DESC LIMIT :limit"
                ),
                {"cid": case_id, "limit": limit},
            ).fetchall()

        return [
            TranscriptionResult(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                media_hash=r["media_hash"],
                text=r["text"],
                language=r["language"],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]
