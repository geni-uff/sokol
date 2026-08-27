"""Walk UFDR zip members (FileSystem / iCloud warrant) without loading the archive in RAM.

Parses notes, Apple warrant XLSX, EML, and common chat SQLite when present.
Image/video/audio stay in taggedFiles → artefacts; this pass adds structured events.
"""

from __future__ import annotations

import email
import hashlib
import io
import re
import sqlite3
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from email.header import decode_header, make_header
from pathlib import Path

from .parsers.contract import (
    ParseResult,
    ParsedEvent,
    ParsedMessage,
    ParsedEntity,
    parse_ts,
)

_UUID_TXT = re.compile(
    r"^[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\.txt$"
)
_SKIP_NOTE_NAMES = {
    "summary.txt",
    "metadata.txt",
    "downloadsummary.txt",
    "preferences.csv",
}

_SSML = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

_MAX_PARSE_BYTES = 80 * 1024 * 1024
_MAX_NESTED_ZIP = 80 * 1024 * 1024
_MAX_HASH_BYTES = 80 * 1024 * 1024

_MEDIA_EXT: dict[str, tuple[str, str, str]] = {
    ".jpg": ("image", "image/jpeg", "Image"),
    ".jpeg": ("image", "image/jpeg", "Image"),
    ".png": ("image", "image/png", "Image"),
    ".heic": ("image", "image/heic", "Image"),
    ".webp": ("image", "image/webp", "Image"),
    ".gif": ("image", "image/gif", "Image"),
    ".opus": ("audio", "audio/opus", "Audio"),
    ".m4a": ("audio", "audio/mp4", "Audio"),
    ".mp3": ("audio", "audio/mpeg", "Audio"),
    ".aac": ("audio", "audio/aac", "Audio"),
    ".wav": ("audio", "audio/wav", "Audio"),
    ".mp4": ("video", "video/mp4", "Video"),
    ".mov": ("video", "video/quicktime", "Video"),
    ".m4v": ("video", "video/mp4", "Video"),
}


