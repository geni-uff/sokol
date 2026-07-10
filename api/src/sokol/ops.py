"""SOKOL API — Operations observability endpoints."""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory
from .llm import check_lmstudio_health

router = APIRouter(prefix="/ops", tags=["ops"])


# ── Models ─────────────────────────────────────────────────────────────────
class ServiceHealth(BaseModel):
    name: str
    status: str  # ok, degraded, down
    latency_ms: Optional[float] = None
    details: Optional[dict] = None


class QueueStats(BaseModel):
    stage: str
    pending: int
    processing: int
    failed: int
    oldest_pending: Optional[datetime] = None


class LatencyStats(BaseModel):
    p50_ms: float
    p95_ms: float
    p99_ms: float
    sample_count: int


class OpsOverview(BaseModel):
    services: list[ServiceHealth]
    queues: list[QueueStats]
    search_latency: Optional[LatencyStats] = None
    agent_latency: Optional[LatencyStats] = None
    disk_usage: Optional[dict] = None
    alerts: list[str]


class FailedJob(BaseModel):
    id: str
    job_type: str
    error: str
    created_at: datetime
    retry_count: int


# ── Health checks ──────────────────────────────────────────────────────────
async def check_postgres() -> ServiceHealth:
    try:
        factory = get_session_factory()
        with factory() as db:
            start = time.monotonic()
            db.execute(text("SELECT 1"))
            latency = (time.monotonic() - start) * 1000
            return ServiceHealth(
                name="postgres", status="ok", latency_ms=round(latency, 2)
            )
    except Exception as e:
        return ServiceHealth(name="postgres", status="down", details={"error": str(e)})


async def check_worker() -> ServiceHealth:
    try:
        factory = get_session_factory()
        with factory() as db:
            row = db.execute(
                text("SELECT COUNT(*) FROM jobs WHERE status = 'pending'")
            ).fetchone()
            pending = row[0] if row else 0
            return ServiceHealth(
                name="worker",
                status="ok" if pending < 100 else "degraded",
                details={"pending_jobs": pending},
            )
    except Exception as e:
        return ServiceHealth(name="worker", status="down", details={"error": str(e)})


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.get("/health", response_model=OpsOverview)
async def ops_health():
    """Full operations health overview."""
    services = []
    alerts = []

    # Check all services
    pg_health = await check_postgres()
    services.append(pg_health)
    if pg_health.status == "down":
        alerts.append("PostgreSQL is down")

    lmstudio_status = await check_lmstudio_health()
    lmstudio_health = ServiceHealth(name="lmstudio", status=lmstudio_status)
    services.append(lmstudio_health)
    if lmstudio_status != "ok":
        alerts.append("LM Studio is not responding")

    worker_health = await check_worker()
    services.append(worker_health)
    if worker_health.status == "degraded":
        alerts.append("Worker queue has high pending count")

    # Check disk usage
    disk_usage = _get_disk_usage()
    if disk_usage and disk_usage.get("percent_used", 0) > 90:
        alerts.append(f"Disk usage critical: {disk_usage['percent_used']}%")

    # Queue stats
    queues = _get_queue_stats()

    # Latency stats
    search_latency = _get_search_latency()
    agent_latency = _get_agent_latency()

    return OpsOverview(
        services=services,
        queues=queues,
        search_latency=search_latency,
        agent_latency=agent_latency,
        disk_usage=disk_usage,
        alerts=alerts,
    )


@router.get("/health/{service_name}", response_model=ServiceHealth)
async def ops_service_health(service_name: str):
    """Health check for a specific service."""
    checks = {
        "postgres": check_postgres,
        "lmstudio": lambda: ServiceHealth(
            name="lmstudio", status=check_lmstudio_health()
        ),
        "worker": check_worker,
    }
    if service_name not in checks:
        raise HTTPException(status_code=404, detail=f"Unknown service: {service_name}")
    return await checks[service_name]()


@router.get("/queues", response_model=list[QueueStats])
async def ops_queues():
    """Queue statistics by stage."""
    return _get_queue_stats()


@router.get("/latency/search", response_model=LatencyStats)
async def ops_search_latency():
    """Search latency statistics."""
    return _get_search_latency() or LatencyStats(
        p50_ms=0, p95_ms=0, p99_ms=0, sample_count=0
    )


@router.get("/latency/agent", response_model=LatencyStats)
async def ops_agent_latency():
    """Agent/chat latency statistics."""
    return _get_agent_latency() or LatencyStats(
        p50_ms=0, p95_ms=0, p99_ms=0, sample_count=0
    )


@router.get("/failed-jobs", response_model=list[FailedJob])
async def ops_failed_jobs(limit: int = Query(20, ge=1, le=100)):
    """Recent failed jobs with errors."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT id, kind, error, created_at, attempts
                FROM jobs
                WHERE status = 'failed'
                ORDER BY created_at DESC
                LIMIT :limit
            """),
            {"limit": limit},
        ).fetchall()
        return [
            FailedJob(
                id=str(r[0]),
                job_type=r[1],
                error=r[2] or "Unknown error",
                created_at=r[3],
                retry_count=r[4] or 0,
            )
            for r in rows
        ]


@router.post("/failed-jobs/{job_id}/reprocess")
async def ops_reprocess_job(job_id: str):
    """Reprocess a failed job."""
    factory = get_session_factory()
    with factory() as db:
        result = db.execute(
            text(
                "UPDATE jobs SET status = 'pending', error = NULL WHERE id = :id AND status = 'failed'"
            ),
            {"id": job_id},
        )
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Job not found or not failed")
        db.commit()
    return {"status": "reprocessed", "job_id": job_id}


@router.get("/disk")
async def ops_disk():
    """Disk usage information."""
    return _get_disk_usage() or {"error": "Unable to determine disk usage"}


# ── Helpers ────────────────────────────────────────────────────────────────
def _get_queue_stats() -> list[QueueStats]:
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT
                    COALESCE(kind, 'unknown') as stage,
                    COUNT(*) FILTER (WHERE status = 'pending') as pending,
                    COUNT(*) FILTER (WHERE status = 'processing') as processing,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    MIN(created_at) FILTER (WHERE status = 'pending') as oldest_pending
                FROM jobs
                GROUP BY kind
                ORDER BY kind
            """)
        ).fetchall()
        return [
            QueueStats(
                stage=r[0],
                pending=r[1],
                processing=r[2],
                failed=r[3],
                oldest_pending=r[4],
            )
            for r in rows
        ]


def _get_search_latency() -> Optional[LatencyStats]:
    # Latency tracking not yet implemented in audit_log
    return None


def _get_agent_latency() -> Optional[LatencyStats]:
    # Latency tracking not yet implemented in audit_log
    return None


def _get_disk_usage() -> Optional[dict]:
    try:
        stat = os.statvfs("/data" if os.path.exists("/data") else "/")
        total = stat.f_blocks * stat.f_frsize
        free = stat.f_bavail * stat.f_frsize
        used = total - free
        return {
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "percent_used": round((used / total) * 100, 1) if total > 0 else 0,
        }
    except Exception:
        return None
