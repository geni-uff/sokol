"""SOKOL API — Watchlists and hit tracking (with global watchlist support)."""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member, require_platform_admin
from .db import get_session_factory
from .watchlist_engine import scan_rows

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
    match_type: str = "exact"
    acknowledged: bool
    created_at: datetime


class ScanRequest(BaseModel):
    case_id: str
    limit: int = 1000


# ── Helpers ────────────────────────────────────────────────────────────────
def _row_to_watchlist(row) -> Watchlist:
    m = row._mapping
    return Watchlist(
        id=str(m["id"]),
        case_id=str(m["case_id"]) if m["case_id"] else None,
        name=m["name"],
        description=m["description"],
        watch_type=m["watch_type"],
        patterns=m["patterns"] if isinstance(m["patterns"], list) else [],
        is_global=bool(m.get("is_global", False)),
        is_active=m["is_active"],
        created_by=str(m["created_by"]),
        created_at=m["created_at"],
    )


def _row_to_hit(row) -> WatchlistHit:
    m = row._mapping
    return WatchlistHit(
        id=str(m["id"]),
        watchlist_id=str(m["watchlist_id"]),
        case_id=str(m["case_id"]) if m.get("case_id") else None,
        event_id=str(m["event_id"]) if m.get("event_id") else None,
        message_id=str(m["message_id"]) if m.get("message_id") else None,
        matched_pattern=m["matched_pattern"],
        matched_text=m["matched_text"],
        confidence=m["confidence"],
        match_type=m.get("match_type") or "exact",
        acknowledged=m["acknowledged"],
        created_at=m["created_at"],
    )


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=Watchlist)
def create_watchlist(body: WatchlistCreate, user: CurrentUser = Depends(get_current_user)):
    import json as _json

    factory = get_session_factory()
    with factory() as db:
        wl_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        if body.is_global:
            db.execute(
                text("""
                    INSERT INTO watchlists (id, case_id, name, description, watch_type, patterns, is_global, created_by)
                    VALUES (:id, NULL, :name, :description, :watch_type, CAST(:patterns AS jsonb), true, :created_by)
                """),
                {
                    "id": wl_id,
                    "name": body.name,
                    "description": body.description,
                    "watch_type": body.watch_type,
                    "patterns": _json.dumps(body.patterns),
                    "created_by": user.user_id,
                },
            )
        else:
            if not body.case_id:
                raise HTTPException(
                    status_code=400, detail="case_id required for non-global watchlist"
                )
            require_case_member(db, UUID(body.case_id), user.user_id, roles=["admin", "analista"])
            db.execute(
                text("""
                    INSERT INTO watchlists (id, case_id, name, description, watch_type, patterns, created_by)
                    VALUES (:id, :case_id, :name, :description, :watch_type, CAST(:patterns AS jsonb), :created_by)
                """),
                {
                    "id": wl_id,
                    "case_id": body.case_id,
                    "name": body.name,
                    "description": body.description,
                    "watch_type": body.watch_type,
                    "patterns": _json.dumps(body.patterns),
                    "created_by": user.user_id,
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
def delete_watchlist(
    watchlist_id: str, user: CurrentUser = Depends(get_current_user)
):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT case_id, is_global FROM watchlists WHERE id = :id"),
            {"id": watchlist_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        if row[1]:
            require_platform_admin(db, user.user_id)
        elif row[0]:
            require_case_member(db, row[0], user.user_id, roles=["admin", "analista"])
        db.execute(text("DELETE FROM watchlists WHERE id = :id"), {"id": watchlist_id})
        db.commit()
    return {"status": "deleted"}


@router.post("/{watchlist_id}/toggle")
def toggle_watchlist(
    watchlist_id: str, user: CurrentUser = Depends(get_current_user)
):
    factory = get_session_factory()
    with factory() as db:
        meta = db.execute(
            text("SELECT case_id, is_global FROM watchlists WHERE id = :id"),
            {"id": watchlist_id},
        ).fetchone()
        if not meta:
            raise HTTPException(status_code=404, detail="Watchlist not found")
        if meta[1]:
            require_platform_admin(db, user.user_id)
        elif meta[0]:
            require_case_member(db, meta[0], user.user_id, roles=["admin", "analista"])
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
def scan_case(body: ScanRequest, user: CurrentUser = Depends(get_current_user)):
    """Scan all active watchlists (case-specific + global) against a case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, UUID(body.case_id), user.user_id)
        watchlists_count = db.execute(
            text("""
                SELECT COUNT(*) FROM watchlists
                WHERE is_active = true AND (case_id = :cid OR is_global = true)
            """),
            {"cid": body.case_id},
        ).scalar()
        hits_created = scan_rows(db, body.case_id)
        db.commit()

    return {"hits_created": hits_created, "watchlists_scanned": watchlists_count}
