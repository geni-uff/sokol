"""SOKOL API — Watchlists and hit tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/watchlists", tags=["watchlists"])


# ── Models ─────────────────────────────────────────────────────────────────
class WatchlistCreate(BaseModel):
    case_id: str
    name: str
    description: Optional[str] = None
    watch_type: str  # 'phone', 'name', 'keyword', 'entity'
    patterns: list[str]  # list of patterns to watch


class Watchlist(BaseModel):
    id: str
    case_id: str
    name: str
    description: Optional[str]
    watch_type: str
    patterns: list[str]
    is_active: bool
    created_by: str
    created_at: datetime


class WatchlistHit(BaseModel):
    id: str
    watchlist_id: str
    event_id: Optional[str]
    message_id: Optional[str]
    matched_pattern: str
    matched_text: str
    confidence: float
    acknowledged: bool
    created_at: datetime


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=Watchlist)
def create_watchlist(body: WatchlistCreate, user_id: str = "system"):
    """Create a new watchlist."""
    factory = get_session_factory()
    with factory() as db:
        watchlist_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO watchlists (id, case_id, name, description, watch_type, patterns, created_by)
                VALUES (:id, :case_id, :name, :description, :watch_type, :patterns, :created_by)
            """),
            {
                "id": watchlist_id,
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
            text("SELECT * FROM watchlists WHERE id = :id"), {"id": watchlist_id}
        ).fetchone()
        return Watchlist(
            id=str(row["id"]),
            case_id=str(row["case_id"]),
            name=row["name"],
            description=row["description"],
            watch_type=row["watch_type"],
            patterns=row["patterns"],
            is_active=row["is_active"],
            created_by=str(row["created_by"]),
            created_at=row["created_at"],
        )


@router.get("/{case_id}", response_model=list[Watchlist])
def list_watchlists(case_id: str):
    """List all watchlists for a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text(
                "SELECT * FROM watchlists WHERE case_id = :case_id ORDER BY created_at DESC"
            ),
            {"case_id": case_id},
        ).fetchall()
        return [
            Watchlist(
                id=str(r["id"]),
                case_id=str(r["case_id"]),
                name=r["name"],
                description=r["description"],
                watch_type=r["watch_type"],
                patterns=r["patterns"],
                is_active=r["is_active"],
                created_by=str(r["created_by"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


@router.delete("/{watchlist_id}")
def delete_watchlist(watchlist_id: str):
    """Delete a watchlist."""
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
    """Toggle watchlist active status."""
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
    """List hits for a watchlist."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT * FROM watchlist_hits
                WHERE watchlist_id = :watchlist_id
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"watchlist_id": watchlist_id, "limit": limit},
        ).fetchall()
        return [
            WatchlistHit(
                id=str(r["id"]),
                watchlist_id=str(r["watchlist_id"]),
                event_id=str(r["event_id"]) if r["event_id"] else None,
                message_id=str(r["message_id"]) if r["message_id"] else None,
                matched_pattern=r["matched_pattern"],
                matched_text=r["matched_text"],
                confidence=r["confidence"],
                acknowledged=r["acknowledged"],
                created_at=r["created_at"],
            )
            for r in rows
        ]


@router.post("/hits/{hit_id}/acknowledge")
def acknowledge_hit(hit_id: str):
    """Acknowledge a watchlist hit."""
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
    """Get summary of all watchlist hits for a case."""
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
                WHERE w.case_id = :case_id
            """),
            {"case_id": case_id},
        ).fetchone()
        return {
            "total_hits": row[0],
            "unacknowledged": row[1],
            "watchlists_with_hits": row[2],
        }
