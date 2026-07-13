"""SOKOL API — deterministic timeline anomaly detection.

Every anomaly is an Indicator (ADR-0004): carries score + explanation,
never asserted as fact. Rules run on demand (POST analyze) and persist
to the anomalies table; GET reads persisted results.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .audit import append_audit
from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

_SEVERITY = {
    "impossible_jump": "high",
    "burst_contact": "medium",
    "odd_hours": "medium",
    "silence_gap": "low",
}


class Anomaly(BaseModel):
    id: str
    case_id: str
    kind: str
    severity: str
    score: float
    explanation: str
    ref_event_ids: list[str]
    dismissed: bool
    created_at: str
    indicator_note: str = (
        "Indício automático (Indicator) — não é fato confirmado; valide antes de usar em laudo."
    )


class AnalyzeResponse(BaseModel):
    case_id: str
    created: int
    by_kind: dict[str, int]


def _case_timezone(db, case_id: UUID) -> str:
    row = db.execute(
        text("SELECT reference_timezone FROM cases WHERE id = :cid"),
        {"cid": case_id},
    ).fetchone()
    return row[0] if row and row[0] else "America/Sao_Paulo"


# ── Rules ──────────────────────────────────────────────────────────────────

def _rule_impossible_jump(db, case_id: UUID) -> list[dict]:
    """Consecutive location events implying speed > 150 km/h."""
    rows = db.execute(
        text("""
            WITH ordered AS (
                SELECT id, ts, geo,
                       LAG(id) OVER (ORDER BY ts) AS prev_id,
                       LAG(ts) OVER (ORDER BY ts) AS prev_ts,
                       LAG(geo) OVER (ORDER BY ts) AS prev_geo
                FROM events
                WHERE case_id = :cid AND kind = 'location'
                  AND ts IS NOT NULL AND geo IS NOT NULL
            )
            SELECT id, prev_id, ts, prev_ts,
                   ST_DistanceSphere(geo::geometry, prev_geo::geometry) AS dist_m,
                   EXTRACT(EPOCH FROM (ts - prev_ts)) AS dt_s
            FROM ordered
            WHERE prev_id IS NOT NULL
              AND EXTRACT(EPOCH FROM (ts - prev_ts)) > 0
              AND (ST_DistanceSphere(geo::geometry, prev_geo::geometry) / 1000.0)
                  / (EXTRACT(EPOCH FROM (ts - prev_ts)) / 3600.0) > 150
        """),
        {"cid": case_id},
    ).fetchall()

    out = []
    for r in rows:
        dist_m, dt_s = float(r[4]), float(r[5])
        speed_kmh = (dist_m / 1000.0) / (dt_s / 3600.0)
        km = dist_m / 1000.0
        minutes = dt_s / 60.0
        out.append(
            {
                "kind": "impossible_jump",
                "score": min(1.0, speed_kmh / 1000.0 + 0.5),
                "explanation": (
                    f"Salto de {km:.1f} km em {minutes:.0f} min "
                    f"(velocidade implícita {speed_kmh:.0f} km/h) entre dois eventos de localização."
                ),
                "ref_event_ids": [str(r[1]), str(r[0])],
            }
        )
    return out


def _rule_odd_hours(db, case_id: UUID, tz: str) -> list[dict]:
    """Days where 02h–05h activity exceeds 3× the case's average for that window."""
    rows = db.execute(
        text("""
            SELECT (ts AT TIME ZONE :tz)::date AS day,
                   COUNT(*) AS night_count,
                   array_agg(id) AS ids
            FROM events
            WHERE case_id = :cid AND ts IS NOT NULL
              AND EXTRACT(HOUR FROM ts AT TIME ZONE :tz) BETWEEN 2 AND 4
            GROUP BY 1
        """),
        {"cid": case_id, "tz": tz},
    ).fetchall()
    if not rows:
        return []

    avg = sum(r[1] for r in rows) / len(rows)
    out = []
    for day, count, ids in rows:
        if avg > 0 and count > 3 * avg and count >= 5:
            out.append(
                {
                    "kind": "odd_hours",
                    "score": min(1.0, count / (3 * avg) / 3),
                    "explanation": (
                        f"{count} eventos entre 02h e 05h em {day.strftime('%d/%m/%Y')} "
                        f"(média do caso nessa janela: {avg:.1f}/dia) — fuso {tz}."
                    ),
                    "ref_event_ids": [str(i) for i in ids[:50]],
                }
            )
    return out


def _rule_burst_contact(db, case_id: UUID) -> list[dict]:
    """New counterpart with > 20 messages within the first 24 h of contact."""
    rows = db.execute(
        text("""
            WITH firsts AS (
                SELECT counterpart, MIN(ts) AS first_ts
                FROM events
                WHERE case_id = :cid AND kind = 'message'
                  AND counterpart IS NOT NULL AND counterpart != '' AND ts IS NOT NULL
                GROUP BY counterpart
            )
            SELECT e.counterpart, COUNT(*) AS n, f.first_ts, array_agg(e.id) AS ids
            FROM events e
            JOIN firsts f ON f.counterpart = e.counterpart
            WHERE e.case_id = :cid AND e.kind = 'message'
              AND e.ts >= f.first_ts AND e.ts < f.first_ts + interval '24 hours'
            GROUP BY e.counterpart, f.first_ts
            HAVING COUNT(*) > 20
        """),
        {"cid": case_id},
    ).fetchall()

    out = []
    for cp, n, first_ts, ids in rows:
        out.append(
            {
                "kind": "burst_contact",
                "score": min(1.0, n / 100.0 + 0.4),
                "explanation": (
                    f"Contato-relâmpago: {n} mensagens com '{cp}' nas primeiras 24 h "
                    f"de contato (início {first_ts.strftime('%d/%m/%Y %H:%M')})."
                ),
                "ref_event_ids": [str(i) for i in ids[:50]],
            }
        )
    return out


