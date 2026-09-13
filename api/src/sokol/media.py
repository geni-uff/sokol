"""SOKOL API — Media viewers and management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import bindparam, text
from uuid import UUID

from .auth import (
    CurrentUser,
    get_current_user,
    get_media_user,
    require_case_member,
    require_platform_admin,
)
from .db import get_session_factory
from .ufdr_extract import (
    ensure_media_on_disk,
    media_cache_file_count,
    normalize_ufdr_path,
)

router = APIRouter(prefix="/media", tags=["media"])

# Extension -> mime, mirrors worker/mime_map.py (kept in sync manually since
# the api and worker containers ship as separate images/dependencies).
_EXTENSION_MIME: dict[str, str] = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heic",
    ".bmp": "image/bmp",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".opus": "audio/opus",
    ".aac": "audio/aac",
    ".wav": "audio/wav",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".mov": "video/quicktime",
    ".m4v": "video/mp4",
    ".3gp": "video/3gpp",
    ".3gpp": "video/3gpp",
    ".avi": "video/x-msvideo",
    ".webm": "video/webm",
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".txt": "text/plain",
    ".csv": "text/csv",
    ".html": "text/html",
    ".json": "application/json",
    ".vcf": "text/vcard",
    ".eml": "message/rfc822",
}

# Extensions that are never worth sniffing/promoting to a media kind even
# when their bytes coincidentally match an image/audio signature: Cellebrite
# internal caches (.thumb — a JPEG-derived preview of a photo that already
# has its own real media row) and app-internal binary blobs (game/app asset
# packs, plists, raw databases). Left as application/octet-stream / kind
# "other" so they land in "Outros arquivos" instead of duplicating/cluttering
# the main gallery. NOTE: .vcf/.eml are deliberately NOT here — they're
# human-readable content (contacts/email), not internal-tool noise, so they
# get a real mime via _EXTENSION_MIME below and show up as documents.
_NEVER_SNIFF_EXT = {
    ".thumb",
    ".pak",
    ".iwa",
    ".tml",
    ".bnk",
    ".binarycookies",
    ".protected",
    ".dat",
    ".bytes",
    ".plist",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".sql",
}

MEDIA_CACHE_DIR = Path(os.getenv("SOKOL_MEDIA_CACHE_DIR", "/data/media-cache"))
UFDR_EXTRACT_DIR = Path(os.getenv("SOKOL_UFDR_EXTRACT_DIR", "/data/ufdr-extract"))

GENERIC_MIME = {"application/octet-stream", "application/octetstream", ""}

_DOCUMENT_MIME_PREFIXES = (
    "text/",
    "application/pdf",
    "application/json",
    "application/xml",
    "message/",
)
_DOCUMENT_MIME_EXACT = {
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-powerpoint",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
}


def classify_mime(mime_type: str | None) -> str:
    """Bucket a mime type into image/audio/video/document/other for the UI."""
    if not mime_type or mime_type in GENERIC_MIME:
        return "other"
    if mime_type.startswith("image/"):
        return "image"
    if mime_type.startswith("audio/"):
        return "audio"
    if mime_type.startswith("video/"):
        return "video"
    if mime_type.startswith(_DOCUMENT_MIME_PREFIXES) or mime_type in _DOCUMENT_MIME_EXACT:
        return "document"
    return "other"


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


def sniff_media_mime(path: Path) -> str | None:
    """Best-effort magic-byte sniff across image/audio/video/document types.

    Superset of `sniff_image_mime`, used when a stored mime is generic
    (`application/octet-stream`) and we want to recover the real type from
    file content rather than trust a (possibly missing/wrong) extension.
    """
    image = sniff_image_mime(path)
    if image:
        return image
    try:
        with path.open("rb") as fh:
            head = fh.read(32)
    except OSError:
        return None
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "audio/wav"
    if head[:4] == b"OggS":
        return "audio/ogg"
    if head[:4] == b"fLaC":
        return "audio/flac"
    if head[:3] == b"ID3" or head[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return "audio/mpeg"
    if len(head) >= 12 and head[4:8] == b"ftyp":
        brand = head[8:12].lower()
        if brand.startswith(b"3gp"):
            return "video/3gpp"
        if brand in (b"m4a ", b"m4a\x20", b"m4a\x00"):
            return "audio/mp4"
        return "video/mp4"
    if head[:4] == b"%PDF":
        return "application/pdf"
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
    kind: str
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
                    kind=classify_mime(r[1]),
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

        if mime_type in GENERIC_MIME and not _should_skip_sniff(storage_ref or {}):
            sniffed = sniff_media_mime(file_path)
            if sniffed:
                mime_type = sniffed
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
        sniffed = None if _should_skip_sniff(storage_ref or {}) else sniff_image_mime(file_path)
        if sniffed and (mime_type or "") in GENERIC_MIME:
            db.execute(
                text("UPDATE media SET mime_type = :m WHERE hash = :h"),
                {"m": sniffed, "h": media_hash},
            )
            db.commit()
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


def _storage_ref_name(storage_ref: dict) -> str:
    return str(
        storage_ref.get("local_path")
        or storage_ref.get("path")
        or storage_ref.get("file_id")
        or ""
    )


def _guess_mime_from_storage_ref(storage_ref: dict) -> str | None:
    """Best-effort filename lookup across the storage_ref shapes media rows use."""
    ext = Path(_storage_ref_name(storage_ref)).suffix.lower()
    return _EXTENSION_MIME.get(ext)


def _should_skip_sniff(storage_ref: dict) -> bool:
    """True when the filename marks this as never worth sniffing (see _NEVER_SNIFF_EXT)."""
    ext = Path(_storage_ref_name(storage_ref)).suffix.lower()
    return ext in _NEVER_SNIFF_EXT


@router.post("/{case_id}/backfill-mime")
def backfill_mime(
    case_id: UUID,
    limit: int = Query(2000, ge=1, le=20000),
    user: CurrentUser = Depends(get_current_user),
):
    """Re-classify media rows stuck at a generic mime type for this case.

    Tries, in order: filename/extension (covers rows ingested before the
    extension tables were fixed/unified), then magic-byte sniffing of the
    file content (covers files with a missing/wrong extension). Rows that
    remain unclassifiable stay `application/octet-stream` and surface in the
    "Outros arquivos" section of the media tab rather than the main grid.
    """
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)

        # Exclude known-never-sniffable extensions in SQL itself (not just in
        # the Python loop below): otherwise a case dominated by Cellebrite
        # .thumb caches (frequently the bulk of its "media" rows) fills the
        # entire LIMIT window on every call and the real unresolved rows
        # never get a turn across repeated calls.
        never_sniff_pattern = "\\.(" + "|".join(e.lstrip(".") for e in sorted(_NEVER_SNIFF_EXT)) + ")$"
        query = text("""
            SELECT DISTINCT m.hash, m.storage_ref
            FROM media m
            LEFT JOIN messages msg ON msg.media_hash = m.hash AND msg.case_id = :cid
            LEFT JOIN artifacts art ON art.media_hash = m.hash AND art.case_id = :cid
            WHERE (msg.id IS NOT NULL OR art.id IS NOT NULL)
              AND (m.mime_type IS NULL OR m.mime_type IN :generic)
              AND COALESCE(m.storage_ref->>'local_path', '') !~* :never_sniff
            ORDER BY m.hash
            LIMIT :limit
        """).bindparams(bindparam("generic", expanding=True))

        rows = db.execute(
            query,
            {
                "cid": case_id,
                "generic": sorted(GENERIC_MIME),
                "never_sniff": never_sniff_pattern,
                "limit": limit,
            },
        ).fetchall()

        updated_by_name = 0
        updated_by_sniff = 0
        skipped_never_sniff = 0
        unresolved = 0
        COMMIT_EVERY = 200

        for i, (media_hash, storage_ref) in enumerate(rows, start=1):
            if isinstance(storage_ref, str):
                try:
                    storage_ref = json.loads(storage_ref)
                except json.JSONDecodeError:
                    storage_ref = {}
            storage_ref = storage_ref or {}

            new_mime = _guess_mime_from_storage_ref(storage_ref)
            if new_mime:
                db.execute(
                    text("UPDATE media SET mime_type = :m WHERE hash = :h"),
                    {"m": new_mime, "h": media_hash},
                )
                updated_by_name += 1
            elif _should_skip_sniff(storage_ref):
                # Cellebrite/app-internal artifact (.thumb, .plist, .db, ...):
                # never worth extracting from the UFDR just to sniff bytes.
                skipped_never_sniff += 1
            else:
                file_path = ensure_media_on_disk(db, case_id, media_hash, storage_ref)
                if file_path is None:
                    file_path = _resolve_media_path(storage_ref, media_hash)
                sniffed = sniff_media_mime(file_path) if file_path else None
                if sniffed:
                    db.execute(
                        text("UPDATE media SET mime_type = :m WHERE hash = :h"),
                        {"m": sniffed, "h": media_hash},
                    )
                    updated_by_sniff += 1
                else:
                    unresolved += 1

            if i % COMMIT_EVERY == 0:
                db.commit()

        db.commit()

        return {
            "scanned": len(rows),
            "updated_by_name": updated_by_name,
            "updated_by_sniff": updated_by_sniff,
            "skipped_never_sniff": skipped_never_sniff,
            "unresolved": unresolved,
        }
