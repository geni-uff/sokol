"""Cross-case analysis — admin-only, fully audited."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import text

from .audit import append_audit
from .auth import CurrentUser, get_current_user, require_case_member
from .cache import cache_delete, cache_get, cache_set
from .db import get_session_factory

router = APIRouter(prefix="/analysis", tags=["analysis"])

_CACHE_TTL = 300  # seconds


# ── Request / Response models ─────────────────────────────────────────

class CrossCaseRequest(BaseModel):
    case_ids: list[UUID]
    justification: str

    @field_validator("justification")
    @classmethod
    def justification_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("justification must not be empty")
        return v.strip()

    @field_validator("case_ids")
    @classmethod
    def at_least_two(cls, v: list[UUID]) -> list[UUID]:
        if len(v) < 2:
            raise ValueError("at least 2 case_ids required")
        return v


class SharedSelector(BaseModel):
    value: str
    cases: dict[str, int]       # case_id → count of occurrences
    confidence: float = 1.0     # always 1.0 for exact match; Indicator per ADR-0004


class SharedLocation(BaseModel):
    case_id_a: str
    case_id_b: str
    event_id_a: str
    event_id_b: str
    ts_a: str | None
    ts_b: str | None
    distance_m: float
    confidence: float = 0.9


class CrossCaseResult(BaseModel):
    case_ids: list[str]
    shared_phones: list[SharedSelector]
    shared_emails: list[SharedSelector]
    shared_locations: list[SharedLocation]
    similarity_score: float
    # Every result is an Indicator — never a Fact (ADR-0004)
    indicator_note: str = (
        "Estes resultados são indícios automáticos (Indicators), "
        "não fatos confirmados. Confirme manualmente antes de incluir em laudo."
    )


# ── Endpoint ──────────────────────────────────────────────────────────

@router.post("/cross-case", response_model=CrossCaseResult)
def cross_case_analysis(
    body: CrossCaseRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Compare multiple cases for shared phones, emails, and locations.
    Requires admin role in ALL supplied case_ids.
    Every call is recorded in the audit log.
    """
    factory = get_session_factory()
    case_id_strs = [str(c) for c in body.case_ids]

    # ── Auth: must be admin in every case ────────────────────────────
    with factory() as db:
        for cid in body.case_ids:
            try:
                require_case_member(db, cid, user.user_id, roles=["admin"])
            except HTTPException:
                raise HTTPException(
                    status_code=403,
                    detail=f"Admin role required in case {cid}",
                )

        # ── Audit (one record, global scope) ─────────────────────────
        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="cross_case_analysis",
            payload={
                "case_ids": case_id_strs,
                "justification": body.justification,
            },
        )
        db.commit()

    # ── Cache lookup ─────────────────────────────────────────────────
    cache_key = "sokol:cross-case:" + ":".join(sorted(case_id_strs))
    cached = cache_get(cache_key)
    if cached is not None:
        return CrossCaseResult(**cached)

    # ── Queries ──────────────────────────────────────────────────────
    with factory() as db:
        shared_phones = _shared_entities(db, body.case_ids, "phone")
        shared_emails = _shared_entities(db, body.case_ids, "email")
        shared_locations = _shared_locations(db, body.case_ids)

    # ── Similarity score: Jaccard on ALL phone+email selectors per case ──
    all_selectors: list[set[str]] = []
    with factory() as db:
        for cid in body.case_ids:
            rows = db.execute(
                text("""
                    SELECT kind, value FROM entities
                    WHERE case_id = :cid
                      AND kind IN ('phone', 'email')
                      AND value IS NOT NULL
                """),
                {"cid": cid},
            ).fetchall()
            all_selectors.append({f"{kind}:{value}" for kind, value in rows})

    if len(all_selectors) >= 2:
        union = set.union(*all_selectors)
        intersection = set.intersection(*all_selectors)
        similarity = len(intersection) / len(union) if union else 0.0
    else:
        similarity = 0.0

    result = CrossCaseResult(
        case_ids=case_id_strs,
        shared_phones=shared_phones,
        shared_emails=shared_emails,
        shared_locations=shared_locations,
        similarity_score=round(similarity, 4),
    )

    cache_set(cache_key, result.model_dump(), ttl_seconds=_CACHE_TTL)
    return result


# ── Query helpers ─────────────────────────────────────────────────────

def _shared_entities(
    db, case_ids: list[UUID], kind: str
) -> list[SharedSelector]:
    """Return entity values of `kind` that appear in 2+ of the given cases."""
    rows = db.execute(
        text("""
            SELECT value, case_id::text, COUNT(*) AS cnt
            FROM entities
            WHERE kind = :kind
              AND case_id::text = ANY(:cids)
              AND value IS NOT NULL
            GROUP BY value, case_id
        """),
        {"kind": kind, "cids": [str(c) for c in case_ids]},
    ).fetchall()

    # Group by value → {case_id: count}
    by_value: dict[str, dict[str, int]] = {}
    for value, case_id, cnt in rows:
        by_value.setdefault(value, {})[str(case_id)] = cnt

    return [
        SharedSelector(value=v, cases=cases_map)
        for v, cases_map in by_value.items()
        if len(cases_map) >= 2
    ]


def _shared_locations(
    db, case_ids: list[UUID], radius_m: float = 500.0
) -> list[SharedLocation]:
    """Return pairs of location events from different cases within radius_m."""
    if len(case_ids) < 2:
        return []

    rows = db.execute(
        text("""
            SELECT
                a.id::text, a.case_id::text, a.ts,
                b.id::text, b.case_id::text, b.ts,
                ST_Distance(a.geo::geography, b.geo::geography) AS dist_m
            FROM events a
            JOIN events b
              ON a.case_id::text < b.case_id::text
             AND b.case_id::text = ANY(:cids)
             AND b.kind = 'location'
             AND b.geo IS NOT NULL
            WHERE a.kind = 'location'
              AND a.geo IS NOT NULL
              AND a.case_id::text = ANY(:cids)
              AND ST_DWithin(a.geo::geography, b.geo::geography, :radius)
            LIMIT 200
        """),
        {"cids": [str(c) for c in case_ids], "radius": radius_m},
    ).fetchall()

    return [
        SharedLocation(
            case_id_a=str(r[1]),
            case_id_b=str(r[4]),
            event_id_a=str(r[0]),
            event_id_b=str(r[3]),
            ts_a=str(r[2]) if r[2] else None,
            ts_b=str(r[5]) if r[5] else None,
            distance_m=round(float(r[6]), 1),
        )
        for r in rows
    ]