def _rule_silence_gap(db, case_id: UUID) -> list[dict]:
    """Gaps > 48 h in a case that otherwise averages daily activity."""
    stats = db.execute(
        text("""
            SELECT COUNT(*)::float / GREATEST(1, (MAX(ts)::date - MIN(ts)::date + 1)) AS per_day
            FROM events WHERE case_id = :cid AND ts IS NOT NULL
        """),
        {"cid": case_id},
    ).fetchone()
    if not stats or not stats[0] or stats[0] < 5:
        return []  # case without steady daily activity — gaps are expected

    rows = db.execute(
        text("""
            WITH ordered AS (
                SELECT id, ts, LAG(id) OVER (ORDER BY ts) AS prev_id,
                       LAG(ts) OVER (ORDER BY ts) AS prev_ts
                FROM events
                WHERE case_id = :cid AND ts IS NOT NULL
            )
            SELECT prev_id, id, prev_ts, ts,
                   EXTRACT(EPOCH FROM (ts - prev_ts)) / 3600.0 AS gap_h
            FROM ordered
            WHERE prev_ts IS NOT NULL
              AND ts - prev_ts > interval '48 hours'
            ORDER BY gap_h DESC
            LIMIT 20
        """),
        {"cid": case_id},
    ).fetchall()

    out = []
    for prev_id, ev_id, prev_ts, ts, gap_h in rows:
        gap_h = float(gap_h)
        out.append(
            {
                "kind": "silence_gap",
                "score": min(1.0, gap_h / 336.0 + 0.2),
                "explanation": (
                    f"Silêncio anômalo de {gap_h / 24.0:.1f} dias "
                    f"({prev_ts.strftime('%d/%m/%Y %H:%M')} → {ts.strftime('%d/%m/%Y %H:%M')}) "
                    f"num caso com média de {stats[0]:.0f} eventos/dia."
                ),
                "ref_event_ids": [str(prev_id), str(ev_id)],
            }
        )
    return out


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.post("/{case_id}/analyze", response_model=AnalyzeResponse)
def analyze(case_id: UUID, user: CurrentUser = Depends(get_current_user)):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id, roles=["admin", "analista"])
        tz = _case_timezone(db, case_id)

        candidates: list[dict] = []
        candidates += _rule_impossible_jump(db, case_id)
        candidates += _rule_odd_hours(db, case_id, tz)
        candidates += _rule_burst_contact(db, case_id)
        candidates += _rule_silence_gap(db, case_id)

        # Dedup: same kind + same ref_event_ids already stored (dismissed or not)
        existing = db.execute(
            text("SELECT kind, ref_event_ids FROM anomalies WHERE case_id = :cid"),
            {"cid": case_id},
        ).fetchall()
        seen = {(r[0], tuple(str(x) for x in (r[1] or []))) for r in existing}

        created = 0
        by_kind: dict[str, int] = {}
        for c in candidates:
            sig = (c["kind"], tuple(c["ref_event_ids"]))
            if sig in seen:
                continue
            db.execute(
                text("""
                    INSERT INTO anomalies (case_id, kind, severity, score, explanation, ref_event_ids)
                    VALUES (:cid, :kind, :sev, :score, :expl, CAST(:refs AS uuid[]))
                """),
                {
                    "cid": case_id,
                    "kind": c["kind"],
                    "sev": _SEVERITY[c["kind"]],
                    "score": round(c["score"], 3),
                    "expl": c["explanation"],
                    "refs": c["ref_event_ids"],
                },
            )
            seen.add(sig)
            created += 1
            by_kind[c["kind"]] = by_kind.get(c["kind"], 0) + 1

        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="anomalies.analyze",
            payload={"created": created, "by_kind": by_kind},
        )
        db.commit()

    return AnalyzeResponse(case_id=str(case_id), created=created, by_kind=by_kind)


@router.get("/{case_id}", response_model=list[Anomaly])
def list_anomalies(
    case_id: UUID,
    dismissed: bool | None = Query(False),
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        conditions = ["case_id = :cid"]
        bind: dict = {"cid": case_id}
        if dismissed is not None:
            conditions.append("dismissed = :dis")
            bind["dis"] = dismissed

        rows = db.execute(
            text(f"""
                SELECT id, case_id, kind, severity, score, explanation,
                       ref_event_ids, dismissed, created_at
                FROM anomalies
                WHERE {" AND ".join(conditions)}
                ORDER BY CASE severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                         score DESC
                LIMIT 200
            """),
            bind,
        ).fetchall()

    return [
        Anomaly(
            id=str(r[0]),
            case_id=str(r[1]),
            kind=r[2],
            severity=r[3],
            score=r[4],
            explanation=r[5],
            ref_event_ids=[str(x) for x in (r[6] or [])],
            dismissed=r[7],
            created_at=str(r[8]),
        )
        for r in rows
    ]


@router.patch("/{anomaly_id}/dismiss")
def dismiss_anomaly(anomaly_id: UUID, user: CurrentUser = Depends(get_current_user)):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT case_id FROM anomalies WHERE id = :id"),
            {"id": anomaly_id},
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Anomaly not found")
        case_id = row[0]
        require_case_member(db, case_id, user.user_id, roles=["admin", "analista"])

        db.execute(
            text("UPDATE anomalies SET dismissed = true WHERE id = :id"),
            {"id": anomaly_id},
        )
        append_audit(
            db,
            case_id=case_id,
            actor_user_id=user.user_id,
            action="anomalies.dismiss",
            payload={"anomaly_id": str(anomaly_id)},
        )
        db.commit()

    return {"status": "dismissed"}
