"""Redis queue helpers for background job processing."""

import json
import os
from typing import Any, Optional
from uuid import UUID

import redis

# ── Config ────────────────────────────────────────────────────────────
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Queue names
INGEST_QUEUE = "sokol:ingest:queue"
INGEST_PROGRESS = "sokol:ingest:progress"


def get_redis_client() -> redis.Redis:
    """Get Redis client instance."""
    return redis.from_url(REDIS_URL, decode_responses=True)


def enqueue_ingest_job(
    job_id: UUID,
    case_id: UUID,
    inbox_ref: str,
    source_type: str,
    user_id: UUID,
) -> bool:
    """
    Enqueue a file for background ingest processing.

    Args:
        job_id: Unique job ID (UUID)
        case_id: Case ID (UUID)
        inbox_ref: Relative path in inbox directory
        source_type: Source type (ufdr, pdf, etc.)
        user_id: User who initiated ingest (UUID)

    Returns:
        True if enqueued successfully, False otherwise
    """
    try:
        client = get_redis_client()
        job = {
            "job_id": str(job_id),
            "case_id": str(case_id),
            "inbox_ref": inbox_ref,
            "source_type": source_type,
            "user_id": str(user_id),
        }
        client.lpush(INGEST_QUEUE, json.dumps(job))
        return True
    except redis.RedisError as e:
        print(f"❌ Error enqueueing ingest job: {e}")
        return False


def get_ingest_progress(job_id: UUID) -> Optional[dict]:
    """Get progress of an ingest job."""
    try:
        client = get_redis_client()
        progress_key = f"{INGEST_PROGRESS}:{job_id}"
        progress = client.hgetall(progress_key)
        if not progress:
            return None
        return {
            "job_id": str(job_id),
            "status": progress.get("status", "unknown"),
            "progress": float(progress.get("progress", 0.0)),
            "message": progress.get("message", ""),
            "updated_at": progress.get("updated_at", ""),
        }
    except redis.RedisError as e:
        print(f"❌ Error getting ingest progress: {e}")
        return None


def queue_size() -> int:
    """Get current size of ingest queue."""
    try:
        client = get_redis_client()
        return client.llen(INGEST_QUEUE)
    except redis.RedisError:
        return 0
