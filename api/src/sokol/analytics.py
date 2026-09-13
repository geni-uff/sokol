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


WEEKDAY_LABELS = {
    0: "domingo",
    1: "segunda-feira",
    2: "terça-feira",
    3: "quarta-feira",
    4: "quinta-feira",
    5: "sexta-feira",
    6: "sábado",
}


class LocationPattern(BaseModel):
    grid_lat: float
    grid_lon: float
    weekday: int  # 0=domingo … 6=sábado (Postgres DOW convention)
    weekday_label: str
    start_hour: float
    end_hour: float
    occurrences: int
    distinct_weeks: int
    sample_address: str | None
    event_ids: list[str]


class LocationPatternsResponse(BaseModel):
    case_id: str
    timezone: str
    patterns: list[LocationPattern]


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


@router.get("/{case_id}/location-patterns", response_model=LocationPatternsResponse)
def location_patterns(
    case_id: UUID,
    min_weeks: int = Query(3, ge=2, le=52, description="Semanas distintas mínimas para considerar recorrente"),
    min_occurrences: int = Query(3, ge=2, le=200, description="Visitas mínimas nesse dia/lugar"),
    max_window_hours: float = Query(6.0, ge=0.5, le=24.0, description="Janela horária máxima para contar como padrão"),
    grid_precision: int = Query(3, ge=2, le=5, description="Casas decimais do grid espacial (3 ≈ 111 m)"),
    user: CurrentUser = Depends(get_current_user),
):
    """Detect recurring day-of-week + time-of-day location patterns.

    Groups location events into a coarse spatial grid (same ~111 m grid as
    `location-heatmap`), then within each grid cell looks for a weekday
    whose visit times cluster into a tight window repeated across several
    distinct calendar weeks — e.g. "toda segunda, das 10h ao meio-dia, o
    alvo fica no centro do Rio". This is an Indicator (ADR-0004): a
    correlation surfaced for human review, not an asserted fact.
    """
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        cache_key = (
            f"sokol:analytics:{case_id}:loc-patterns:"
            f"{min_weeks}:{min_occurrences}:{max_window_hours}:{grid_precision}"
        )
        cached = cache_get(cache_key)
        if cached is not None:
            return cached

        tz = _case_timezone(db, case_id)

        rows = db.execute(
            text(f"""
                SELECT
                    id,
                    ROUND(ST_Y(geo::geometry)::numeric, {grid_precision}) AS glat,
                    ROUND(ST_X(geo::geometry)::numeric, {grid_precision}) AS glon,
                    ts AT TIME ZONE :tz AS local_ts,
                    meta
                FROM events
                WHERE case_id = :cid
                  AND kind = 'location'
                  AND geo IS NOT NULL
                  AND ts IS NOT NULL
                ORDER BY local_ts
            """),
            {"cid": case_id, "tz": tz},
        ).fetchall()

    groups: dict[tuple[float, float, int], list] = {}
    for row_id, glat, glon, local_ts, meta in rows:
        weekday = (local_ts.weekday() + 1) % 7  # Postgres DOW: 0=domingo
        iso_year, iso_week, _ = local_ts.isocalendar()
        key = (float(glat), float(glon), weekday)
        groups.setdefault(key, []).append((row_id, local_ts, iso_year, iso_week, meta))

    patterns: list[LocationPattern] = []
    for (glat, glon, weekday), items in groups.items():
        distinct_weeks = {(y, w) for _, _, y, w, _ in items}
        if len(distinct_weeks) < min_weeks or len(items) < min_occurrences:
            continue

        hours = [t.hour + t.minute / 60 for _, t, _, _, _ in items]
        start_hour, end_hour = min(hours), max(hours)
        if end_hour - start_hour > max_window_hours:
            continue

        sample_address = next(
            (m.get("address") for *_, m in items if isinstance(m, dict) and m.get("address")),
            None,
        )
        patterns.append(
            LocationPattern(
                grid_lat=glat,
                grid_lon=glon,
                weekday=weekday,
                weekday_label=WEEKDAY_LABELS[weekday],
                start_hour=round(start_hour, 2),
                end_hour=round(end_hour, 2),
                occurrences=len(items),
                distinct_weeks=len(distinct_weeks),
                sample_address=sample_address,
                event_ids=[str(item[0]) for item in items],
            )
        )

    patterns.sort(key=lambda p: (-p.distinct_weeks, -p.occurrences))
    result = LocationPatternsResponse(case_id=str(case_id), timezone=tz, patterns=patterns[:50])
    cache_set(cache_key, result.model_dump(), _CACHE_TTL)
    return result
