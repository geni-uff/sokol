"""Background worker for UFDR ingest — processes files from Redis queue."""

import hashlib
import json
import logging
import os
import shutil
import signal
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import redis
from sqlalchemy import create_engine, text

# ── Config ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sokol:change_me@sokol-postgres:5433/sokol"
)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

INBOX_DIR = Path(os.getenv("SOKOL_CONTAINER_INGEST_DIR", "/ingest/inbox"))
STAGING_DIR = Path(os.getenv("SOKOL_STAGING_DIR", "/data/staging"))

# ── Redis Queue ────────────────────────────────────────────────────────
INGEST_QUEUE = "sokol:ingest:queue"
INGEST_PROGRESS = "sokol:ingest:progress"  # hash for job status


class IngestWorker:
    """Background worker consuming ingest jobs from Redis queue."""

    def __init__(self, worker_id: int = 1, num_workers: int = 1):
        self.worker_id = worker_id
        self.num_workers = num_workers
        self.redis_client = redis.from_url(REDIS_URL, decode_responses=True)
        self.db_engine = create_engine(DATABASE_URL)
        self.shutdown_event = Event()

        # Signal handlers for graceful shutdown
        signal.signal(signal.SIGTERM, self._on_shutdown)
        signal.signal(signal.SIGINT, self._on_shutdown)

        logger.info(f"Worker {worker_id}/{num_workers} initialized")

    def _on_shutdown(self, signum, frame):
        logger.info(f"Worker {self.worker_id} shutting down...")
        self.shutdown_event.set()

    def run(self):
        """Main loop — consume jobs from queue."""
        logger.info(f"Worker {self.worker_id} started, listening for jobs...")

        while not self.shutdown_event.is_set():
            try:
                # BRPOP blocks until job available (timeout 5s to check shutdown)
                result = self.redis_client.brpop(INGEST_QUEUE, timeout=5)

                if result is None:
                    continue

                _key, job_json = result
                job = json.loads(job_json)

                self._process_job(job)

            except redis.RedisError as e:
                logger.error(f"Redis error: {e}, retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                time.sleep(1)

        logger.info(f"Worker {self.worker_id} stopped")

    def _process_job(self, job: dict):
        """Process a single ingest job."""
        job_id = job.get("job_id")
        case_id = job.get("case_id")
        inbox_ref = job.get("inbox_ref")
        source_type = job.get("source_type")
        user_id = job.get("user_id")

        logger.info(f"[{job_id}] Processing: {inbox_ref}")

        try:
            self._update_progress(job_id, "running", 0.0, f"Starting ingest of {inbox_ref}")

            # Validate file
            source = INBOX_DIR / inbox_ref
            if not source.exists() or not source.is_file():
                raise FileNotFoundError(f"File not found: {inbox_ref}")

            # SHA256 hash
            file_hash = self._sha256_file(source)
            file_size = source.stat().st_size

            self._update_progress(job_id, "running", 10.0, f"File verified: {file_size} bytes")

            # Copy to staging
            STAGING_DIR.mkdir(parents=True, exist_ok=True)
            staging_file = STAGING_DIR / f"{job_id}_{source.name}"
            shutil.copy2(source, staging_file)

            self._update_progress(job_id, "running", 30.0, f"Copied to staging: {staging_file}")

            # Create DB records
            with self.db_engine.connect() as conn:
                doc_id = uuid4()
                now = datetime.now(timezone.utc)

                # Create document
                conn.execute(
                    text("""
                        INSERT INTO documents (id, case_id, title, source_type, source_uri, sha256, status, created_at)
                        VALUES (:id, :cid, :title, :stype, :uri, :sha, 'importing', :now)
                    """),
                    {
                        "id": doc_id,
                        "cid": case_id,
                        "title": inbox_ref,
                        "stype": source_type,
                        "uri": f"inbox:{inbox_ref}",
                        "sha": file_hash,
                        "now": now,
                    },
                )

                # Create job
                # Note: This job_id matches the ingest job, but parser will create its own
                conn.execute(
                    text("""
                        INSERT INTO jobs (id, case_id, kind, payload, status, pipeline_version, created_at, updated_at)
                        VALUES (:id, :cid, 'ingest', :payload, 'pending', 'v1', :now, :now)
                    """),
                    {
                        "id": job_id,
                        "cid": case_id,
                        "payload": json.dumps({
                            "document_id": str(doc_id),
                            "staging_path": str(staging_file),
                            "source_type": source_type,
                        }),
                        "now": now,
                    },
                )

                # Audit log
                audit_id = uuid4()
                conn.execute(
                    text("""
                        INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, hash, created_at)
                        VALUES (:id, :cid, :actor, 'ingest.worker', :payload, :hash, :now)
                    """),
                    {
                        "id": audit_id,
                        "cid": case_id,
                        "actor": user_id,
                        "payload": json.dumps({
                            "document_id": str(doc_id),
                            "inbox_ref": inbox_ref,
                            "sha256": file_hash,
                            "file_size": file_size,
                            "worker_id": self.worker_id,
                        }),
                        "hash": hashlib.sha256(
                            f"{doc_id}{file_hash}{self.worker_id}".encode()
                        ).hexdigest(),
                        "now": now,
                    },
                )

                conn.commit()

            self._update_progress(job_id, "running", 70.0, f"Database records created")

            # Here: Parser would be triggered (in real impl, via another queue or direct call)
            # For now, mark as ready for pipeline
            self._update_progress(job_id, "completed", 100.0, f"Ingest completed: {inbox_ref}")
            logger.info(f"[{job_id}] ✅ Ingest completed successfully")

        except Exception as e:
            logger.error(f"[{job_id}] ❌ Error: {e}", exc_info=True)
            self._update_progress(job_id, "failed", 0.0, f"Error: {str(e)}")

    def _update_progress(self, job_id: str, status: str, progress: float, message: str):
        """Update job progress in Redis."""
        self.redis_client.hset(
            f"{INGEST_PROGRESS}:{job_id}",
            mapping={
                "status": status,
                "progress": progress,
                "message": message,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        # Expire after 24h
        self.redis_client.expire(f"{INGEST_PROGRESS}:{job_id}", 86400)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        """Calculate SHA256 of file."""
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()


if __name__ == "__main__":
    import sys

    worker_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    num_workers = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    worker = IngestWorker(worker_id=worker_id, num_workers=num_workers)
    worker.run()