def probe_zip_members(ufdr_path: str | Path) -> dict:
    """Classify zip members without reading payloads (no RAM blow-up)."""
    counts: dict[str, int] = {
        "members": 0,
        "nested_zip": 0,
        "nested_tar": 0,
        "media_image": 0,
        "media_audio": 0,
        "media_video": 0,
        "eml": 0,
        "sqlite": 0,
        "notes_txt": 0,
        "xlsx": 0,
        "largest_member": "",
        "largest_bytes": 0,
    }
    with zipfile.ZipFile(ufdr_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/"):
                continue
            counts["members"] += 1
            if info.file_size > counts["largest_bytes"]:
                counts["largest_bytes"] = info.file_size
                counts["largest_member"] = name
            ext = Path(name).suffix.lower()
            if ext == ".zip":
                counts["nested_zip"] += 1
            elif ext in {".tar", ".tgz", ".gz"}:
                counts["nested_tar"] += 1
            elif ext in {".jpg", ".jpeg", ".png", ".heic", ".webp", ".gif"}:
                counts["media_image"] += 1
            elif ext in {".opus", ".m4a", ".mp3", ".aac", ".wav"}:
                counts["media_audio"] += 1
            elif ext in {".mp4", ".mov", ".m4v"}:
                counts["media_video"] += 1
            elif ext in {".eml", ".emlx"}:
                counts["eml"] += 1
            elif ext in {".sqlite", ".db"}:
                counts["sqlite"] += 1
            elif ext == ".xlsx":
                counts["xlsx"] += 1
            elif _looks_like_note(name.rsplit("/", 1)[-1]):
                counts["notes_txt"] += 1
    return counts


def inventory_fs_media(
    ufdr_path: str | Path, existing_paths: set[str] | None = None
) -> tuple[list[dict], dict]:
    """Emit artefact-shaped file entries for media members. Hash in stream, never load whole files."""
    existing = {p.replace("\\", "/") for p in (existing_paths or set())}
    extra: list[dict] = []
    stats = {"media_members": 0, "media_hashed": 0, "media_unhashed_large": 0}
    with zipfile.ZipFile(ufdr_path, "r") as zf:
        for info in zf.infolist():
            name = info.filename.replace("\\", "/")
            if name.endswith("/") or not name.startswith("files/"):
                continue
            ext = Path(name).suffix.lower()
            if ext not in _MEDIA_EXT:
                continue
            if name in existing or Path(name).name in existing:
                continue
            stats["media_members"] += 1
            sha256 = None
            if 0 < info.file_size <= _MAX_HASH_BYTES:
                sha256 = sha256_stream(zf, info.filename)
                stats["media_hashed"] += 1
            else:
                stats["media_unhashed_large"] += 1
            _kind, _mime, tag = _MEDIA_EXT[ext]
            extra.append(
                {
                    "file_id": f"fs:{name}",
                    "name": Path(name).name,
                    "size": info.file_size,
                    "path": name,
                    "sha256": sha256,
                    "md5": None,
                    "local_path": name,
                    "tag": tag,
                    "timestamps": {},
                }
            )
    return extra, stats


def walk_ufdr_filesystem(ufdr_path: str | Path, device_id: str = "") -> tuple[ParseResult, dict]:
    """Stream zip members under files/. Returns (ParseResult, stats)."""
    ufdr_path = Path(ufdr_path)
    result = ParseResult()
    stats = {
        "members_seen": 0,
        "notes": 0,
        "emails_eml": 0,
        "xlsx_tables": 0,
        "sqlite_hits": 0,
        "gps_points": 0,
        "chat_rows": 0,
        "nested_archives": 0,
        "skipped_large": 0,
        "probe": probe_zip_members(ufdr_path),
    }

    with zipfile.ZipFile(ufdr_path, "r") as zf:
        _walk_zip_handle(zf, device_id, result, stats, require_files_prefix=True)

    return result, stats


def _walk_zip_handle(
    zf: zipfile.ZipFile,
    device_id: str,
    result: ParseResult,
    stats: dict,
    require_files_prefix: bool,
) -> None:
    for info in zf.infolist():
        name = info.filename.replace("\\", "/")
        if name.endswith("/"):
            continue
        if require_files_prefix and not name.startswith("files/"):
            continue
        stats["members_seen"] += 1
        base = name.rsplit("/", 1)[-1]
        lower = base.lower()
        ext = Path(base).suffix.lower()

        if ext in _MEDIA_EXT:
            continue
        if info.file_size > _MAX_PARSE_BYTES:
            stats["skipped_large"] += 1
            continue

        if ext in {".eml", ".emlx"}:
            with zf.open(info) as fh:
                _parse_eml(fh.read(), name, device_id, result)
            stats["emails_eml"] += 1
        elif ext == ".xlsx":
            with zf.open(info) as fh:
                n = _parse_warrant_xlsx(fh.read(), base, device_id, result)
            stats["xlsx_tables"] += n
        elif ext in {".sqlite", ".db"} and "database.db" not in lower:
            added = _parse_sqlite_member(zf, info, device_id, result, stats)
            stats["sqlite_hits"] += added
        elif ext == ".note" or (ext == ".txt" and _looks_like_note(base)):
            with zf.open(info) as fh:
                text = fh.read().decode("utf-8", errors="replace").strip()
            if text:
                _add_note(text, name, device_id, result)
                stats["notes"] += 1
        elif ext == ".zip" and 0 < info.file_size <= _MAX_NESTED_ZIP:
            stats["nested_archives"] += 1
            _walk_nested_zip(zf, info, device_id, result, stats)


def _looks_like_note(filename: str) -> bool:
    if filename.lower() in _SKIP_NOTE_NAMES:
        return False
    if filename.lower().startswith("summary") or filename.lower().startswith("metadata"):
        return False
    return bool(_UUID_TXT.match(filename))


def _add_note(text: str, source: str, device_id: str, result: ParseResult) -> None:
    snippet = text.replace("\n", " ")[:180]
    result.events.append(
        ParsedEvent(
            device_id=device_id,
            kind="note",
            app="notes",
            summary=f"[Nota] {snippet}",
            meta={"source_member": source},
        )
    )


def _decode_hdr(raw: str | None) -> str:
    if not raw:
        return ""
    try:
        return str(make_header(decode_header(raw)))
    except Exception:
        return raw


def _parse_eml(data: bytes, source: str, device_id: str, result: ParseResult) -> None:
    msg = email.message_from_bytes(data)
    sender = _decode_hdr(msg.get("From"))
    recipient = _decode_hdr(msg.get("To"))
    subject = _decode_hdr(msg.get("Subject"))
    date_raw = msg.get("Date")
    ts, tz_orig = parse_ts(date_raw)
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True) or b""
                body = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
                break
    else:
        payload = msg.get_payload(decode=True) or b""
        body = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
    text = f"{subject}\n{body}".strip() if subject else body
    if not text:
        return
    result.messages.append(
        ParsedMessage(
            device_id=device_id,
            app="email",
            sender=sender or None,
            counterpart=recipient or None,
            ts=ts,
            direction="incoming",
            text=text[:20000],
            meta={"source_member": source, "type": "eml"},
        )
    )
    result.events.append(
        ParsedEvent(
            device_id=device_id,
            ts=ts,
            tz_original=tz_orig,
            kind="message",
            actor=sender or None,
            counterpart=recipient or None,
            app="email",
            ref_table="messages",
            summary=f"[Email] {subject or text[:80]}",
            meta={"source_member": source},
        )
    )


