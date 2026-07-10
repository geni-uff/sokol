"""SOKOL cases — CRUD endpoints with RBAC."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user, require_case_member
from .audit import append_audit
from .db import get_session_factory

router = APIRouter(prefix="/cases", tags=["cases"])


class CaseCreate(BaseModel):
    name: str
    legal_ref: str | None = None
    retention_policy: str | None = None


class CaseResponse(BaseModel):
    id: UUID
    name: str
    legal_ref: str | None
    status: str
    reference_timezone: str
    created_at: datetime


@router.post("", response_model=CaseResponse, status_code=201)
def create_case(
    body: CaseCreate,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        case_id = uuid4()
        now = datetime.now(timezone.utc)
        db.execute(
            text("""
                INSERT INTO cases (id, name, legal_ref, status, reference_timezone, created_at)
                VALUES (:id, :name, :legal_ref, 'active', 'America/Sao_Paulo', :now)
            """),
            {"id": case_id, "name": body.name, "legal_ref": body.legal_ref, "now": now},
        )
        # Creator becomes admin
        db.execute(
            text("INSERT INTO case_members (case_id, user_id, role) VALUES (:cid, :uid, 'admin')"),
            {"cid": case_id, "uid": user.user_id},
        )
        append_audit(
            db, case_id=case_id, actor_user_id=user.user_id,
            action="case.created", payload={"name": body.name, "legal_ref": body.legal_ref},
        )
        db.commit()
        return CaseResponse(
            id=case_id,
            name=body.name,
            legal_ref=body.legal_ref,
            status="active",
            reference_timezone="America/Sao_Paulo",
            created_at=now,
        )


@router.get("", response_model=list[CaseResponse])
def list_cases(user: CurrentUser = Depends(get_current_user)):
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT c.id, c.name, c.legal_ref, c.status, c.reference_timezone, c.created_at
                FROM cases c
                JOIN case_members cm ON cm.case_id = c.id
                WHERE cm.user_id = :uid
                ORDER BY c.created_at DESC
            """),
            {"uid": user.user_id},
        ).fetchall()
        return [
            CaseResponse(
                id=r[0], name=r[1], legal_ref=r[2], status=r[3],
                reference_timezone=r[4], created_at=r[5],
            )
            for r in rows
        ]


@router.get("/{case_id}", response_model=CaseResponse)
def get_case(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        row = db.execute(
            text("SELECT id, name, legal_ref, status, reference_timezone, created_at FROM cases WHERE id = :id"),
            {"id": case_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Case not found")
        return CaseResponse(
            id=row[0], name=row[1], legal_ref=row[2], status=row[3],
            reference_timezone=row[4], created_at=row[5],
        )
