"""SOKOL API — Playbooks for forensic investigation workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory
from .reports import generate_html_laudo

router = APIRouter(prefix="/playbooks", tags=["playbooks"])


# ── Models ─────────────────────────────────────────────────────────────────
class PlaybookStep(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    action: str  # 'search', 'filter', 'analyze', 'export', 'notify'
    params: dict[str, Any] = {}
    depends_on: list[str] = []  # step IDs this depends on
    auto: bool = False  # auto-execute or manual


class PlaybookCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: str = "general"  # general, financial, communication, location
    steps: list[PlaybookStep]
    is_template: bool = False


class Playbook(BaseModel):
    id: str
    name: str
    description: Optional[str]
    category: str
    steps: list[PlaybookStep]
    is_template: bool
    created_by: str
    created_at: datetime


class PlaybookExecution(BaseModel):
    id: str
    playbook_id: str
    case_id: str
    status: str  # pending, running, completed, failed
    current_step: Optional[str]
    results: dict = {}
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_by: str


class PlaybookResult(BaseModel):
    execution_id: str
    step_id: str
    status: str
    output: Any = None
    error: Optional[str] = None
    timestamp: datetime


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=Playbook)
def create_playbook(body: PlaybookCreate, user_id: str = "system"):
    """Create a new playbook."""
    factory = get_session_factory()
    with factory() as db:
        playbook_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO playbooks (id, name, description, category, steps, is_template, created_by)
                VALUES (:id, :name, :description, :category, :steps, :is_template, :created_by)
            """),
            {
                "id": playbook_id,
                "name": body.name,
                "description": body.description,
                "category": body.category,
                "steps": json.dumps([s.model_dump() for s in body.steps]),
                "is_template": body.is_template,
                "created_by": user_id,
            },
        )
        db.commit()

        row = (
            db.execute(
                text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
            )
            .mappings()
            .fetchone()
        )
        return Playbook(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            category=row["category"],
            steps=[PlaybookStep(**s) for s in json.loads(row["steps"])],
            is_template=row["is_template"],
            created_by=str(row["created_by"]),
            created_at=row["created_at"],
        )


@router.get("/", response_model=list[Playbook])
def list_playbooks(category: Optional[str] = None, templates_only: bool = False):
    """List playbooks."""
    factory = get_session_factory()
    with factory() as db:
        query = "SELECT * FROM playbooks WHERE 1=1"
        params = {}

        if category:
            query += " AND category = :category"
            params["category"] = category
        if templates_only:
            query += " AND is_template = true"

        query += " ORDER BY created_at DESC"

        rows = db.execute(text(query), params).fetchall()
        result = []
        for r in rows:
            row_dict = dict(r._mapping)
            steps_raw = row_dict["steps"]
            # Handle both JSONB (list) and text (string) formats
            if isinstance(steps_raw, str):
                steps_list = json.loads(steps_raw)
            else:
                steps_list = steps_raw
            result.append(
                Playbook(
                    id=str(row_dict["id"]),
                    name=row_dict["name"],
                    description=row_dict["description"],
                    category=row_dict["category"],
                    steps=[PlaybookStep(**s) for s in steps_list],
                    is_template=row_dict["is_template"],
                    created_by=str(row_dict["created_by"]),
                    created_at=row_dict["created_at"],
                )
            )
        return result


@router.get("/{playbook_id}", response_model=Playbook)
def get_playbook(playbook_id: str):
    """Get playbook details."""
    factory = get_session_factory()
    with factory() as db:
        row = (
            db.execute(
                text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
            )
            .mappings()
            .fetchone()
        )
        if not row:
            raise HTTPException(status_code=404, detail="Playbook not found")

        return Playbook(
            id=str(row["id"]),
            name=row["name"],
            description=row["description"],
            category=row["category"],
            steps=[PlaybookStep(**s) for s in json.loads(row["steps"])],
            is_template=row["is_template"],
            created_by=str(row["created_by"]),
            created_at=row["created_at"],
        )


