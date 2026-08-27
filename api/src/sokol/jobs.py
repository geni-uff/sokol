"""SOKOL jobs — repository with FOR UPDATE SKIP LOCKED and SSE progress."""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(tags=["jobs"])


# ── SSE progress store (in-memory for v1) ────────────────────────────────
_job_events: dict[str, list[dict]] = {}
_job_subs: dict[str, list[asyncio.Queue]] = {}
_job_case_ids: dict[str, str] = {}


def emit_progress(
    job_id: str,
    stage: str,
    status: str,
    progress: float,
    message: str = "",
    case_id: str | None = None,
) -> None:
    """Push a progress event to all SSE subscribers and persist to store."""
    if case_id:
        _job_case_ids[job_id] = case_id
    resolved = case_id or _job_case_ids.get(job_id)
    event = {
        "job_id": job_id,
        "case_id": resolved,
        "stage": stage,
        "status": status,
        "progress": progress,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    _job_events.setdefault(job_id, []).append(event)
    for q in _job_subs.get(job_id, []):
        q.put_nowait(event)


# ── Job claim (FOR UPDATE SKIP LOCKED) ───────────────────────────────────
def claim_next_job(db: Session, worker_id: str, pipeline_version: str = "v1") -> dict | None:
    """Atomically claim the next pending job. Returns None if no job available."""
    row = db.execute(
        text("""
            UPDATE jobs
            SET status = 'running',
                claimed_by = :worker,
                attempts = attempts + 1,
                heartbeat_at = now(),
                updated_at = now()
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'pending'
                ORDER BY priority, created_at
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            RETURNING id, case_id, kind, payload, priority, attempts, max_attempts
        """),
        {"worker": worker_id},
    ).fetchone()
    if row is None:
        return None
    db.commit()
    return {
        "id": row[0],
        "case_id": row[1],
        "kind": row[2],
        "payload": row[3],
        "priority": row[4],
        "attempts": row[5],
        "max_attempts": row[6],
    }


def complete_job(db: Session, job_id: UUID, status: str = "done", error: str | None = None) -> None:
    db.execute(
        text("UPDATE jobs SET status = :s, error = :e, updated_at = now() WHERE id = :id"),
        {"s": status, "e": error, "id": job_id},
    )
    db.commit()
    emit_progress(str(job_id), "done" if status == "done" else "error", status, 1.0 if status == "done" else 0.0, error or "")


def heartbeat_job(db: Session, job_id: UUID) -> None:
    db.execute(
        text("UPDATE jobs SET heartbeat_at = now() WHERE id = :id"),
        {"id": job_id},
    )
    db.commit()


# ── Endpoints ─────────────────────────────────────────────────────────────
class JobResponse(BaseModel):
    id: UUID
    case_id: UUID | None
    kind: str
    status: str
    priority: int
    attempts: int
    max_attempts: int
    error: str | None
    created_at: datetime
    updated_at: datetime


@router.get("/jobs/{job_id}", response_model=JobResponse)
def get_job(
    job_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT id, case_id, kind, status, priority, attempts, max_attempts, error, created_at, updated_at FROM jobs WHERE id = :id"),
            {"id": job_id},
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Job not found")
        return JobResponse(
            id=row[0], case_id=row[1], kind=row[2], status=row[3],
            priority=row[4], attempts=row[5], max_attempts=row[6],
            error=row[7], created_at=row[8], updated_at=row[9],
        )


async def _sse_generator(job_id: str):
    """SSE generator that yields job progress events."""
    queue: asyncio.Queue = asyncio.Queue()
    _job_subs.setdefault(job_id, []).append(queue)
    try:
        # Send existing events first
        for evt in _job_events.get(job_id, []):
            yield f"data: {json.dumps(evt)}\n\n"
        # Then stream new ones
        while True:
            try:
                evt = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                # Send keepalive
                yield ": keepalive\n\n"
                continue
            yield f"data: {json.dumps(evt)}\n\n"
            if evt.get("status") in ("done", "failed", "cancelled"):
                break
    finally:
        _job_subs.get(job_id, []).remove(queue)


@router.get("/events/jobs/{job_id}")
async def job_events_sse(
    job_id: UUID,
    user: CurrentUser = Depends(get_current_user),
):
    return StreamingResponse(
        _sse_generator(str(job_id)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
