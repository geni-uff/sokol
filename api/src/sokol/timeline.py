"""SOKOL timeline — API endpoints for timeline events."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from .app_filter import app_filter_sql, app_filter_value
from .auth import CurrentUser, get_current_user, require_case_member
from .cache import cache_get, cache_invalidate, cache_set
from .db import get_session_factory

router = APIRouter(prefix="/events", tags=["events"])


def _case_timezone(db, case_id: UUID) -> str:
    row = db.execute(
        text("SELECT reference_timezone FROM cases WHERE id = :cid"),
        {"cid": case_id},
    ).fetchone()
    return row[0] if row and row[0] else "America/Sao_Paulo"


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
    chunks_embedded: int = 0
    events_embedded: int = 0


class GeoEvent(BaseModel):
    id: str
    ts: str | None
    summary: str
    lat: float
    lon: float
    meta: dict | None = None


@router.get("/timeline", response_model=TimelineResponse)
def get_timeline(
    case_id: UUID,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    kind: str | None = None,
    app: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
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
            conditions.append(app_filter_sql("e.app"))
            bind["app"] = app_filter_value(app)
        if start_date:
            conditions.append("e.ts >= :start_date")
            bind["start_date"] = start_date
        if end_date:
            conditions.append("e.ts <= :end_date")
            bind["end_date"] = end_date

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
                ORDER BY e.ts DESC NULLS LAST
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


@router.get("/apps", response_model=list[str])
def list_event_apps(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Distinct `events.app` values for the case (timeline filter)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        rows = db.execute(
            text(
                """
                SELECT DISTINCT app FROM events
                WHERE case_id = :cid AND app IS NOT NULL AND app <> ''
                ORDER BY app
                """
            ),
            {"cid": case_id},
        ).fetchall()
    return [str(r[0]) for r in rows]


_STATS_TTL = 60  # seconds


@router.get("/stats", response_model=CaseStats)
def get_case_stats(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Get case statistics."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

    cache_key = f"sokol:stats:{case_id}"
    cached = cache_get(cache_key)
    if cached is not None:
        return CaseStats(**cached)

    with factory() as db:
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

        chunks_embedded = db.execute(
            text(
                "SELECT count(*) FROM chunks WHERE case_id = :cid AND embedding IS NOT NULL"
            ),
            {"cid": case_id},
        ).scalar()

        events_embedded = db.execute(
            text(
                "SELECT count(*) FROM events WHERE case_id = :cid AND embedding IS NOT NULL"
            ),
            {"cid": case_id},
        ).scalar()

        entities = db.execute(
            text("SELECT count(*) FROM entities WHERE case_id = :cid"),
            {"cid": case_id},
        ).scalar()

        media = db.execute(
            text(
                "SELECT count(DISTINCT m.hash) FROM media m "
                "JOIN artifacts a ON a.media_hash = m.hash "
                "WHERE a.case_id = :cid"
            ),
            {"cid": case_id},
        ).scalar()

    result = CaseStats(
        events=events or 0,
        messages=messages or 0,
        chunks=chunks or 0,
        entities=entities or 0,
        media=media or 0,
        chunks_embedded=chunks_embedded or 0,
        events_embedded=events_embedded or 0,
    )
    cache_set(cache_key, result.model_dump(), ttl_seconds=_STATS_TTL)
    return result


@router.get("/nearby", response_model=list[dict])
def get_nearby_events(
    case_id: UUID,
    lat: float = Query(...),
    lon: float = Query(...),
    radius_km: float = Query(1.0, ge=0.1, le=100),
    user: CurrentUser = Depends(get_current_user),
):
    """Get events within radius of a point."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        rows = db.execute(
            text("""
                SELECT id, ts, summary, kind,
                       ST_DistanceSphere(geo::geometry, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)) as distance_m
                FROM events
                WHERE case_id = :cid
                  AND geo IS NOT NULL
                  AND ST_DWithin(geo::geography, ST_SetSRID(ST_MakePoint(:lon, :lat), 4326)::geography, :radius_m)
                ORDER BY distance_m ASC
                LIMIT 50
            """),
            {
                "cid": case_id,
                "lat": lat,
                "lon": lon,
                "radius_m": radius_km * 1000,
            },
        ).fetchall()

        return [
            {
                "id": str(r[0]),
                "ts": r[1].isoformat() if r[1] else None,
                "summary": r[2],
                "kind": r[3],
                "distance_m": float(r[4]) if r[4] else 0,
            }
            for r in rows
        ]


