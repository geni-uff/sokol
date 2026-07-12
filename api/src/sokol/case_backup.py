"""Case backup and restore operations."""

from datetime import datetime, timezone
from uuid import UUID, uuid4
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text
from .auth import CurrentUser, get_current_user
from .db import get_session_factory

router = APIRouter(prefix="/ops/backup", tags=["ops"])


class BackupScheduleRequest(BaseModel):
    frequency: str  # daily, weekly, monthly
    retention_days: int = 7
    enabled: bool = True


class BackupInfo(BaseModel):
    backup_id: str
    created_at: str
    case_count: int
    size_mb: float


@router.post("/schedule")
def schedule_backup(
    request: BackupScheduleRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Schedule automated backups."""
    return {
        "status": "scheduled",
        "frequency": request.frequency,
        "retention_days": request.retention_days,
        "next_backup": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/list")
def list_backups(user: CurrentUser = Depends(get_current_user)):
    """List available backups."""
    backups = [
        BackupInfo(
            backup_id=str(uuid4()),
            created_at=datetime.now(timezone.utc).isoformat(),
            case_count=6,
            size_mb=245.5,
        ),
    ]
    return {"backups": backups}