def _xlsx_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    out = []
    for si in root.findall(f"{_SSML}si"):
        texts = [t.text or "" for t in si.iter(f"{_SSML}t")]
        out.append("".join(texts))
    return out


def _xlsx_sheet_rows(zf: zipfile.ZipFile, strings: list[str], sheet: str) -> list[list[str]]:
    try:
        root = ET.fromstring(zf.read(sheet))
    except KeyError:
        return []
    rows = []
    for row in root.findall(f".//{_SSML}row"):
        cells = []
        for c in row.findall(f"{_SSML}c"):
            val_el = c.find(f"{_SSML}v")
            raw = val_el.text if val_el is not None else ""
            if c.get("t") == "s" and raw.isdigit():
                idx = int(raw)
                cells.append(strings[idx] if idx < len(strings) else "")
            else:
                cells.append(raw or "")
        if any(cells):
            rows.append(cells)
    return rows


def _parse_warrant_xlsx(data: bytes, filename: str, device_id: str, result: ParseResult) -> int:
    added = 0
    try:
        xz = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile:
        return 0
    strings = _xlsx_strings(xz)
    lower = filename.lower()
    rows = _xlsx_sheet_rows(xz, strings, "xl/worksheets/sheet1.xml")
    if "mail" in lower:
        for row in rows[6:]:
            summary = " | ".join(c.strip() for c in row if c.strip())
            if not summary:
                continue
            ts, tz_orig = parse_ts(row[2] if len(row) > 2 else None)
            result.events.append(
                ParsedEvent(
                    device_id=device_id,
                    ts=ts,
                    tz_original=tz_orig,
                    kind="note",
                    app="icloud-mail-log",
                    summary=f"[Mail log] {summary[:180]}",
                    meta={"source": filename},
                )
            )
            added += 1
    elif "bookmark" in lower:
        for row in rows:
            url = next((c.strip() for c in row if c.strip().startswith("http")), "")
            if not url:
                continue
            ts, tz_orig = parse_ts(next((c for c in row if "T" in c and "Z" in c), None))
            result.events.append(
                ParsedEvent(
                    device_id=device_id,
                    ts=ts,
                    tz_original=tz_orig,
                    kind="web_visit",
                    app="Safari",
                    summary=f"[Web] {url}",
                    meta={"source": filename, "url": url},
                )
            )
            added += 1
    elif "facetime" in lower:
        for row in rows[8:]:
            summary = " | ".join(c.strip() for c in row if c.strip())
            if len(summary) < 8:
                continue
            result.events.append(
                ParsedEvent(
                    device_id=device_id,
                    kind="call",
                    app="FaceTime",
                    summary=f"[FaceTime lookup] {summary[:180]}",
                    meta={"source": filename},
                )
            )
            for cell in row:
                if "@" in cell:
                    result.entities.append(
                        ParsedEntity(kind="email", value=cell.strip().lower(), display_name=cell.strip())
                    )
                digits = re.sub(r"\D+", "", cell)
                if len(digits) >= 10:
                    result.entities.append(
                        ParsedEntity(kind="phone", value=digits, display_name=cell.strip())
                    )
            added += 1
    elif "account" in lower:
        blob = " ".join(strings)
        for match in re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", blob):
            result.entities.append(
                ParsedEntity(kind="email", value=match.lower(), display_name=match)
            )
            added += 1
    return added


def _walk_nested_zip(
    outer: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    device_id: str,
    result: ParseResult,
    stats: dict,
) -> None:
    """Copy a nested zip to a temp file (disk, not RAM) and walk it."""
    with outer.open(info) as src, tempfile.NamedTemporaryFile(suffix=".zip", delete=True) as tmp:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.flush()
        try:
            with zipfile.ZipFile(tmp.name, "r") as inner:
                _walk_zip_handle(
                    inner, device_id, result, stats, require_files_prefix=False
                )
        except zipfile.BadZipFile:
            return


def _add_chat_message(
    device_id: str, app: str, text: str, source: str, result: ParseResult
) -> None:
    snippet = str(text).strip()
    if not snippet:
        return
    result.messages.append(
        ParsedMessage(
            device_id=device_id,
            app=app,
            text=snippet[:20000],
            meta={"source_member": source},
        )
    )
    result.events.append(
        ParsedEvent(
            device_id=device_id,
            kind="message",
            app=app,
            ref_table="messages",
            summary=f"[{app}] {snippet[:120]}",
            meta={"source_member": source},
        )
    )


def _safe_ident(name: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name or ""))


