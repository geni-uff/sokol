"""SOKOL API — Watchlists and hit tracking (with global watchlist support)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


# ── Models ─────────────────────────────────────────────────────────────────
class WatchlistCreate(BaseModel):
    case_id: Optional[str] = None  # None = global watchlist
    name: str
    description: Optional[str] = None
    watch_type: str  # 'phone', 'name', 'keyword', 'entity', 'plate'
    patterns: list[str]
    is_global: bool = False


class Watchlist(BaseModel):
    id: str
    case_id: Optional[str]
    name: str
    description: Optional[str]
    watch_type: str
    patterns: list[str]
    is_global: bool
    is_active: bool
    created_by: str
    created_at: datetime


class WatchlistHit(BaseModel):
    id: str
    watchlist_id: str
    case_id: Optional[str]
    event_id: Optional[str]
    message_id: Optional[str]
    matched_pattern: str
    matched_text: str
    confidence: float
    acknowledged: bool
    created_at: datetime


class ScanRequest(BaseModel):
    case_id: str
    limit: int = 1000


# ── Helpers ────────────────────────────────────────────────────────────────
def _row_to_watchlist(row) -> Watchlist:
    return Watchlist(
        id=str(row["id"]),
        case_id=str(row["case_id"]) if row["case_id"] else None,
        name=row["name"],
        description=row["description"],
        watch_type=row["watch_type"],
        patterns=row["patterns"] if isinstance(row["patterns"], list) else [],
        is_global=bool(row.get("is_global", False)),
        is_active=row["is_active"],
        created_by=str(row["created_by"]),
        created_at=row["created_at"],
    )


def _row_to_hit(row) -> WatchlistHit:
    return WatchlistHit(
        id=str(row["id"]),
        watchlist_id=str(row["watchlist_id"]),
        case_id=str(row["case_id"]) if row.get("case_id") else None,
        event_id=str(row["event_id"]) if row.get("event_id") else None,
        message_id=str(row["message_id"]) if row.get("message_id") else None,
        matched_pattern=row["matched_pattern"],
        matched_text=row["matched_text"],
        confidence=row["confidence"],
        acknowledged=row["acknowledged"],
        created_at=row["created_at"],
    )


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=Watchlist)
def create_watchlist(body: WatchlistCreate, user_id: str = "system"):
    factory = get_session_factory()
    with factory() as db:
        wl_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]
        case_id = None if body.is_global else body.case_id

        if body.is_global:
            db.execute(
                text("""
                    INSERT INTO watchlists (id, case_id, name, description, watch_type, patterns, is_global, created_by)
                    VALUES (:id, NULL, :name, :description, :watch_type, :patterns, true, :created_by)
                """),
                {
                    "id": wl_id,
                    "name": body.name,
                    "description": body.description,
                    "watch_type": body.watch_type,
                    "patterns": body.patterns,
                    "created_by": user_id,
                },
            )
        else:
            if not body.case_id:
                raise HTTPException(
                    status_code=400, detail="case_id required for non-global watchlist"
                )
            db.execute(
                text("""
                    INSERT INTO watchlists (id, case_id, name, description, watch_type, patterns, created_by)
                    VALUES (:id, :case_id, :name, :description, :watch_type, :patterns, :created_by)
                """),
                {
                    "id": wl_id,
                    "case_id": body.case_id,
                    "name": body.name,
                    "description": body.description,
                    "watch_type": body.watch_type,
                    "patterns": body.patterns,
                    "created_by": user_id,
                },
            )
        db.commit()

        row = db.execute(
            text("SELECT * FROM watchlists WHERE id = :id"), {"id": wl_id}
        ).fetchone()
        return _row_to_watchlist(row)


@router.get("/global", response_model=list[Watchlist])
def list_global_watchlists():
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text(
                "SELECT * FROM watchlists WHERE is_global = true ORDER BY created_at DESC"
            )
        ).fetchall()
        return [_row_to_watchlist(r) for r in rows]


@router.get("/{case_id}", response_model=list[Watchlist])
def list_watchlists(case_id: str):
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT * FROM watchlists
                WHERE case_id = :case_id OR is_global = true
                ORDER BY is_global DESC, created_at DESC
            """),
            {"case_id": case_id},
        ).fetchall()
        return [_row_to_watchlist(r) for r in rows]


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: str):
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("DELETE FROM watchlists WHERE id = :id"), {"id": watchlist_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        db.commit()
    return {"status": "deleted"}


@router.post("/{watchlist_id}/toggle")
def toggle_watchlist(watchlist_id: str):
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text(
                "UPDATE watchlists SET is_active = NOT is_active WHERE id = :id RETURNING is_active"
            ),
            {"id": watchlist_id},
        )
        row = result.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        db.commit()
    return {"is_active": row[0]}


