"""SOKOL API — Playbooks for forensic investigation workflows."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

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

        row = db.execute(
            text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
        ).fetchone()
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
        row = db.execute(
            text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
        ).fetchone()
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
def execute_playbook(playbook_id: str, case_id: str, user_id: str = "system"):
    """Start playbook execution for a case."""
    factory = get_session_factory()
    with factory() as db:
        # Verify playbook exists
        playbook = db.execute(
            text("SELECT * FROM playbooks WHERE id = :id"), {"id": playbook_id}
        ).fetchone()
        if not playbook:
            raise HTTPException(status_code=404, detail="Playbook not found")

        # Verify case exists
        case = db.execute(
            text("SELECT id FROM cases WHERE id = :id"), {"id": case_id}
        ).fetchone()
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")

        execution_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO playbook_executions (id, playbook_id, case_id, status, created_by)
                VALUES (:id, :playbook_id, :case_id, 'pending', :created_by)
            """),
            {
                "id": execution_id,
                "playbook_id": playbook_id,
                "case_id": case_id,
                "created_by": user_id,
            },
        )
        db.commit()

        return PlaybookExecution(
            id=str(execution_id),
            playbook_id=playbook_id,
            case_id=case_id,
            status="pending",
            current_step=None,
            results={},
            started_at=None,
            completed_at=None,
            created_by=user_id,
        )


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