@router.post("/{playbook_id}/execute", response_model=PlaybookExecution)
def execute_playbook(playbook_id: str, case_id: str):
    """Start playbook execution for a case — runs all steps synchronously."""
    factory = get_session_factory()
    with factory() as db:
        admin_user = (
            db.execute(text("SELECT id FROM users LIMIT 1")).mappings().fetchone()
        )
        user_id = (
            str(admin_user["id"])
            if admin_user
            else "00000000-0000-0000-0000-000000000000"
        )

        playbook = (
            db.execute(
                text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
            )
            .mappings()
            .fetchone()
        )
        if not playbook:
            raise HTTPException(status_code=404, detail="Playbook not found")

        case = (
            db.execute(text("SELECT id FROM cases WHERE id = :id"), {"id": case_id})
            .mappings()
            .fetchone()
        )
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        execution_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]
        db.execute(
            text("""
                INSERT INTO playbook_executions (id, playbook_id, case_id, status, current_step, created_by)
                VALUES (:id, :playbook_id, :case_id, 'running', 'starting', :created_by)
            """),
            {
                "id": execution_id,
                "playbook_id": playbook_id,
                "case_id": case_id,
                "created_by": user_id,
            },
        )
        db.commit()

        steps_raw = playbook["steps"]
        steps = steps_raw if isinstance(steps_raw, list) else json.loads(steps_raw)
        results = {}

        for step in steps:
            step_id = step["id"]
            step_name = step.get("name", step_id)
            action = step.get("action", "noop")
            params = step.get("params", {})

            db.execute(
                text("""
                    UPDATE playbook_executions
                    SET current_step = :step_name
                    WHERE id = :eid
                """),
                {"step_name": f"{step_name} ({action})", "eid": execution_id},
            )
            db.commit()

            try:
                output = _execute_step(db, case_id, action, params, user_id=user_id)
                results[step_id] = {"status": "ok", "output": output}
                db.execute(
                    text("""
                        INSERT INTO playbook_results (id, execution_id, step_id, status, output)
                        VALUES (gen_random_uuid(), :eid, :sid, 'ok', CAST(:output AS jsonb))
                    """),
                    {"eid": execution_id, "sid": step_id, "output": json.dumps(output)},
                )
            except Exception as e:
                db.rollback()
                results[step_id] = {"status": "error", "error": str(e)}
                db.execute(
                    text("""
                        INSERT INTO playbook_results (id, execution_id, step_id, status, error)
                        VALUES (gen_random_uuid(), :eid, :sid, 'error', :error)
                    """),
                    {"eid": execution_id, "sid": step_id, "error": str(e)},
                )
            db.commit()

        db.execute(
            text("""
                UPDATE playbook_executions
                SET status = 'completed', current_step = NULL, results = CAST(:results AS jsonb),
                    completed_at = now()
                WHERE id = :eid
            """),
            {"results": json.dumps(results), "eid": execution_id},
        )
        db.commit()

        row = (
            db.execute(
                text("SELECT * FROM playbook_executions WHERE id = :id"),
                {"id": execution_id},
            )
            .mappings()
            .fetchone()
        )

        return PlaybookExecution(
            id=str(row["id"]),
            playbook_id=playbook_id,
            case_id=case_id,
            status="completed",
            current_step=None,
            results=results,
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            created_by=user_id,
        )


