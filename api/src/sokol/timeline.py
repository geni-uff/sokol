"""SOKOL timeline — API endpoints for timeline events."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/events", tags=["events"])


class EventResponse(BaseModel):
    id: str
    ts: str | None
    tz_original: str | None
    kind: str
    actor: str | None
    counterpart: str | None
    app: str | None
    ref_table: str | None
    ref_id: str | None
    summary: str
    meta: dict | None = None


class TimelineResponse(BaseModel):
    events: list[EventResponse]
    total: int
    case_id: str


class CaseStats(BaseModel):
    events: int
    messages: int
    chunks: int
    entities: int
    media: int


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    case_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    kind: str | None = None,
    app: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """Get timeline events for a case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        conditions = ["e.case_id = :cid"]
        bind = {"cid": case_id, "limit": limit, "offset": offset}

        if kind:
            conditions.append("e.kind = :kind")
            bind["kind"] = kind
        if app:
            conditions.append("e.app = :app")
            bind["app"] = app

        where = " AND ".join(conditions)

        # Get total count
        count_result = db.execute(
            text(f"""
                SELECT count(*) FROM events e WHERE {where}
            """),
            bind,
        ).scalar()

        # Get events
        rows = db.execute(
            text(f"""
                SELECT e.id, e.ts, e.tz_original, e.kind, e.actor, e.counterpart,
                       e.app, e.ref_table, e.ref_id, e.summary, e.meta
                FROM events e
                WHERE {where}
                ORDER BY e.ts DESC
                LIMIT :limit OFFSET :offset
            """),
            bind,
        ).fetchall()

        events = [
            EventResponse(
                id=str(r[0]),
                ts=r[1].isoformat() if r[1] else None,
                tz_original=r[2],
                kind=r[3],
                actor=r[4],
                counterpart=r[5],
                app=r[6],
                ref_table=r[7],
                ref_id=str(r[8]) if r[8] else None,
                summary=r[9],
                meta=r[10] if isinstance(r[10], dict) else {},
            )
            for r in rows
        ]

        return TimelineResponse(
            events=events,
            total=count_result,
            case_id=str(case_id),
        )


@router.get("/stats", response_model=CaseStats)
def get_case_stats(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Get case statistics."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        events = db.execute(
            text("SELECT count(*) FROM events WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()

        messages = db.execute(
            text("SELECT count(*) FROM messages WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()

        chunks = db.execute(
            text("SELECT count(*) FROM chunks WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()

        entities = db.execute(
            text("SELECT count(*) FROM entities WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()

        media = db.execute(
            text("SELECT count(*) FROM media"),
        ).scalar()

        messages = db.execute(
            __import__("sqlalchemy").text(
                "SELECT count(*) FROM messages WHERE case_id = :cid"
            ),
            {"cid": case_id},
        ).scalar()

        chunks = db.execute(
            __import__("sqlalchemy").text(
                "SELECT count(*) FROM chunks WHERE case_id = :cid"
            ),
            {"cid": case_id},
        ).scalar()

        entities = db.execute(
            __import__("sqlalchemy").text(
                "SELECT count(*) FROM entities WHERE case_id = :cid"
            ),
            {"cid": case_id},
        ).scalar()

        media = db.execute(
            __import__("sqlalchemy").text("SELECT count(*) FROM media"),
        ).scalar()

        return CaseStats(
            events=events,
            messages=messages,
            chunks=chunks,
            entities=entities,
            media=media,
        )
