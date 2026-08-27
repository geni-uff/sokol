"""SOKOL ingest — inbox listing, import to staging with SHA-256, progress SSE.

Author: Matheus C. Pestana
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory
from .inbox_ready import inbox_file_status
from .jobs import emit_progress
from .queue import get_ingest_progress, queue_size

router = APIRouter(prefix="/ingest", tags=["ingest"])

MAX_BATCH_FILES = 200
_INGESTIBLE_SUFFIXES = {
    "ufdr": {".ufdr"},
    "pdf": {".pdf"},
    "image": {".jpg", ".jpeg", ".png", ".webp", ".heic", ".tif", ".tiff", ".bmp"},
    "document": {".pdf", ".docx", ".doc", ".txt"},
}


def _inbox_dir() -> Path:
    p = os.getenv("SOKOL_CONTAINER_INGEST_DIR", "/ingest/inbox")
    return Path(p)


def _staging_dir() -> Path:
    p = os.getenv("SOKOL_STAGING_DIR", "/data/staging")
    return Path(p)


class InboxFile(BaseModel):
    path: str
    name: str
    size: int
    is_dir: bool
    ready: bool = True
    not_ready_reason: str | None = None


class IngestRequest(BaseModel):
    case_id: UUID
    source_type: str  # "ufdr", "pdf", "image", etc.
    inbox_ref: str  # relative path inside inbox (may include subfolders)


class IngestResponse(BaseModel):
    job_id: UUID
    document_id: UUID
    status: str


class BatchIngestRequest(BaseModel):
    case_id: UUID
    source_type: str  # "ufdr", "pdf", "image", etc.
    inbox_refs: list[str]  # files or directories, relative to inbox


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


class IngestJobRow(BaseModel):
    job_id: UUID
    document_id: UUID | None
    status: str
    inbox_ref: str | None
    error: str | None
    created_at: datetime
    updated_at: datetime | None
    parse_coverage: dict | None = None


def _validate_inbox_ref(ref: str) -> str:
    raw = ref.replace("\\", "/").strip()
    if not raw or raw == ".":
        raise HTTPException(status_code=400, detail="inbox_ref is required")
    if os.path.isabs(raw) or raw.startswith("~"):
        raise HTTPException(status_code=400, detail="Absolute paths not allowed")
    normalized = os.path.normpath(raw).replace("\\", "/")
    if normalized == ".." or normalized.startswith("../") or normalized.startswith("/"):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return normalized


def _resolve_under_inbox(ref: str) -> Path:
    inbox = _inbox_dir().resolve()
    source = (inbox / ref).resolve()
    if not source.is_relative_to(inbox):
        raise HTTPException(status_code=400, detail="Path traversal not allowed")
    return source


def _suffixes_for(source_type: str) -> set[str] | None:
    return _INGESTIBLE_SUFFIXES.get(source_type.lower())


def _is_hidden(path: Path, inbox: Path) -> bool:
    try:
        parts = path.relative_to(inbox).parts
    except ValueError:
        return True
    return any(part.startswith(".") or part == "__MACOSX" for part in parts)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _expand_inbox_refs(refs: list[str], source_type: str) -> list[str]:
    """Turn files and directories into unique file paths under the inbox."""
    inbox = _inbox_dir().resolve()
    suffixes = _suffixes_for(source_type)
    expanded: list[str] = []
    seen: set[str] = set()

    for raw in refs:
        ref = _validate_inbox_ref(raw)
        source = _resolve_under_inbox(ref)
        candidates: list[Path]
        if source.is_file():
            candidates = [source]
        elif source.is_dir():
            candidates = sorted(p for p in source.rglob("*") if p.is_file())
        else:
            continue

        for path in candidates:
            if _is_hidden(path, inbox):
                continue
            if suffixes and path.suffix.lower() not in suffixes:
                continue
            rel = path.relative_to(inbox).as_posix()
            if rel in seen:
                continue
            seen.add(rel)
            expanded.append(rel)

    if len(expanded) > MAX_BATCH_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Batch too large ({len(expanded)} files; max {MAX_BATCH_FILES})",
        )
    return expanded


def _queue_one_file(
    db: Session,
    *,
    case_id: UUID,
    user_id: UUID,
    source_type: str,
    inbox_ref: str,
    audit_action: str,
    extra_audit: dict | None = None,
) -> IngestResponse:
    source = _resolve_under_inbox(inbox_ref)
    if not source.is_file():
        raise HTTPException(status_code=404, detail=f"File not found in inbox: {inbox_ref}")
    ready, reason = inbox_file_status(source, source_type)
    if not ready:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Arquivo ainda não está pronto para ingestão: {reason}. "
                "Espere a cópia terminar (o UFDR é um ZIP — só fica válido no fim)."
            ),
        )

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
            "cid": case_id,
            "title": inbox_ref,
            "stype": source_type,
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
            "cid": case_id,
            "payload": json.dumps(
                {
                    "document_id": str(doc_id),
                    "staging_path": str(staging_file),
                    "inbox_ref": inbox_ref,
                    "source_type": source_type,
                }
            ),
            "now": now,
        },
    )

    audit_payload = {
        "document_id": str(doc_id),
        "inbox_ref": inbox_ref,
        "sha256": file_hash,
        **(extra_audit or {}),
    }
    db.execute(
        text("""
            INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, hash, created_at)
            VALUES (:id, :cid, :actor, :action, :payload, :hash, :now)
        """),
        {
            "id": uuid4(),
            "cid": case_id,
            "actor": user_id,
            "action": audit_action,
            "payload": json.dumps(audit_payload),
            "hash": hashlib.sha256(f"{doc_id}{file_hash}".encode()).hexdigest(),
            "now": now,
        },
    )

    emit_progress(str(job_id), "import", "running", 0.0, f"Importing {inbox_ref}")
    return IngestResponse(job_id=job_id, document_id=doc_id, status="pending")


@router.get("/inbox", response_model=list[InboxFile])
def list_inbox(
    user: CurrentUser = Depends(get_current_user),
    prefix: str | None = Query(default=None, description="Subpasta relativa ao inbox"),
    kind: str = Query(default="ufdr", pattern="^(ufdr|pdf|all)$"),
):
    inbox = _inbox_dir().resolve()
    if not inbox.exists():
        raise HTTPException(status_code=404, detail="Inbox directory not accessible")

    root = inbox
    if prefix:
        root = _resolve_under_inbox(_validate_inbox_ref(prefix))
        if not root.is_dir():
            raise HTTPException(status_code=400, detail="prefix must be a directory")

    if kind == "all":
        suffixes = {".ufdr", ".pdf"}
    elif kind == "pdf":
        suffixes = {".pdf"}
    else:
        suffixes = {".ufdr"}

    glob_pat = "*.ufdr" if kind == "ufdr" else "*.pdf" if kind == "pdf" else "*"
    iterator = root.rglob(glob_pat) if kind != "all" else root.rglob("*")

    files: list[InboxFile] = []
    dir_rels: set[str] = set()

    for path in sorted(iterator):
        if _is_hidden(path, inbox):
            continue
        if not path.is_file():
            continue
        if path.suffix.lower() not in suffixes:
            continue
        rel = path.relative_to(inbox).as_posix()
        stype = "pdf" if path.suffix.lower() == ".pdf" else "ufdr"
        ready, reason = inbox_file_status(path, stype)
        files.append(
            InboxFile(
                path=rel,
                name=path.name,
                size=path.stat().st_size,
                is_dir=False,
                ready=ready,
                not_ready_reason=reason,
            )
        )
        parent = path.parent
        while parent != inbox and parent.is_relative_to(inbox):
            dir_rels.add(parent.relative_to(inbox).as_posix())
            parent = parent.parent

    dirs = [
        InboxFile(
            path=rel,
            name=Path(rel).name,
            size=0,
            is_dir=True,
            ready=True,
            not_ready_reason=None,
        )
        for rel in sorted(dir_rels)
    ]
    return dirs + files


@router.get("/jobs", response_model=list[IngestJobRow])
def list_ingest_jobs(
    case_id: UUID,
    user: CurrentUser = Depends(get_current_user),
    limit: int = Query(default=50, ge=1, le=200),
):
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)
        rows = db.execute(
            text("""
                SELECT id, status, payload, error, created_at, updated_at
                FROM jobs
                WHERE case_id = :cid AND kind = 'ingest'
                ORDER BY created_at DESC
                LIMIT :lim
            """),
            {"cid": case_id, "lim": limit},
        ).mappings().all()

    result: list[IngestJobRow] = []
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
        if not isinstance(payload, dict):
            payload = {}
        doc_raw = payload.get("document_id")
        try:
            document_id = UUID(str(doc_raw)) if doc_raw else None
        except ValueError:
            document_id = None
        inbox_ref = payload.get("inbox_ref")
        result.append(
            IngestJobRow(
                job_id=row["id"],
                document_id=document_id,
                status=row["status"],
                inbox_ref=str(inbox_ref) if inbox_ref else None,
                error=row["error"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                parse_coverage=payload.get("parse_coverage")
                if isinstance(payload.get("parse_coverage"), dict)
                else None,
            )
        )
    return result


@router.post("", response_model=IngestResponse, status_code=201)
async def start_ingest(
    body: IngestRequest,
    user: CurrentUser = Depends(get_current_user),
):
    inbox_ref = _validate_inbox_ref(body.inbox_ref)
    source = _resolve_under_inbox(inbox_ref)
    if source.is_dir():
        raise HTTPException(
            status_code=400,
            detail="Directories require POST /ingest/batch",
        )
    if not source.is_file():
        raise HTTPException(status_code=404, detail=f"File not found in inbox: {inbox_ref}")
    suffixes = _suffixes_for(body.source_type)
    if suffixes and source.suffix.lower() not in suffixes:
        raise HTTPException(
            status_code=400,
            detail=f"Extension {source.suffix} does not match source_type={body.source_type}",
        )

    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])
        result = _queue_one_file(
            db,
            case_id=body.case_id,
            user_id=user.user_id,
            source_type=body.source_type,
            inbox_ref=inbox_ref,
            audit_action="ingest.started",
        )
        db.commit()
    return result


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
    """Ingest files, or entire subfolders, from the inbox."""
    refs = _expand_inbox_refs(body.inbox_refs, body.source_type)
    factory = get_session_factory()

    with factory() as db:
        require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])

    results: list[IngestResponse] = []
    for inbox_ref in refs:
        with factory() as db:
            require_case_member(db, body.case_id, user.user_id, roles=["admin", "analista"])
            queued = _queue_one_file(
                db,
                case_id=body.case_id,
                user_id=user.user_id,
                source_type=body.source_type,
                inbox_ref=inbox_ref,
                audit_action="ingest.batch",
                extra_audit={"batch_size": len(refs)},
            )
            db.commit()
            results.append(queued)

    return BatchIngestResponse(results=results, total=len(refs), queued=len(results))
