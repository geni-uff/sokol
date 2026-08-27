"""Extract a media member from a case UFDR zip into the media cache.

Cellebrite paths use Windows backslashes (`files\\Image\\….thumb`). Ingest
inventories hashes without extracting binaries; this helper does it lazily.

Author: Matheus C. Pestana
"""

from __future__ import annotations

import json
import os
import zipfile
from pathlib import Path
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

MEDIA_CACHE_DIR = Path(os.getenv("SOKOL_MEDIA_CACHE_DIR", "/data/media-cache"))
STAGING_DIR = Path(os.getenv("SOKOL_STAGING_DIR", "/data/staging"))
INBOX_DIR = Path(os.getenv("SOKOL_INBOX_DIR", "/ingest/inbox"))

_zip_index: dict[str, dict[str, str]] = {}


def normalize_ufdr_path(raw: str | None) -> str:
    if not raw:
        return ""
    return raw.replace("\\", "/").lstrip("/")


def _parse_payload(payload: object) -> dict:
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}
    return {}


def find_case_ufdr_paths(db: Session, case_id: UUID | str) -> list[Path]:
    """Locate UFDR zip files for a case (staging job payload, inbox uri, glob)."""
    found: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if not resolved.is_file():
            return
        key = str(resolved)
        if key in seen:
            return
        seen.add(key)
        found.append(resolved)

    job_rows = db.execute(
        text("""
            SELECT payload FROM jobs
            WHERE case_id = :cid AND kind = 'ingest'
        """),
        {"cid": case_id},
    ).fetchall()
    for row in job_rows:
        payload = _parse_payload(row[0])
        staging = payload.get("staging_path")
        if staging:
            p = Path(str(staging))
            _add(p)
            _add(STAGING_DIR / p.name)

    doc_rows = db.execute(
        text("""
            SELECT source_uri, title FROM documents
            WHERE case_id = :cid AND source_type = 'ufdr'
        """),
        {"cid": case_id},
    ).mappings().all()
    for doc in doc_rows:
        uri = doc["source_uri"] or ""
        title = doc["title"] or ""
        ref = uri.split(":", 1)[1] if uri.startswith("inbox:") else title
        if ref:
            _add(INBOX_DIR / ref)
            _add(STAGING_DIR / Path(ref).name)

    if found:
        return found

    if STAGING_DIR.is_dir():
        for p in STAGING_DIR.glob("*.ufdr"):
            _add(p)
    if INBOX_DIR.is_dir():
        for p in INBOX_DIR.rglob("*.ufdr"):
            _add(p)

    return found


def _zip_member_index(zip_path: Path) -> dict[str, str]:
    key = str(zip_path)
    cached = _zip_index.get(key)
    if cached is not None:
        return cached
    index: dict[str, str] = {}
    with zipfile.ZipFile(zip_path, "r") as zf:
        for name in zf.namelist():
            posix = normalize_ufdr_path(name)
            index[posix] = name
            index[posix.lower()] = name
            base = Path(posix).name
            if base and base not in index:
                index[base] = name
                index[base.lower()] = name
    _zip_index[key] = index
    return index


def _match_member(index: dict[str, str], local_path: str, file_id: str | None) -> str | None:
    posix = normalize_ufdr_path(local_path)
    if not posix and not file_id:
        return None
    for candidate in (posix, posix.lower(), Path(posix).name, Path(posix).name.lower()):
        if candidate and candidate in index:
            return index[candidate]
    if file_id:
        fid = str(file_id).lower()
        for key, member in index.items():
            if fid in key.lower():
                return member
    return None


def extract_media_from_ufdr(
    zip_path: Path,
    dest: Path,
    local_path: str | None,
    file_id: str | None = None,
) -> Path | None:
    if not zip_path.is_file():
        return None
    index = _zip_member_index(zip_path)
    member = _match_member(index, local_path or "", file_id)
    if not member:
        return None
    dest.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        with zf.open(member) as src:
            data = src.read()
    if not data:
        return None
    dest.write_bytes(data)
    return dest


def ensure_media_on_disk(
    db: Session,
    case_id: UUID | str,
    media_hash: str,
    storage_ref: dict | None,
) -> Path | None:
    """Return a readable cache path, extracting from the UFDR if needed."""
    MEDIA_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cached = MEDIA_CACHE_DIR / media_hash
    if cached.is_file() and cached.stat().st_size > 0:
        return cached

    ref = storage_ref or {}
    local_path = ref.get("local_path") or ref.get("path") or ""
    file_id = ref.get("file_id")

    for ufdr in find_case_ufdr_paths(db, case_id):
        extracted = extract_media_from_ufdr(ufdr, cached, str(local_path), str(file_id) if file_id else None)
        if extracted is not None:
            return extracted
    return cached if cached.is_file() and cached.stat().st_size > 0 else None


def media_cache_file_count() -> int:
    if not MEDIA_CACHE_DIR.is_dir():
        return 0
    return sum(1 for p in MEDIA_CACHE_DIR.iterdir() if p.is_file())
