"""SOKOL API — Pendências (pending tasks/indicators)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/pendencias", tags=["pendencias"])


# ── Models ─────────────────────────────────────────────────────────────────
class PendenciaCreate(BaseModel):
    case_id: str
    title: str
    description: Optional[str] = None
    priority: str = "medium"  # low, medium, high, critical
    assigned_to: Optional[str] = None
    related_event_id: Optional[str] = None
    related_message_id: Optional[str] = None
    due_date: Optional[datetime] = None


class Pendencia(BaseModel):
    id: str
    case_id: str
    title: str
    description: Optional[str]
    priority: str
    status: str  # open, in_progress, resolved, dismissed
    assigned_to: Optional[str]
    related_event_id: Optional[str]
    related_message_id: Optional[str]
    due_date: Optional[datetime]
    created_by: str
    created_at: datetime
    resolved_at: Optional[datetime]


def _pendencia_from_row(row) -> Pendencia:
    data = dict(row)
    for key in ("id", "case_id", "related_event_id", "related_message_id", "created_by"):
        if data.get(key) is not None:
            data[key] = str(data[key])
    return Pendencia(**{k: data.get(k) for k in Pendencia.model_fields})


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.post("/", response_model=Pendencia)
def create_pendencia(body: PendenciaCreate, user_id: str = "system"):
    """Create a new pendência (pending task)."""
    factory = get_session_factory()
    with factory() as db:
        pendencia_id = db.execute(text("SELECT gen_random_uuid()")).fetchone()[0]

        db.execute(
            text("""
                INSERT INTO pendencias (id, case_id, title, description, priority, assigned_to,
                                        related_event_id, related_message_id, due_date, created_by)
                VALUES (:id, :case_id, :title, :description, :priority, :assigned_to,
                        :related_event_id, :related_message_id, :due_date, :created_by)
            """),
            {
                "id": pendencia_id,
                "case_id": body.case_id,
                "title": body.title,
                "description": body.description,
                "priority": body.priority,
                "assigned_to": body.assigned_to,
                "related_event_id": body.related_event_id,
                "related_message_id": body.related_message_id,
                "due_date": body.due_date,
                "created_by": user_id,
            },
        )
        db.commit()

        row = db.execute(
            text("SELECT * FROM pendencias WHERE id = :id"), {"id": pendencia_id}
        ).mappings().first()
        return _pendencia_from_row(row)


@router.get("/{case_id}", response_model=list[Pendencia])
def list_pendencias(
    case_id: str,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List pendências for a case with optional filters."""
    factory = get_session_factory()
    with factory() as db:
        query = "SELECT * FROM pendencias WHERE case_id = :case_id"
        params = {"case_id": case_id, "limit": limit}

        if status:
            query += " AND status = :status"
            params["status"] = status
        if priority:
            query += " AND priority = :priority"
            params["priority"] = priority

        query += " ORDER BY created_at DESC LIMIT :limit"

        rows = db.execute(text(query), params).mappings().all()
        return [_pendencia_from_row(r) for r in rows]


@router.put("/{pendencia_id}/status")
def update_pendencia_status(pendencia_id: str, status: str):
    """Update pendência status."""
    valid_statuses = ["open", "in_progress", "resolved", "dismissed"]
    if status not in valid_statuses:
        raise HTTPException(
            status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}"
        )

    factory = get_session_factory()
    with factory() as db:
        resolved_at = datetime.now(timezone.utc) if status == "resolved" else None
        result = db.execute(
            text(
                "UPDATE pendencias SET status = :status, resolved_at = :resolved_at WHERE id = :id"
            ),
            {"id": pendencia_id, "status": status, "resolved_at": resolved_at},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pendência not found")
        db.commit()
    return {"status": status}


@router.delete("/{pendencia_id}")
def delete_pendencia(pendencia_id: str):
    """Delete a pendência."""
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text("DELETE FROM pendencias WHERE id = :id"), {"id": pendencia_id}
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Pendência not found")
        db.commit()
    return {"status": "deleted"}


@router.get("/{case_id}/summary")
def pendencias_summary(case_id: str):
    """Get summary of pendências for a case."""
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("""
                SELECT
                    COUNT(*) as total,
                    COUNT(*) FILTER (WHERE status = 'open') as open,
                    COUNT(*) FILTER (WHERE status = 'in_progress') as in_progress,
                    COUNT(*) FILTER (WHERE status = 'resolved') as resolved,
                    COUNT(*) FILTER (WHERE status = 'dismissed') as dismissed,
                    COUNT(*) FILTER (WHERE priority = 'critical' AND status != 'resolved') as critical,
                    COUNT(*) FILTER (WHERE priority = 'high' AND status != 'resolved') as high_priority
                FROM pendencias
                WHERE case_id = :case_id
            """),
            {"case_id": case_id},
        ).fetchone()
        return {
            "total": row[0],
            "open": row[1],
            "in_progress": row[2],
            "resolved": row[3],
            "dismissed": row[4],
            "critical": row[5],
            "high_priority": row[6],
        }
