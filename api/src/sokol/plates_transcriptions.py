"""SOKOL API — Plate detection and transcription endpoints."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

plates_router = APIRouter(prefix="/plates", tags=["plates"])
transcriptions_router = APIRouter(prefix="/transcriptions", tags=["transcriptions"])

_WA_JID = re.compile(r"(\d+)@s\.whatsapp\.net", re.IGNORECASE)


def _posix(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.replace("\\", "/").strip() or None


def _file_name(source_member: str | None, original_path: str | None) -> str | None:
    for raw in (source_member, original_path):
        posix = _posix(raw)
        if posix:
            name = Path(posix).name
            if name:
                return name
    return None


def _whatsapp_id(original_path: str | None) -> str | None:
    if not original_path:
        return None
    match = _WA_JID.search(original_path)
    return match.group(1) if match else None


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
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, UUID(case_id), user.user_id)
        query = "SELECT * FROM plate_detections WHERE case_id = :cid"
        params: dict = {"cid": case_id, "limit": limit}
        if label:
            query += " AND label = :label"
            params["label"] = label
        query += " ORDER BY created_at DESC LIMIT :limit"
        rows = db.execute(text(query), params).mappings().all()
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
    mime_type: Optional[str] = None
    size_bytes: Optional[int] = None
    file_name: Optional[str] = None
    source_member: Optional[str] = None
    original_path: Optional[str] = None
    document_title: Optional[str] = None
    app: Optional[str] = None
    sender: Optional[str] = None
    counterpart: Optional[str] = None
    chat_id: Optional[str] = None
    whatsapp_id: Optional[str] = None


@transcriptions_router.get("/{case_id}", response_model=list[TranscriptionResult])
def list_transcriptions(
    case_id: str,
    search: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, UUID(case_id), user.user_id)
        origin_sql = """
            SELECT
                t.id, t.case_id, t.media_hash, t.text, t.language, t.created_at,
                m.mime_type, m.size_bytes,
                a.source_member,
                a.meta->>'original_path' AS original_path,
                d.title AS document_title,
                msg.app, msg.sender, msg.counterpart, msg.chat_id
            FROM transcriptions t
            LEFT JOIN media m ON m.hash = t.media_hash
            LEFT JOIN LATERAL (
                SELECT art.source_member, art.meta, art.document_id
                FROM artifacts art
                WHERE art.case_id = t.case_id AND art.media_hash = t.media_hash
                ORDER BY
                    CASE
                        WHEN art.meta->>'original_path' ILIKE '%/Message/Media/%' THEN 0
                        WHEN art.meta->>'original_path' IS NOT NULL THEN 1
                        ELSE 2
                    END,
                    length(coalesce(art.meta->>'original_path', art.source_member, ''))
                LIMIT 1
            ) a ON true
            LEFT JOIN documents d ON d.id = a.document_id AND d.case_id = t.case_id
            LEFT JOIN LATERAL (
                SELECT app, sender, counterpart, chat_id
                FROM messages
                WHERE case_id = t.case_id AND media_hash = t.media_hash
                ORDER BY ts DESC NULLS LAST
                LIMIT 1
            ) msg ON true
            WHERE t.case_id = :cid
        """
        params: dict = {"cid": case_id, "limit": limit}
        if search:
            origin_sql += """
              AND to_tsvector('portuguese', t.text)
                  @@ plainto_tsquery('portuguese', :search)
            """
            params["search"] = search
        origin_sql += " ORDER BY t.created_at DESC LIMIT :limit"
        rows = db.execute(text(origin_sql), params).mappings().all()

        return [
            TranscriptionResult(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                media_hash=r["media_hash"],
                text=r["text"],
                language=r["language"],
                created_at=str(r["created_at"]),
                mime_type=r["mime_type"],
                size_bytes=r["size_bytes"],
                file_name=_file_name(r["source_member"], r["original_path"]),
                source_member=_posix(r["source_member"]),
                original_path=_posix(r["original_path"]),
                document_title=r["document_title"],
                app=r["app"],
                sender=r["sender"],
                counterpart=r["counterpart"],
                chat_id=r["chat_id"],
                whatsapp_id=_whatsapp_id(r["original_path"]),
            )
            for r in rows
        ]
