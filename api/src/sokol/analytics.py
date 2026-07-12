"""SOKOL API — forensic analytics: activity/location heatmaps, contact frequency."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .cache import cache_get, cache_set
from .db import get_session_factory

router = APIRouter(prefix="/analytics", tags=["analytics"])

_CACHE_TTL = 300  # seconds


def _case_timezone(db, case_id: UUID) -> str:
    row = db.execute(
        text("SELECT reference_timezone FROM cases WHERE id = :cid"),
        {"cid": case_id},
    ).fetchone()
    return row[0] if row and row[0] else "America/Sao_Paulo"


# ── Models ─────────────────────────────────────────────────────────────────

class HeatmapCell(BaseModel):
    dow: int  # 0=domingo … 6=sábado (Postgres DOW)
    hour: int
    count: int


class ActivityHeatmap(BaseModel):
    case_id: str
    timezone: str
    cells: list[HeatmapCell]
    total_events: int


class LocationCell(BaseModel):
    lat: float
    lon: float
    count: int


class LocationHeatmap(BaseModel):
    case_id: str
    points: list[LocationCell]
    total: int


class MonthCount(BaseModel):
    month: str  # YYYY-MM
    count: int


class ContactFrequency(BaseModel):
    counterpart: str
    total: int
    kinds: dict[str, int]
    monthly: list[MonthCount]


class ContactFrequencyResponse(BaseModel):
    case_id: str
    contacts: list[ContactFrequency]


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/{case_id}/activity-heatmap", response_model=ActivityHeatmap)
def activity_heatmap(
    case_id: UUID,
    kind: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """7×24 matrix (day-of-week × hour) in the case's reference timezone."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        cache_key = f"sokol:analytics:{case_id}:activity:{kind or 'all'}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        tz = _case_timezone(db, case_id)

        conditions = ["case_id = :cid", "ts IS NOT NULL"]
        bind: dict = {"cid": case_id, "tz": tz}
        if kind:
            conditions.append("kind = :kind")
            bind["kind"] = kind
        where = " AND ".join(conditions)

        rows = db.execute(
            text(f"""
                SELECT
                    EXTRACT(DOW FROM ts AT TIME ZONE :tz)::int AS dow,
                    EXTRACT(HOUR FROM ts AT TIME ZONE :tz)::int AS hour,
                    COUNT(*) AS count
                FROM events
                WHERE {where}
                GROUP BY 1, 2
                ORDER BY 1, 2
            """),
            bind,
        ).fetchall()

    cells = [HeatmapCell(dow=r[0], hour=r[1], count=r[2]) for r in rows]
    result = ActivityHeatmap(
        case_id=str(case_id),
        timezone=tz,
        cells=cells,
        total_events=sum(c.count for c in cells),
    )
    cache_set(cache_key, result.model_dump(), _CACHE_TTL)
    return result


@router.get("/{case_id}/location-heatmap", response_model=LocationHeatmap)
def location_heatmap(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    """Location events aggregated on a ~110 m grid (lat/lon rounded to 3 decimals)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        cache_key = f"sokol:analytics:{case_id}:location"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        rows = db.execute(
            text("""
                SELECT
                    ROUND(ST_Y(geo::geometry)::numeric, 3) AS lat,
                    ROUND(ST_X(geo::geometry)::numeric, 3) AS lon,
                    COUNT(*) AS count
                FROM events
                WHERE case_id = :cid AND geo IS NOT NULL
                GROUP BY 1, 2
                ORDER BY count DESC
                LIMIT 2000
            """),
            {"cid": case_id},
        ).fetchall()

    points = [LocationCell(lat=float(r[0]), lon=float(r[1]), count=r[2]) for r in rows]
    result = LocationHeatmap(
        case_id=str(case_id),
        points=points,
        total=sum(p.count for p in points),
    )
    cache_set(cache_key, result.model_dump(), _CACHE_TTL)
    return result


@router.get("/{case_id}/contact-frequency", response_model=ContactFrequencyResponse)
def contact_frequency(
    case_id: UUID,
    top: int = Query(15, ge=1, le=50),
    user: CurrentUser = Depends(get_current_user),
):
    """Top counterparts by message/call volume, with a monthly series each."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        cache_key = f"sokol:analytics:{case_id}:contacts:{top}"
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        top_rows = db.execute(
            text("""
                SELECT counterpart, kind, COUNT(*) AS count
                FROM events
                WHERE case_id = :cid
                  AND kind IN ('message', 'call')
                  AND counterpart IS NOT NULL AND counterpart != ''
                GROUP BY counterpart, kind
            """),
            {"cid": case_id},
        ).fetchall()

        # Aggregate kinds per counterpart, pick top N by total
        agg: dict[str, dict[str, int]] = {}
        for cp, kind, count in top_rows:
            agg.setdefault(cp, {})[kind] = count
        ranked = sorted(agg.items(), key=lambda kv: -sum(kv[1].values()))[:top]
        top_cps = [cp for cp, _ in ranked]

        monthly_map: dict[str, list[MonthCount]] = {cp: [] for cp in top_cps}
        if top_cps:
            tz = _case_timezone(db, case_id)
            month_rows = db.execute(
                text("""
                    SELECT counterpart,
                           to_char(ts AT TIME ZONE :tz, 'YYYY-MM') AS month,
                           COUNT(*) AS count
                    FROM events
                    WHERE case_id = :cid
                      AND kind IN ('message', 'call')
                      AND counterpart = ANY(:cps)
                      AND ts IS NOT NULL
                    GROUP BY 1, 2
                    ORDER BY 1, 2
                """),
                {"cid": case_id, "cps": top_cps, "tz": tz},
            ).fetchall()
            for cp, month, count in month_rows:
                monthly_map[cp].append(MonthCount(month=month, count=count))

    contacts = [
        ContactFrequency(
            counterpart=cp,
            total=sum(kinds.values()),
            kinds=kinds,
            monthly=monthly_map.get(cp, []),
        )
        for cp, kinds in ranked
    ]
    result = ContactFrequencyResponse(case_id=str(case_id), contacts=contacts)
    cache_set(cache_key, result.model_dump(), _CACHE_TTL)
    return result