def _safe_dict(row) -> dict:
    d = dict(row._mapping)
    out = {}
    for k, v in d.items():
        if hasattr(v, "isoformat"):
            out[k] = str(v)
        elif hasattr(v, "hex"):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def _execute_step(db, case_id: str, action: str, params: dict, user_id: str | None = None) -> dict:
    """Execute a single playbook step and return its output."""
    if action == "extract_contacts":
        rows = db.execute(
            text("""
                SELECT DISTINCT kind, value, display_name, COUNT(*) as count
                FROM entities WHERE case_id = :cid
                GROUP BY kind, value, display_name
                ORDER BY count DESC LIMIT 50
            """),
            {"cid": case_id},
        ).fetchall()
        return {"contacts": [_safe_dict(r) for r in rows], "count": len(rows)}

    elif action == "map_communications":
        rows = db.execute(
            text("""
                SELECT actor, counterpart, kind, COUNT(*) as count, MIN(ts) as first, MAX(ts) as last
                FROM events WHERE case_id = :cid AND kind IN ('message', 'call')
                GROUP BY actor, counterpart, kind ORDER BY count DESC LIMIT 50
            """),
            {"cid": case_id},
        ).fetchall()
        return {"communications": [_safe_dict(r) for r in rows], "count": len(rows)}

    elif action == "analyze_patterns":
        rows = db.execute(
            text("""
                SELECT kind, COUNT(*) as count
                FROM events WHERE case_id = :cid
                GROUP BY kind ORDER BY count DESC
            """),
            {"cid": case_id},
        ).fetchall()
        return {"patterns": [_safe_dict(r) for r in rows]}

    elif action == "extract_timeline":
        rows = db.execute(
            text("""
                SELECT id, kind, ts, summary
                FROM events WHERE case_id = :cid
                ORDER BY ts LIMIT 200
            """),
            {"cid": case_id},
        ).fetchall()
        return {"events": [_safe_dict(r) for r in rows], "count": len(rows)}

    elif action == "detect_peaks":
        rows = db.execute(
            text("""
                SELECT date_trunc('hour', ts) as hour, COUNT(*) as count
                FROM events WHERE case_id = :cid
                GROUP BY hour ORDER BY count DESC LIMIT 10
            """),
            {"cid": case_id},
        ).fetchall()
        return {"peak_hours": [_safe_dict(r) for r in rows]}

    elif action == "generate_report":
        title = str(params.get("title") or "Laudo do playbook")
        uid_raw = user_id or db.execute(text("SELECT id FROM users LIMIT 1")).scalar()
        if not uid_raw:
            return {"message": "Não há usuário para gerar o laudo"}
        resp = generate_html_laudo(db, UUID(str(case_id)), UUID(str(uid_raw)), title)
        return {
            "report_id": resp.report_id,
            "status": resp.status,
            "title": title,
            "message": "Laudo HTML gerado — abra a aba Relatórios",
        }

    elif action == "search_mentions":
        term = params.get(
            "term", params.get("names", [""])[0] if params.get("names") else ""
        )
        if not term:
            return {
                "message": "No search term defined — pass params.term or params.names"
            }
        rows = db.execute(
            text("""
                SELECT id, kind, ts, summary
                FROM events WHERE case_id = :cid AND summary ILIKE :q
                LIMIT 50
            """),
            {"cid": case_id, "q": f"%{term}%"},
        ).fetchall()
        return {
            "matches": [_safe_dict(r) for r in rows],
            "count": len(rows),
            "term": term,
        }

    elif action == "define_names":
        return {
            "message": "Manual step — define names before proceeding",
            "names": params.get("names", []),
        }

    elif action == "context_analysis":
        return {"message": "Manual step — review results from previous steps"}

    elif action == "search_entity":
        entity = params.get("entity", "")
        rows = db.execute(
            text("""
                SELECT id, kind, ts, summary
                FROM events WHERE case_id = :cid AND (summary ILIKE :q OR actor ILIKE :q OR counterpart ILIKE :q)
                LIMIT 50
            """),
            {"cid": case_id, "q": f"%{entity}%"},
        ).fetchall()
        return {
            "matches": [_safe_dict(r) for r in rows],
            "count": len(rows),
            "entity": entity,
        }

    elif action == "extract_locations":
        rows = db.execute(
            text("""
                SELECT e.id, e.ts, e.summary,
                       ST_Y(e.geo::geometry) AS lat,
                       ST_X(e.geo::geometry) AS lon,
                       e.meta
                FROM events e
                WHERE e.case_id = :cid
                  AND e.geo IS NOT NULL
                ORDER BY e.ts
                LIMIT 500
            """),
            {"cid": case_id},
        ).fetchall()
        return {"locations": [_safe_dict(r) for r in rows], "count": len(rows)}

    elif action == "activity_heatmap":
        # Hour-of-day × day-of-week using case timezone
        tz = params.get("timezone", "America/Sao_Paulo")
        rows = db.execute(
            text("""
                SELECT
                    EXTRACT(DOW FROM ts AT TIME ZONE :tz)::int AS dow,
                    EXTRACT(HOUR FROM ts AT TIME ZONE :tz)::int AS hour,
                    COUNT(*) AS count
                FROM events
                WHERE case_id = :cid AND ts IS NOT NULL
                GROUP BY dow, hour
                ORDER BY dow, hour
            """),
            {"cid": case_id, "tz": tz},
        ).fetchall()
        cells = [{"dow": r[0], "hour": r[1], "count": r[2]} for r in rows]
        total = sum(r[2] for r in rows)
        peak = max(cells, key=lambda x: x["count"]) if cells else {}
        return {"heatmap": cells, "total_events": total, "peak_cell": peak}

    else:
        return {"message": f"Unknown action: {action}", "params": params}


