"""SOKOL ingest — inbox listing, import to staging with SHA-256, progress SSE."""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory
from .jobs import emit_progress
from .queue import enqueue_ingest_job, get_ingest_progress, queue_size

router = APIRouter(prefix="/ingest", tags=["ingest"])


def _inbox_dir() -> Path:
    p = os.getenv("SOKOL_CONTAINER_INGEST_DIR", "/ingest/inbox")
    return Path(p)


def _staging_dir() -> Path:
    p = os.getenv("SOKOL_STAGING_DIR", "/data/staging")
    return Path(p)


class InboxFile(BaseModel):
    name: str
    size: int
    is_dir: bool


class IngestRequest(BaseModel):
    case_id: UUID
    source_type: str  # "ufdr", "pdf", "image", etc.
    inbox_ref: str  # relative path inside inbox


class IngestResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    status: str


class BatchIngestRequest(BaseModel):
    case_id: UUID
    source_type: str  # "ufdr", "pdf", "image", etc.
    inbox_refs: list[str]  # relative paths inside inbox


class BatchIngestResponse(BaseModel):
    results: list[IngestResponse]
    total: int
    queued: int


class IngestProgressResponse(BaseModel):
    job_id: str
    status: str  # running, completed, failed
    progress: float  # 0.0 to 100.0
    message: str
    updated_at: str


# ── Path traversal protection ─────────────────────────────────────────────
def _validate_inbox_ref(ref: str) -> str:
    if os.path.isabs(ref):
        raise HTTPException(status_code=400, detail="Absolute paths not allowed")
    normalized = os.path.normpath(ref)
    if normalized.startswith("..") or normalized.startswith("/"):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return normalized


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@router.get("/inbox", response_model=list[InboxFile])
def list_inbox(user: CurrentUser = Depends(get_current_user)):
    inbox = _inbox_dir()
    if not inbox.exists():
        raise HTTPException(status_code=404, detail="Inbox directory not accessible")
    files = []
    for entry in sorted(inbox.iterdir()):
        if entry.name.startswith("."):
            continue
        files.append(
            InboxFile(
                name=entry.name,
                size=entry.stat().st_size if entry.is_file() else 0,
                is_dir=entry.is_dir(),
            )
        )
    return files


@router.post("", response_model=IngestResponse, status_code=201)
async def start_ingest(
    body: IngestRequest,
    user: CurrentUser = Depends(get_current_user),
):
    inbox_ref = _validate_inbox_ref(body.inbox_ref)
    inbox = _inbox_dir()
    source = inbox / inbox_ref

    if not source.exists():
        raise HTTPException(
            status_code=404, detail=f"File not found in inbox: {inbox_ref}"
        )
    if not source.is_file():
        raise HTTPException(status_code=400, detail="inbox_ref must point to a file")

    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])

        # Create document
        doc_id = uuid4()
        now = datetime.now(timezone.utc)
        file_hash = _sha256_file(source)

        db.execute(
            text("""
                INSERT INTO documents (id, case_id, title, source_type, source_uri, sha256, status, created_at)
                VALUES (:id, :cid, :title, :stype, :uri, :sha, 'importing', :now)
            """),
            {
                "id": doc_id,
                "cid": body.case_id,
                "title": inbox_ref,
                "stype": body.source_type,
                "uri": f"inbox:{inbox_ref}",
                "sha": file_hash,
                "now": now,
            },
        )

        # Copy to staging
        staging = _staging_dir()
        staging.mkdir(parents=True, exist_ok=True)
        staging_file = staging / f"{doc_id}_{source.name}"
        shutil.copy2(source, staging_file)

        # Create job
        job_id = uuid4()
        db.execute(
            text("""
                INSERT INTO jobs (id, case_id, kind, payload, status, pipeline_version, created_at, updated_at)
                VALUES (:id, :cid, 'ingest', :payload, 'pending', 'v1', :now, :now)
            """),
            {
                "id": job_id,
                "cid": body.case_id,
                "payload": f'{{"document_id":"{doc_id}","staging_path":"{staging_file}"}}',
                "now": now,
            },
        )

        # Audit
        audit_id = uuid4()
        db.execute(
            text("""
                INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, hash, created_at)
                VALUES (:id, :cid, :actor, 'ingest.started', :payload, :hash, :now)
            """),
            {
                "id": audit_id,
                "cid": body.case_id,
                "actor": user.user_id,
                "payload": f'{{"document_id":"{doc_id}","inbox_ref":"{inbox_ref}","sha256":"{file_hash}"}}',
                "hash": hashlib.sha256(f"{doc_id}{file_hash}".encode()).hexdigest(),
                "now": now,
            },
        )

        db.commit()

    emit_progress(str(job_id), "import", "running", 0.0, f"Importing {inbox_ref}")

    return IngestResponse(job_id=job_id, document_id=doc_id, status="pending")


