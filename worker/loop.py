"""SOKOL worker — job polling loop with FOR UPDATE SKIP LOCKED."""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

try:
    from .ufdr_parser import process_ufdr
except ImportError:
    from ufdr_parser import process_ufdr

logger = logging.getLogger("sokol.worker")

WORKER_ID = f"sokol-worker-{uuid.uuid4().hex[:8]}"
POLL_INTERVAL = float(os.getenv("SOKOL_WORKER_POLL_INTERVAL", "2.0"))
BACKUP_CHECK_INTERVAL = float(os.getenv("SOKOL_BACKUP_CHECK_INTERVAL", "300"))
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol"
)


def _emit_progress(job_id: str, stage: str, progress: float, message: str = "") -> None:
    """Emit progress event — mirrors API's emit_progress via DB notification."""
    # In v1 we just log; the SSE endpoint reads from _job_events in the API process.
    # For a real worker, we'd publish to Redis or use NOTIFY/LISTEN.
    logger.info(f"[{job_id}] {stage}: {progress:.0%} — {message}")


def claim_next_job(engine) -> dict | None:
    """Atomically claim the next pending job."""
    with engine.connect() as conn:
        row = conn.execute(
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
            {"worker": WORKER_ID},
        ).fetchone()
        conn.commit()
        if row is None:
            return None
        return {
            "id": row[0],
            "case_id": row[1],
            "kind": row[2],
            "payload": row[3],
            "priority": row[4],
            "attempts": row[5],
            "max_attempts": row[6],
        }


def complete_job(
    engine, job_id, status: str = "done", error: str | None = None
) -> None:
    with engine.connect() as conn:
        conn.execute(
            text(
                "UPDATE jobs SET status = :s, error = :e, updated_at = now() WHERE id = :id"
            ),
            {"s": status, "e": error, "id": job_id},
        )
        conn.commit()


def heartbeat_job(engine, job_id) -> None:
    with engine.connect() as conn:
        conn.execute(
            text("UPDATE jobs SET heartbeat_at = now() WHERE id = :id"),
            {"id": job_id},
        )
        conn.commit()


def process_job(engine, job: dict) -> None:
    """Process a single job based on its kind."""
    job_id = job["id"]
    case_id = job["case_id"]
    kind = job["kind"]

    # Parse payload
    payload = job["payload"]
    if isinstance(payload, str):
        payload = json.loads(payload)

    logger.info(f"Processing job {job_id} (kind={kind})")

    if kind == "ingest":
        _process_ingest(engine, job_id, case_id, payload)
    else:
        logger.warning(f"Unknown job kind: {kind}")
        complete_job(engine, job_id, "failed", f"Unknown job kind: {kind}")


def _process_ingest(engine, job_id, case_id, payload: dict) -> None:
    """Process an ingest job — parse UFDR and populate database."""
    document_id = payload.get("document_id")
    staging_path = payload.get("staging_path")

    if not document_id or not staging_path:
        complete_job(engine, job_id, "failed", "Missing document_id or staging_path")
        return

    ufdr_path = Path(staging_path)

    if not ufdr_path.exists():
        complete_job(engine, job_id, "failed", f"File not found: {staging_path}")
        return

    if ufdr_path.suffix.lower() == ".ufdr" and not zipfile.is_zipfile(ufdr_path):
        complete_job(
            engine,
            job_id,
            "failed",
            "UFDR incompleto (ZIP inválido). A cópia para o inbox ainda não tinha acabado.",
        )
        return

    def progress_callback(stage: str, progress: float, message: str = ""):
        _emit_progress(str(job_id), stage, progress, message)
        # Update heartbeat periodically
        if progress % 0.2 < 0.05:
            heartbeat_job(engine, job_id)

    try:
        with engine.connect() as conn:
            result = process_ufdr(
                db=conn,
                ufdr_path=ufdr_path,
                case_id=uuid.UUID(str(case_id)),
                document_id=uuid.UUID(str(document_id)),
                progress_callback=progress_callback,
            )

            # Update document status
            conn.execute(
                text("UPDATE documents SET status = 'ready' WHERE id = :id"),
                {"id": document_id},
            )
            payload["parse_coverage"] = {
                "model_type_counts": result.get("model_type_counts"),
                "ignored_model_types": result.get("ignored_model_types"),
                "fs_walk": result.get("fs_walk"),
            }
            conn.execute(
                text("UPDATE jobs SET payload = CAST(:p AS json) WHERE id = :id"),
                {"p": json.dumps(payload, default=str), "id": job_id},
            )
            conn.commit()

        complete_job(engine, job_id, "done")
        logger.info(f"Job {job_id} completed: {result}")
        try:
            from api.src.sokol.cache import cache_delete, cache_invalidate

            cache_delete(f"sokol:stats:{case_id}")
            cache_invalidate("sokol:cross-case")
        except Exception:
            pass

    except Exception as e:
        logger.exception(f"Job {job_id} failed")
        complete_job(engine, job_id, "failed", str(e))


def run_forever() -> None:
    """Main worker loop — polls for jobs and processes them."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    logger.info(f"Worker {WORKER_ID} starting (poll_interval={POLL_INTERVAL}s)")
    logger.info(
        f"Database: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else DATABASE_URL}"
    )

    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    last_backup_check = 0.0

    while True:
        try:
            job = claim_next_job(engine)
            if job is None:
                now = time.monotonic()
                if now - last_backup_check >= BACKUP_CHECK_INTERVAL:
                    last_backup_check = now
                    try:
                        from api.src.sokol.backup_service import run_scheduled_backup_if_due

                        result = run_scheduled_backup_if_due()
                        if result:
                            logger.info("Scheduled backup created: %s", result.get("name"))
                    except Exception as e:
                        logger.warning("Scheduled backup check failed: %s", e)
                time.sleep(POLL_INTERVAL)
                continue

            process_job(engine, job)

        except KeyboardInterrupt:
            logger.info("Worker shutting down")
            break
        except Exception as e:
            logger.exception(f"Worker error: {e}")
            time.sleep(POLL_INTERVAL * 2)


if __name__ == "__main__":
    run_forever()
