"""SOKOL API — Media viewers and management."""

from __future__ import annotations

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

router = APIRouter(prefix="/media", tags=["media"])

MEDIA_CACHE_DIR = Path(os.getenv("SOKOL_MEDIA_CACHE_DIR", "/data/media-cache"))
UFDR_EXTRACT_DIR = Path(os.getenv("SOKOL_UFDR_EXTRACT_DIR", "/data/ufdr-extract"))


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

        # Resolve file path from storage_ref
        if "path" in storage_ref:
            file_path = Path(storage_ref["path"])
        elif "local_path" in storage_ref:
            local_path = storage_ref["local_path"]
            # local_path is relative to extracted UFDR dir (e.g., "files/Image/foo.jpg")
            # Search in all subdirs of UFDR_EXTRACT_DIR for the file
            file_path = None
            # 1. Try direct path under UFDR_EXTRACT_DIR (fallback)
            direct = UFDR_EXTRACT_DIR / local_path
            if direct.exists():
                file_path = direct
            else:
                # 2. Glob all subdirs for the basename
                basename = Path(local_path).name
                for candidate in UFDR_EXTRACT_DIR.rglob(basename):
                    if candidate.is_file():
                        file_path = candidate
                        break
                # 3. Also try MEDIA_CACHE_DIR
                if file_path is None:
                    cache_path = MEDIA_CACHE_DIR / local_path
                    if cache_path.exists():
                        file_path = cache_path
            if file_path is None:
                raise HTTPException(
                    status_code=404, detail="Media file not found on disk"
                )
        elif "ufdr_member" in storage_ref or "source_member" in storage_ref:
            member = storage_ref.get("ufdr_member") or storage_ref.get(
                "source_member", ""
            )
            file_path = MEDIA_CACHE_DIR / media_hash
            if not file_path.exists():
                raise HTTPException(
                    status_code=404,
                    detail="Media not cached on disk.",
                )
        else:
            raise HTTPException(status_code=500, detail="Invalid storage reference")

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Media file not found on disk")

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
                SELECT m.thumbnail_ref, m.mime_type
                FROM media m
                LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :cid
                LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :cid
                WHERE m.hash = :hash AND (msg.id IS NOT NULL OR art.id IS NOT NULL)
            """),
            {"hash": media_hash, "cid": case_id},
        ).fetchone()
        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="Thumbnail not found in case")

        thumbnail_path = Path(row[0])
        if not thumbnail_path.exists():
            raise HTTPException(status_code=404, detail="Thumbnail file not found")

        mime_type = "image/jpeg"  # Thumbnails are always JPEG
        return FileResponse(thumbnail_path, media_type=mime_type)


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
        }