@router.get("/progress/{job_id}", response_model=IngestProgressResponse | dict)
def get_ingest_progress_endpoint(
    job_id: str,
    user: CurrentUser = Depends(get_current_user),
):
    """Get progress of an ingest job."""
    progress = get_ingest_progress(UUID(job_id))
    if not progress:
        return {"detail": "Job not found", "job_id": job_id}
    return progress


@router.get("/queue/status", response_model=dict)
def get_queue_status(user: CurrentUser = Depends(get_current_user)):
    """Get current queue status."""
    return {
        "queued_jobs": queue_size(),
        "worker_status": "Check /health for worker health",
    }


@router.post("/batch", response_model=BatchIngestResponse, status_code=201)
async def batch_ingest(
    body: BatchIngestRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Ingest multiple files in parallel."""
    inbox = _inbox_dir()
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])

    results = []

    for inbox_ref in body.inbox_refs:
        inbox_ref = _validate_inbox_ref(inbox_ref)
        source = inbox / inbox_ref

        if not source.exists() or not source.is_file():
            continue

        with factory() as db:
            require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])

            doc_id = uuid4()
            now = datetime.now(timezone.utc)
            file_hash = _sha256_file(source)

            db.execute(
                text("""
                    INSERT INTO documents (id, case_id, title, source_type, source_uri, sha256, status, created_at)
                    VALUES (:id, :cid, :title, :stype, :uri, :sha, 'importing', :now)
                """),
                {
                    "id": doc_id,
                    "cid": body.case_id,
                    "title": inbox_ref,
                    "stype": body.source_type,
                    "uri": f"inbox:{inbox_ref}",
                    "sha": file_hash,
                    "now": now,
                },
            )

            staging = _staging_dir()
            staging.mkdir(parents=True, exist_ok=True)
            staging_file = staging / f"{doc_id}_{source.name}"
            shutil.copy2(source, staging_file)

            job_id = uuid4()
            db.execute(
                text("""
                    INSERT INTO jobs (id, case_id, kind, payload, status, pipeline_version, created_at, updated_at)
                    VALUES (:id, :cid, 'ingest', :payload, 'pending', 'v1', :now, :now)
                """),
                {
                    "id": job_id,
                    "cid": body.case_id,
                    "payload": f'{{"document_id":"{doc_id}","staging_path":"{staging_file}"}}',
                    "now": now,
                },
            )

            audit_id = uuid4()
            db.execute(
                text("""
                    INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, hash, created_at)
                    VALUES (:id, :cid, :actor, 'ingest.batch', :payload, :hash, :now)
                """),
                {
                    "id": audit_id,
                    "cid": body.case_id,
                    "actor": user.user_id,
                    "payload": f'{{"batch_size":{len(body.inbox_refs)},"document_id":"{doc_id}"}}',
                    "hash": hashlib.sha256(f"{doc_id}{file_hash}".encode()).hexdigest(),
                    "now": now,
                },
            )

            db.commit()

            emit_progress(str(job_id), "import", "running", 0.0, f"Importing {inbox_ref}")

            results.append(IngestResponse(job_id=job_id, document_id=doc_id, status="pending"))

    return BatchIngestResponse(results=results, total=len(body.inbox_refs), queued=len(results))