@router.get("/executions/{case_id}", response_model=list[PlaybookExecution])
def list_executions(case_id: str, limit: int = Query(20, ge=1, le=100)):
    """List playbook executions for a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT pe.*, p.name as playbook_name
                FROM playbook_executions pe
                JOIN playbooks p ON pe.playbook_id = p.id
                WHERE pe.case_id = :case_id
                ORDER BY pe.created_at DESC
                LIMIT :limit
            """),
            {"case_id": case_id, "limit": limit},
        ).fetchall()
        result = []
        for r in rows:
            row_dict = dict(r._mapping)
            result.append(
                PlaybookExecution(
                    id=str(row_dict["id"]),
                    playbook_id=str(row_dict["playbook_id"]),
                    case_id=str(row_dict["case_id"]),
                    status=row_dict["status"],
                    current_step=row_dict["current_step"],
                    results=json.loads(row_dict["results"])
                    if row_dict["results"]
                    else {},
                    started_at=row_dict["started_at"],
                    completed_at=row_dict["completed_at"],
                    created_by=str(row_dict["created_by"]),
                )
            )
        return result


@router.get("/executions/{execution_id}/results", response_model=list[PlaybookResult])
def get_execution_results(execution_id: str):
    """Get results of playbook execution."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT * FROM playbook_results
                WHERE execution_id = :execution_id
                ORDER BY timestamp
            """),
            {"execution_id": execution_id},
        ).fetchall()
        result = []
        for r in rows:
            row_dict = dict(r._mapping)
            result.append(
                PlaybookResult(
                    execution_id=str(row_dict["execution_id"]),
                    step_id=row_dict["step_id"],
                    status=row_dict["status"],
                    output=json.loads(row_dict["output"])
                    if row_dict["output"]
                    else None,
                    error=row_dict["error"],
                    timestamp=row_dict["timestamp"],
                )
            )
        return result


