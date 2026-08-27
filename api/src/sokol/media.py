"""SOKOL API — Media viewers and management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import text
from uuid import UUID

from .auth import CurrentUser, get_current_user, get_media_user, require_case_member
from .db import get_session_factory
from .ufdr_extract import (
    ensure_media_on_disk,
    media_cache_file_count,
    normalize_ufdr_path,
)

router = APIRouter(prefix="/media", tags=["media"])

MEDIA_CACHE_DIR = Path(os.getenv("SOKOL_MEDIA_CACHE_DIR", "/data/media-cache"))
UFDR_EXTRACT_DIR = Path(os.getenv("SOKOL_UFDR_EXTRACT_DIR", "/data/ufdr-extract"))

GENERIC_MIME = {"application/octet-stream", "application/octetstream", ""}


def sniff_image_mime(path: Path) -> str | None:
    """Best-effort magic-byte sniff for common image types."""
    try:
        with path.open("rb") as fh:
            head = fh.read(16)
    except OSError:
        return None
    if head[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if head[:4] == b"GIF8":
        return "image/gif"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12].lower()
        if brand in (b"heic", b"heif", b"mif1", b"msf1"):
            return "image/heic"
    return None


def _resolve_media_path(storage_ref: dict, media_hash: str) -> Path | None:
    if not storage_ref:
        cache = MEDIA_CACHE_DIR / media_hash
        return cache if cache.exists() else None
    if "path" in storage_ref:
        p = Path(normalize_ufdr_path(str(storage_ref["path"])))
        return p if p.exists() else None
    if "local_path" in storage_ref:
        local_path = normalize_ufdr_path(str(storage_ref["local_path"]))
        direct = UFDR_EXTRACT_DIR / local_path
        if direct.exists():
            return direct
        basename = Path(local_path).name
        extract_hit = UFDR_EXTRACT_DIR / basename
        if extract_hit.is_file():
            return extract_hit
        cache_path = MEDIA_CACHE_DIR / local_path
        if cache_path.exists():
            return cache_path
        hashed = MEDIA_CACHE_DIR / media_hash
        return hashed if hashed.exists() else None
    if "ufdr_member" in storage_ref or "source_member" in storage_ref:
        file_path = MEDIA_CACHE_DIR / media_hash
        return file_path if file_path.exists() else None
    hashed = MEDIA_CACHE_DIR / media_hash
    return hashed if hashed.exists() else None


# ── Models ─────────────────────────────────────────────────────────────────
class MediaInfo(BaseModel):
    hash: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    storage_ref: dict
    thumbnail_ref: Optional[str]
    created_at: str


class MediaListItem(BaseModel):
    hash: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    thumbnail_available: bool
    usage_count: int


class MediaListResponse(BaseModel):
    items: list[MediaListItem]
    total: int
    cache_files: int = 0


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.get("/{case_id}", response_model=MediaListResponse)
def list_media(
    case_id: UUID,
    mime_type: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
):
    """List media files used in a case — from messages AND artifacts."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        base = """
            FROM media m
            LEFT JOIN (
                SELECT media_hash, COUNT(*) as msg_count
                FROM messages
                WHERE case_id = :case_id AND media_hash IS NOT NULL
                GROUP BY media_hash
            ) msg ON msg.media_hash = m.hash
            LEFT JOIN (
                SELECT media_hash, COUNT(*) as art_count
                FROM artifacts
                WHERE case_id = :case_id AND media_hash IS NOT NULL
                GROUP BY media_hash
            ) art ON art.media_hash = m.hash
            WHERE (msg.msg_count IS NOT NULL OR art.art_count IS NOT NULL)
        """
        params = {"case_id": case_id, "limit": limit, "offset": offset}

        if mime_type:
            base += " AND m.mime_type LIKE :mime_type"
            params["mime_type"] = f"{mime_type}%"

        total = db.execute(text("SELECT COUNT(*) " + base), params).scalar()

        rows = db.execute(
            text(
                """
                SELECT
                    m.hash,
                    m.mime_type,
                    m.size_bytes,
                    m.thumbnail_ref IS NOT NULL as thumbnail_available,
                    COALESCE(msg_count, 0) + COALESCE(art_count, 0) as usage_count
                """
                + base
                + " ORDER BY usage_count DESC, m.hash LIMIT :limit OFFSET :offset"
            ),
            params,
        ).fetchall()

        return MediaListResponse(
            items=[
                MediaListItem(
                    hash=r[0],
                    mime_type=r[1],
                    size_bytes=r[2],
                    thumbnail_available=r[3],
                    usage_count=r[4],
                )
                for r in rows
            ],
            total=total,
            cache_files=media_cache_file_count(),
        )


@router.get("/file/{media_hash}")
def get_media_file(
    media_hash: str,
    case_id: UUID = Query(...),
    user: CurrentUser = Depends(get_media_user),
):
    """Get media file by hash — only if linked to case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        row = db.execute(
            text("""
                SELECT m.storage_ref, m.mime_type
                FROM media m
                LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :cid
                LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :cid
                WHERE m.hash = :hash AND (msg.id IS NOT NULL OR art.id IS NOT NULL)
            """),
            {"hash": media_hash, "cid": case_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Media not found in case")

        storage_ref = row[0]
        mime_type = row[1] or "application/octet-stream"
        if isinstance(storage_ref, str):
            try:
                storage_ref = json.loads(storage_ref)
            except json.JSONDecodeError:
                storage_ref = {}

        file_path = ensure_media_on_disk(db, case_id, media_hash, storage_ref)
        if file_path is None:
            file_path = _resolve_media_path(storage_ref or {}, media_hash)
        if file_path is None:
            raise HTTPException(status_code=404, detail="Media file not found on disk")

        if mime_type in GENERIC_MIME or not mime_type.startswith("image/"):
            sniffed = sniff_image_mime(file_path)
            if sniffed:
                mime_type = sniffed
                if mime_type in GENERIC_MIME or row[1] in GENERIC_MIME:
                    db.execute(
                        text("UPDATE media SET mime_type = :m WHERE hash = :h"),
                        {"m": sniffed, "h": media_hash},
                    )
                    db.commit()

        return FileResponse(file_path, media_type=mime_type)


@router.get("/thumbnail/{media_hash}")
def get_media_thumbnail(
    media_hash: str,
    case_id: UUID = Query(...),
    user: CurrentUser = Depends(get_media_user),
):
    """Get media thumbnail by hash — only if linked to case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        row = db.execute(
            text("""
                SELECT m.thumbnail_ref, m.mime_type, m.storage_ref
                FROM media m
                LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :cid
                LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :cid
                WHERE m.hash = :hash AND (msg.id IS NOT NULL OR art.id IS NOT NULL)
            """),
            {"hash": media_hash, "cid": case_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Thumbnail not found in case")

        thumb_ref, mime_type, storage_ref = row[0], row[1], row[2]
        if isinstance(storage_ref, str):
            try:
                storage_ref = json.loads(storage_ref)
            except json.JSONDecodeError:
                storage_ref = {}
        if thumb_ref:
            thumbnail_path = Path(thumb_ref)
            if thumbnail_path.exists():
                return FileResponse(thumbnail_path, media_type="image/jpeg")

        file_path = ensure_media_on_disk(db, case_id, media_hash, storage_ref)
        if file_path is None:
            file_path = _resolve_media_path(storage_ref or {}, media_hash)
        if file_path is None:
            raise HTTPException(status_code=404, detail="Thumbnail file not found")
        sniffed = sniff_image_mime(file_path)
        if not sniffed and not (mime_type or "").startswith("image/"):
            raise HTTPException(status_code=404, detail="Thumbnail not found in case")
        return FileResponse(file_path, media_type=sniffed or mime_type or "image/jpeg")


@router.get("/info/{media_hash}", response_model=MediaInfo)
def get_media_info(
    media_hash: str,
    case_id: UUID = Query(...),
    user: CurrentUser = Depends(get_current_user),
):
    """Get media metadata — only if linked to case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        row = db.execute(
            text("""
                SELECT m.*
                FROM media m
                LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :cid
                LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :cid
                WHERE m.hash = :hash AND (msg.id IS NOT NULL OR art.id IS NOT NULL)
            """),
            {"hash": media_hash, "cid": case_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Media not found in case")

        return MediaInfo(
            hash=row["hash"],
            mime_type=row["mime_type"],
            size_bytes=row["size_bytes"],
            storage_ref=row["storage_ref"],
            thumbnail_ref=row["thumbnail_ref"],
            created_at=str(row["created_at"]),
        )


@router.get("/{case_id}/stats")
def media_stats(case_id: str):
    """Get media statistics for a case — from messages AND artifacts."""
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("""
                SELECT
                    COUNT(DISTINCT m.hash) as total_files,
                    COALESCE(SUM(m.size_bytes), 0) as total_size,
                    COUNT(DISTINCT m.mime_type) as file_types,
                    COUNT(DISTINCT m.hash) FILTER (WHERE m.mime_type LIKE 'image/%') as images,
                    COUNT(DISTINCT m.hash) FILTER (WHERE m.mime_type LIKE 'video/%') as videos,
                    COUNT(DISTINCT m.hash) FILTER (WHERE m.mime_type LIKE 'audio/%') as audio
                FROM media m
                LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :case_id
                LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :case_id
                WHERE msg.id IS NOT NULL OR art.id IS NOT NULL
            """),
            {"case_id": case_id},
        ).fetchone()
        return {
            "total_files": row[0],
            "total_size_bytes": row[1],
            "total_size_mb": round(row[1] / (1024 * 1024), 2) if row[1] else 0,
            "file_types": row[2],
            "images": row[3],
            "videos": row[4],
            "audio": row[5],
            "cache_files": media_cache_file_count(),
        }
