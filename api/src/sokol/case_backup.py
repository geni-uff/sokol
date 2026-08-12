"""Backup and restore API — real pg_dump + media archives (v2-11)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from .audit import append_audit
from .auth import CurrentUser, get_current_user
from .backup_helpers import compute_next_run
from .backup_service import (
    create_backup,
    list_backup_archives,
    load_schedule,
    restore_backup,
    save_schedule,
)
from .db import get_session_factory

router = APIRouter(prefix="/backup", tags=["backup"])


class BackupScheduleRequest(BaseModel):
    frequency: str = Field(..., pattern="^(daily|weekly|monthly)$")
    retention_days: int = Field(7, ge=1, le=365)
    enabled: bool = True


class RestoreRequest(BaseModel):
    backup_file: str
    confirm: bool = False
    target_db: str | None = None


def require_platform_admin(db: Session, user_id: UUID) -> None:
    """Admin-only: user must hold role=admin on at least one case."""
    row = db.execute(
        text("""
            SELECT 1 FROM case_members
            WHERE user_id = :uid AND role = 'admin'
            LIMIT 1
        """),
        {"uid": user_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="Admin role required")


@router.post("")
@router.post("/")
def run_backup(user: CurrentUser = Depends(get_current_user)):
    """Create a real backup archive (pg_dump + media/staging) under SOKOL_BACKUP_DIR."""
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)
        try:
            result = create_backup()
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Backup failed: {e}") from e

        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="backup.created",
            payload={
                "name": result["name"],
                "sha256": result["sha256"],
                "size_bytes": result["size_bytes"],
            },
        )
        db.commit()
        return {"status": "created", **result}


@router.get("/list")
def list_backups(user: CurrentUser = Depends(get_current_user)):
    """List real backups from SOKOL_BACKUP_DIR."""
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)
        backups = list_backup_archives()
        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="backup.listed",
            payload={"count": len(backups)},
        )
        db.commit()
        return {"backups": backups}


@router.post("/schedule")
def schedule_backup(
    request: BackupScheduleRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Persist backup schedule (honoured by the worker loop)."""
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)
        now = datetime.now(timezone.utc)
        schedule = {
            "frequency": request.frequency,
            "retention_days": request.retention_days,
            "enabled": request.enabled,
            "last_run_at": load_schedule().get("last_run_at"),
            "next_run_at": compute_next_run(request.frequency, now).isoformat()
            if request.enabled
            else None,
            "updated_at": now.isoformat(),
        }
        save_schedule(schedule)
        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="backup.scheduled",
            payload=schedule,
        )
        db.commit()
        return {"status": "scheduled", **schedule}


@router.get("/schedule")
def get_schedule(user: CurrentUser = Depends(get_current_user)):
    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)
        return load_schedule()


@router.post("/restore")
def restore(
    body: RestoreRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """
    Restore a backup archive into Postgres.

    **Destructive:** when `target_db` is omitted, the live database is dropped
    and recreated. Requires `confirm: true`.
    """
    if body.confirm is not True:
        raise HTTPException(
            status_code=400,
            detail="Restore overwrites the database; set confirm=true to proceed",
        )

    factory = get_session_factory()
    with factory() as db:
        require_platform_admin(db, user.user_id)

        try:
            result = restore_backup(body.backup_file, target_db=body.target_db)
        except FileNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Restore failed: {e}") from e

        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="backup.restored",
            payload={
                "backup_file": body.backup_file,
                "target_db": result.get("target_db"),
                "confirm": True,
            },
        )
        db.commit()
        return result