@router.get("/{watchlist_id}/hits", response_model=list[WatchlistHit])
def list_hits(watchlist_id: str, limit: int = Query(50, ge=1, le=200)):
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT * FROM watchlist_hits
                WHERE watchlist_id = :watchlist_id
                ORDER BY created_at DESC LIMIT :limit
            """),
            {"watchlist_id": watchlist_id, "limit": limit},
        ).fetchall()
        return [_row_to_hit(r) for r in rows]


@router.post("/hits/{hit_id}/acknowledge")
def acknowledge_hit(hit_id: str):
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("UPDATE watchlist_hits SET acknowledged = true WHERE id = :id"),
            {"id": hit_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Hit not found")
        db.commit()
    return {"status": "acknowledged"}


@router.get("/{case_id}/hits/summary")
def hits_summary(case_id: str):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) as total_hits,
                    COUNT(*) FILTER (WHERE NOT acknowledged) as unacknowledged,
                    COUNT(DISTINCT watchlist_id) as watchlists_with_hits
                FROM watchlist_hits wh
                JOIN watchlists w ON wh.watchlist_id = w.id
                WHERE w.case_id = :case_id OR w.is_global = true
            """),
            {"case_id": case_id},
        ).fetchone()
        return {
            "total_hits": row[0],
            "unacknowledged": row[1],
            "watchlists_with_hits": row[2],
        }


# ── Scan endpoint ──────────────────────────────────────────────────────────
@router.post("/scan")
def scan_case(body: ScanRequest):
    """Scan all active watchlists (case-specific + global) against a case's events and messages."""
    factory = get_session_factory()
    hits_created = 0

    with factory() as db:
        watchlists = db.execute(
            text("""
                SELECT * FROM watchlists
                WHERE is_active = true AND (case_id = :cid OR is_global = true)
            """),
            {"cid": body.case_id},
        ).fetchall()

        if not watchlists:
            return {"hits_created": 0, "watchlists_scanned": 0}

        events = db.execute(
            text("""
                SELECT id, kind, summary, source, dest, ts
                FROM events WHERE case_id = :cid
                ORDER BY ts DESC LIMIT :lim
            """),
            {"cid": body.case_id, "lim": body.limit},
        ).fetchall()

        messages = db.execute(
            text("""
                SELECT id, body, sender, receiver, ts
                FROM messages WHERE case_id = :cid
                ORDER BY ts DESC LIMIT :lim
            """),
            {"cid": body.case_id, "lim": body.limit},
        ).fetchall()

        existing_hashes = set()
        existing = db.execute(
            text("""
                SELECT watchlist_id, matched_pattern, event_id, message_id
                FROM watchlist_hits wh
                JOIN watchlists w ON wh.watchlist_id = w.id
                WHERE w.case_id = :cid OR w.is_global = true
            """),
            {"cid": body.case_id},
        ).fetchall()
        for e in existing:
            key = (
                str(e["watchlist_id"]),
                e["matched_pattern"],
                str(e["event_id"] or ""),
                str(e["message_id"] or ""),
            )
            existing_hashes.add(key)

        for wl in watchlists:
            wl_id = str(wl["id"])
            patterns = wl["patterns"] if isinstance(wl["patterns"], list) else []
            watch_type = wl["watch_type"]

            compiled = []
            for p in patterns:
                try:
                    compiled.append((p, re.compile(re.escape(p), re.IGNORECASE)))
                except re.error:
                    compiled.append((p, None))

            for event in events:
                searchable = " ".join(
                    str(event[k] or "") for k in ("summary", "source", "dest")
                )
                for pattern_str, regex in compiled:
                    if regex and regex.search(searchable):
                        key = (wl_id, pattern_str, str(event["id"]), "")
                        if key not in existing_hashes:
                            db.execute(
                                text("""
                                    INSERT INTO watchlist_hits
                                    (id, watchlist_id, case_id, event_id, matched_pattern, matched_text, confidence)
                                    VALUES (gen_random_uuid(), :wid, :cid, :eid, :pat, :txt, 1.0)
                                """),
                                {
                                    "wid": wl_id,
                                    "cid": body.case_id,
                                    "eid": str(event["id"]),
                                    "pat": pattern_str,
                                    "txt": str(event.get("summary", ""))[:500],
                                },
                            )
                            hits_created += 1
                            existing_hashes.add(key)

            for msg in messages:
                searchable = " ".join(
                    str(msg[k] or "") for k in ("body", "sender", "receiver")
                )
                for pattern_str, regex in compiled:
                    if regex and regex.search(searchable):
                        key = (wl_id, pattern_str, "", str(msg["id"]))
                        if key not in existing_hashes:
                            db.execute(
                                text("""
                                    INSERT INTO watchlist_hits
                                    (id, watchlist_id, case_id, message_id, matched_pattern, matched_text, confidence)
                                    VALUES (gen_random_uuid(), :wid, :cid, :mid, :pat, :txt, 1.0)
                                """),
                                {
                                    "wid": wl_id,
                                    "cid": body.case_id,
                                    "mid": str(msg["id"]),
                                    "pat": pattern_str,
                                    "txt": str(msg.get("body", ""))[:500],
                                },
                            )
                            hits_created += 1
                            existing_hashes.add(key)

        db.commit()

    return {"hits_created": hits_created, "watchlists_scanned": len(watchlists)}
