"""Operations monitoring and health endpoints."""

import os
import psutil
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from .auth import CurrentUser, get_current_user

router = APIRouter(prefix="/ops/monitoring", tags=["ops"])


class ServiceStatus(BaseModel):
    name: str
    status: str  # up, down, slow
    latency_ms: float | None = None
    uptime_pct: float | None = None


class SystemMetrics(BaseModel):
    cpu_percent: float
    memory_percent: float
    disk_percent: float
    timestamp: str


class MonitoringResponse(BaseModel):
    services: list[ServiceStatus]
    system: SystemMetrics
    queued_jobs: int
    timestamp: str


@router.get("/status", response_model=MonitoringResponse)
def get_monitoring_status(user: CurrentUser = Depends(get_current_user)):
    """Get system and services health status."""
    
    # System metrics
    cpu = psutil.cpu_percent(interval=0.1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    # Service status (mock for now, could query real services)
    services = [
        ServiceStatus(name="API", status="up", latency_ms=45.2, uptime_pct=99.8),
        ServiceStatus(name="Database", status="up", latency_ms=12.5, uptime_pct=99.9),
        ServiceStatus(name="Redis", status="up", latency_ms=2.1, uptime_pct=99.7),
        ServiceStatus(name="Embed", status="up", latency_ms=280.5, uptime_pct=98.5),
        ServiceStatus(name="Vision", status="up", latency_ms=450.0, uptime_pct=97.2),
    ]
    
    # Queue stats (from Redis if available)
    try:
        from .queue import queue_size
        queued = queue_size()
    except:
        queued = 0
    
    return MonitoringResponse(
        services=services,
        system=SystemMetrics(
            cpu_percent=cpu,
            memory_percent=mem.percent,
            disk_percent=disk.percent,
            timestamp=datetime.now(timezone.utc).isoformat(),
        ),
        queued_jobs=queued,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