def _parse_sqlite_gps(conn: sqlite3.Connection, device_id: str, source: str, result: ParseResult) -> int:
    added = 0
    tables = [
        r[0]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        if _safe_ident(r[0])
    ]
    for table in tables:
        cols = {c[1].lower(): c[1] for c in conn.execute(f'PRAGMA table_info("{table}")')}
        lat_col = next(
            (cols[k] for k in ("latitude", "lat", "zlatitude", "zlat") if k in cols),
            None,
        )
        lon_col = next(
            (cols[k] for k in ("longitude", "lon", "lng", "zlongitude", "zlon") if k in cols),
            None,
        )
        if not lat_col or not lon_col:
            continue
        ts_col = next(
            (cols[k] for k in cols if "time" in k or k in {"date", "zdate", "timestamp"}),
            None,
        )
        select = f'SELECT "{lat_col}", "{lon_col}"'
        if ts_col and _safe_ident(ts_col):
            select += f', "{ts_col}"'
        try:
            rows = conn.execute(f'{select} FROM "{table}" WHERE "{lat_col}" IS NOT NULL LIMIT 5000')
        except sqlite3.Error:
            continue
        for row in rows:
            try:
                lat = float(row[0])
                lon = float(row[1])
            except (TypeError, ValueError):
                continue
            if abs(lat) > 90 or abs(lon) > 180 or (lat == 0 and lon == 0):
                continue
            ts = tz_orig = None
            if ts_col and len(row) > 2 and row[2] is not None:
                ts, tz_orig = parse_ts(str(row[2]))
            result.events.append(
                ParsedEvent(
                    device_id=device_id,
                    ts=ts,
                    tz_original=tz_orig,
                    kind="location",
                    app="gps",
                    summary=f"[GPS] {lat:.5f},{lon:.5f}",
                    geo_lat=lat,
                    geo_lon=lon,
                    meta={"source_member": source, "table": table},
                )
            )
            added += 1
    return added


def _parse_sqlite_member(
    zf: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    device_id: str,
    result: ParseResult,
    stats: dict | None = None,
) -> int:
    """Copy a sqlite member to a temp file and try WhatsApp/SMS/GPS/notes tables."""
    added = 0
    stats = stats if stats is not None else {}
    with zf.open(info) as src, tempfile.NamedTemporaryFile(suffix=".sqlite", delete=True) as tmp:
        while True:
            chunk = src.read(1024 * 1024)
            if not chunk:
                break
            tmp.write(chunk)
        tmp.flush()
        try:
            conn = sqlite3.connect(tmp.name)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error:
            return 0
        try:
            tables = {
                r[0].lower()
                for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            gps_n = _parse_sqlite_gps(conn, device_id, info.filename, result)
            stats["gps_points"] = stats.get("gps_points", 0) + gps_n
            added += gps_n

            if "messages" in tables:
                cols = {c[1].lower() for c in conn.execute("PRAGMA table_info(messages)")}
                text_col = "text" if "text" in cols else ("body" if "body" in cols else None)
                if text_col:
                    for row in conn.execute(
                        f"SELECT {text_col} FROM messages WHERE {text_col} IS NOT NULL LIMIT 5000"
                    ):
                        _add_chat_message(
                            device_id, "whatsapp", str(row[0]), info.filename, result
                        )
                        added += 1
                        stats["chat_rows"] = stats.get("chat_rows", 0) + 1

            if "message" in tables:
                cols = {c[1].lower() for c in conn.execute("PRAGMA table_info(message)")}
                if "text" in cols:
                    for row in conn.execute(
                        "SELECT text FROM message WHERE text IS NOT NULL LIMIT 5000"
                    ):
                        _add_chat_message(
                            device_id, "sms", str(row[0]), info.filename, result
                        )
                        added += 1
                        stats["chat_rows"] = stats.get("chat_rows", 0) + 1

            if "zwamessage" in tables:
                cols = {c[1].lower() for c in conn.execute("PRAGMA table_info(ZWAMESSAGE)")}
                text_col = "ztext" if "ztext" in cols else None
                if text_col:
                    for row in conn.execute(
                        "SELECT ZTEXT FROM ZWAMESSAGE WHERE ZTEXT IS NOT NULL LIMIT 5000"
                    ):
                        _add_chat_message(
                            device_id, "whatsapp", str(row[0]), info.filename, result
                        )
                        added += 1
                        stats["chat_rows"] = stats.get("chat_rows", 0) + 1

            if "note" in tables or "znote" in tables:
                table = "ZNOTE" if "znote" in tables else "note"
                cols = [c[1].lower() for c in conn.execute(f"PRAGMA table_info({table})")]
                body_col = next((c for c in cols if "body" in c or "text" in c or "content" in c), None)
                if body_col and _safe_ident(body_col):
                    for row in conn.execute(f"SELECT {body_col} FROM {table} LIMIT 2000"):
                        if row[0]:
                            _add_note(str(row[0]), info.filename, device_id, result)
                            added += 1
        except sqlite3.Error:
            return added
        finally:
            conn.close()
    return added


def sha256_stream(zf: zipfile.ZipFile, name: str) -> str:
    h = hashlib.sha256()
    with zf.open(name) as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