@router.get("/geo", response_model=list[GeoEvent])
def get_geo_events(
    case_id: UUID,
    app: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    weekday: int | None = Query(None, ge=0, le=6, description="0=domingo … 6=sábado, fuso do caso"),
    start_hour: float | None = Query(None, ge=0, le=24),
    end_hour: float | None = Query(None, ge=0, le=24),
    grid_lat: float | None = None,
    grid_lon: float | None = None,
    grid_precision: int = Query(3, ge=2, le=5),
    user: CurrentUser = Depends(get_current_user),
):
    """Get geolocalized events for a case, ordered by time.

    Optional filters mirror `/events/timeline` (app, date range) plus a
    recurrence filter (weekday/hour window/grid cell) so a pattern detected
    by `/analytics/{case_id}/location-patterns` can be applied directly to
    the map — e.g. only the "toda segunda, 10h–12h" points.
    """
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        conditions = ["case_id = :cid", "kind = 'location'", "geo IS NOT NULL"]
        bind: dict = {"cid": case_id}

        if app:
            conditions.append(app_filter_sql("app"))
            bind["app"] = app_filter_value(app)
        if start_date:
            conditions.append("ts >= :start_date")
            bind["start_date"] = start_date
        if end_date:
            conditions.append("ts <= :end_date")
            bind["end_date"] = end_date
        if grid_lat is not None and grid_lon is not None:
            conditions.append(
                f"ROUND(ST_Y(geo::geometry)::numeric, {grid_precision}) = :glat"
            )
            conditions.append(
                f"ROUND(ST_X(geo::geometry)::numeric, {grid_precision}) = :glon"
            )
            bind["glat"] = round(grid_lat, grid_precision)
            bind["glon"] = round(grid_lon, grid_precision)

        needs_tz = weekday is not None or start_hour is not None or end_hour is not None
        tz = _case_timezone(db, case_id) if needs_tz else None
        if weekday is not None:
            conditions.append("EXTRACT(DOW FROM ts AT TIME ZONE :tz)::int = :weekday")
            bind["tz"] = tz
            bind["weekday"] = weekday
        if start_hour is not None or end_hour is not None:
            bind["tz"] = tz
            local_hour = "(EXTRACT(HOUR FROM ts AT TIME ZONE :tz) + EXTRACT(MINUTE FROM ts AT TIME ZONE :tz) / 60.0)"
            if start_hour is not None:
                conditions.append(f"{local_hour} >= :start_hour")
                bind["start_hour"] = start_hour
            if end_hour is not None:
                conditions.append(f"{local_hour} <= :end_hour")
                bind["end_hour"] = end_hour

        where = " AND ".join(conditions)

        rows = db.execute(
            text(f"""
                SELECT id, ts, summary, meta,
                       ST_Y(geo::geometry) as lat,
                       ST_X(geo::geometry) as lon
                FROM events
                WHERE {where}
                ORDER BY ts ASC
            """),
            bind,
        ).fetchall()

        return [
            GeoEvent(
                id=str(r[0]),
                ts=r[1].isoformat() if r[1] else None,
                summary=r[2],
                lat=float(r[4]),
                lon=float(r[5]),
                meta=r[3] if isinstance(r[3], dict) else {},
            )
            for r in rows
        ]
