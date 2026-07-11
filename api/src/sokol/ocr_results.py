"""SOKOL API — OCR results endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/ocr", tags=["ocr"])


class OCRResult(BaseModel):
    id: str
    case_id: str
    media_hash: str
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    lines: list = []
    created_at: str


@router.get("/{case_id}", response_model=list[OCRResult])
def list_ocr_results(
    case_id: str,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    factory = get_session_factory()
    with factory() as db:
        if search:
            rows = db.execute(
                text("""
                    SELECT * FROM ocr_results
                    WHERE case_id = :cid
                      AND to_tsvector('portuguese', text) @@ plainto_tsquery('portuguese', :search)
                    ORDER BY created_at DESC LIMIT :limit
                """),
                {"cid": case_id, "search": search, "limit": limit},
            ).fetchall()
        else:
            rows = db.execute(
                text(
                    "SELECT * FROM ocr_results WHERE case_id = :cid ORDER BY created_at DESC LIMIT :limit"
                ),
                {"cid": case_id, "limit": limit},
            ).fetchall()

        return [
            OCRResult(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                media_hash=r["media_hash"],
                text=r["text"],
                confidence=r["confidence"],
                language=r["language"],
                lines=r["lines"] if isinstance(r["lines"], list) else [],
                created_at=str(r["created_at"]),
            )
            for r in rows
        ]
