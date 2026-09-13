"""Select the next chronological media batch for the detection pipeline.

Sample mode skips hashes already seen in this case so a second click
advances in time instead of repeating the first N items.
"""

from __future__ import annotations

import json

from sqlalchemy import text

PREFERRED_IMAGE = ("image/jpeg", "image/jpg", "image/png", "image/webp", "image/heic")
PREFERRED_AUDIO = ("audio/opus", "audio/mpeg", "audio/mp4", "audio/ogg", "audio/wav", "audio/aac")
PREFERRED_VIDEO = ("video/mp4", "video/quicktime", "video/webm", "video/3gpp")


def next_unseen(items: list[dict], seen: set[str], limit: int) -> list[dict]:
    """Return up to `limit` items not in `seen`, preserving input order."""
    if limit <= 0:
        return []
    out: list[dict] = []
    for item in items:
        h = item.get("hash")
        if not h or h in seen:
            continue
        out.append(item)
        if len(out) >= limit:
            break
    return out


def load_seen(db, case_id: str, kind: str) -> set[str]:
    rows = db.execute(
        text("""
            SELECT media_hash FROM pipeline_sample_seen
            WHERE case_id = :cid AND kind = :kind
        """),
        {"cid": case_id, "kind": kind},
    ).fetchall()
    return {r[0] for r in rows}


def mark_seen(db, case_id: str, kind: str, hashes: list[str]) -> None:
    for h in hashes:
        db.execute(
            text("""
                INSERT INTO pipeline_sample_seen (case_id, media_hash, kind)
                VALUES (:cid, :h, :kind)
                ON CONFLICT (case_id, media_hash, kind) DO NOTHING
            """),
            {"cid": case_id, "h": h, "kind": kind},
        )


def remaining_count(db, case_id: str, kind: str, total: int) -> int:
    seen = db.execute(
        text("""
            SELECT COUNT(*) FROM pipeline_sample_seen
            WHERE case_id = :cid AND kind = :kind
        """),
        {"cid": case_id, "kind": kind},
    ).scalar()
    return max(0, total - int(seen or 0))


def list_case_media(db, case_id: str, mime_prefix: str, *, allow_octet: bool) -> list[dict]:
    """Case-scoped media linked to messages or artifacts, oldest first."""
    octet = "OR m.mime_type = 'application/octet-stream'" if allow_octet else ""
    rows = (
        db.execute(
            text(f"""
            SELECT hash, mime_type, storage_ref, media_ts FROM (
                SELECT
                    m.hash,
                    m.mime_type,
                    m.storage_ref,
                    COALESCE(MIN(msg.ts), MIN(m.created_at)) AS media_ts
                FROM media m
                LEFT JOIN messages msg
                  ON msg.media_hash = m.hash AND msg.case_id = :cid
                LEFT JOIN artifacts a
                  ON a.media_hash = m.hash AND a.case_id = :cid
                WHERE (msg.media_hash IS NOT NULL OR a.media_hash IS NOT NULL)
                  AND (
                    m.mime_type LIKE :prefix
                    {octet}
                  )
                GROUP BY m.hash, m.mime_type, m.storage_ref
            ) t
            ORDER BY media_ts ASC NULLS LAST, hash ASC
            """),
            {"cid": case_id, "prefix": f"{mime_prefix}%"},
        )
        .mappings()
        .all()
    )
    out = []
    for r in rows:
        ref = r["storage_ref"] or {}
        if isinstance(ref, str):
            try:
                ref = json.loads(ref)
            except json.JSONDecodeError:
                ref = {}
        out.append(
            {
                "hash": r["hash"],
                "mime_type": r["mime_type"] or "",
                "storage_ref": ref,
                "media_ts": r["media_ts"],
            }
        )
    return out