# ── Built-in Playbook Templates ──────────────────────────────────────────
BUILTIN_TEMPLATES = [
    {
        "name": "Padrão de Comunicação",
        "description": "Quem falou com quem: volume por contato, horários típicos, apps usados e gaps de silêncio",
        "category": "communication",
        "steps": [
            PlaybookStep(
                id="1",
                name="Mapear comunicações",
                description="Top contatos por volume de mensagens e chamadas",
                action="map_communications",
                auto=True,
            ),
            PlaybookStep(
                id="2",
                name="Identificar horários típicos",
                description="Picos de atividade por hora do dia",
                action="detect_peaks",
                depends_on=["1"],
                auto=True,
            ),
            PlaybookStep(
                id="3",
                name="Distribuição por canal",
                description="Quais apps/tipos de evento dominam",
                action="analyze_patterns",
                depends_on=["2"],
                auto=True,
            ),
            PlaybookStep(
                id="4",
                name="Relatório de padrão",
                action="generate_report",
                depends_on=["3"],
                auto=False,
            ),
        ],
    },
    {
        "name": "Rastreamento de Localização",
        "description": "Sequência de localizações, distância percorrida e locais recorrentes",
        "category": "location",
        "steps": [
            PlaybookStep(
                id="1",
                name="Extrair pontos GPS",
                description="Todos os eventos com coordenadas geográficas",
                action="extract_locations",
                auto=True,
            ),
            PlaybookStep(
                id="2",
                name="Picos de deslocamento",
                description="Horas com maior concentração de movimentação",
                action="detect_peaks",
                depends_on=["1"],
                auto=True,
            ),
            PlaybookStep(
                id="3",
                name="Relatório de localização",
                action="generate_report",
                depends_on=["2"],
                auto=False,
            ),
        ],
    },
    {
        "name": "Análise de Contatos",
        "description": "Analisa todos os contatos e comunicações do caso",
        "category": "communication",
        "steps": [
            PlaybookStep(
                id="1", name="Extrair contatos", action="extract_contacts", auto=True
            ),
            PlaybookStep(
                id="2",
                name="Mapear comunicações",
                action="map_communications",
                depends_on=["1"],
                auto=True,
            ),
            PlaybookStep(
                id="3",
                name="Identificar padrões",
                action="analyze_patterns",
                depends_on=["2"],
                auto=False,
            ),
        ],
    },
    {
        "name": "Análise Temporal",
        "description": "Analisa atividade ao longo do tempo",
        "category": "general",
        "steps": [
            PlaybookStep(
                id="1", name="Extrair timeline", action="extract_timeline", auto=True
            ),
            PlaybookStep(
                id="2",
                name="Identificar picos",
                action="detect_peaks",
                depends_on=["1"],
                auto=True,
            ),
            PlaybookStep(
                id="3",
                name="Gerar relatório",
                action="generate_report",
                depends_on=["2"],
                auto=False,
            ),
        ],
    },
    {
        "name": "Busca de Pessoas",
        "description": "Busca menções a pessoas específicas",
        "category": "general",
        "steps": [
            PlaybookStep(
                id="1", name="Definir nomes", action="define_names", auto=False
            ),
            PlaybookStep(
                id="2",
                name="Buscar menções",
                action="search_mentions",
                depends_on=["1"],
                auto=True,
            ),
            PlaybookStep(
                id="3",
                name="Análise de contexto",
                action="context_analysis",
                depends_on=["2"],
                auto=False,
            ),
        ],
    },
]


@router.post("/templates/init")
def init_builtin_templates(user_id: str = "00000000-0000-0000-0000-000000000001"):
    """Initialize built-in playbook templates."""
    factory = get_session_factory()
    created = 0

    with factory() as db:
        for template in BUILTIN_TEMPLATES:
            # Check if exists
            existing = db.execute(
                text(
                    "SELECT id FROM playbooks WHERE name = :name AND is_template = true"
                ),
                {"name": template["name"]},
            ).fetchone()

            if not existing:
                playbook_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]
                db.execute(
                    text("""
                        INSERT INTO playbooks (id, name, description, category, steps, is_template, created_by)
                        VALUES (:id, :name, :description, :category, :steps, true, :created_by)
                    """),
                    {
                        "id": playbook_id,
                        "name": template["name"],
                        "description": template["description"],
                        "category": template["category"],
                        "steps": json.dumps(
                            [s.model_dump() for s in template["steps"]]
                        ),
                        "created_by": user_id,
                    },
                )
                created += 1

        db.commit()

    return {"created": created, "total": len(BUILTIN_TEMPLATES)}
