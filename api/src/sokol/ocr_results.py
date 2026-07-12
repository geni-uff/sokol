"""SOKOL API — OCR results endpoints."""

from __future__ import annotations

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/ocr", tags=["ocr"])


class OCRResult(BaseModel):
    id: str
    case_id: str
    media_hash: str
    mime_type: Optional[str] = None
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    lines: list = []
    created_at: str


@router.get("/{case_id}", response_model=list[OCRResult])
def list_ocr_results(
    case_id: UUID,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        base = """
            SELECT o.id, o.case_id, o.media_hash, m.mime_type,
                   o.text, o.confidence, o.language, o.lines, o.created_at
            FROM ocr_results o
            LEFT JOIN media m ON m.hash = o.media_hash
            WHERE o.case_id = :cid
        """
        params: dict = {"cid": case_id, "limit": limit}

        if search:
            base += " AND to_tsvector('portuguese', o.text) @@ plainto_tsquery('portuguese', :search)"
            params["search"] = search

        base += " ORDER BY o.created_at DESC LIMIT :limit"

        rows = db.execute(text(base), params).fetchall()

        return [
            OCRResult(
                id=str(r[0]),
                case_id=str(r[1]),
                media_hash=r[2],
                mime_type=r[3],
                text=r[4],
                confidence=r[5],
                language=r[6],
                lines=r[7] if isinstance(r[7], list) else [],
                created_at=str(r[8]),
            )
            for r in rows
        ]
