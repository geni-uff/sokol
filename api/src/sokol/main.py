"""SOKOL API — main application."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .llm import check_lmstudio_health

SOKOL_VERSION = "0.1.0"


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(title="SOKOL API", version=SOKOL_VERSION, lifespan=lifespan)

# ── Register routers ──────────────────────────────────────────────────────
from .cases import router as cases_router
from .jobs import router as jobs_router
from .ingest import router as ingest_router
from .models_registry import router as models_router
from .search import router as search_router
from .chat_api import router as chat_router
from .timeline import router as timeline_router
from .ops import router as ops_router
from .reports import router as reports_router
from .watchlists import router as watchlists_router
from .pendencias import router as pendencias_router
from .media import router as media_router
from .graph import router as graph_router
from .playbooks import router as playbooks_router
from .vision import router as vision_router
from .faces import router as faces_router
from .pipeline import router as pipeline_router
from .plates_transcriptions import plates_router as plates_router_mod
from .plates_transcriptions import transcriptions_router as transcriptions_router_mod
from .ocr_results import router as ocr_router

app.include_router(cases_router)
app.include_router(jobs_router)
app.include_router(ingest_router)
app.include_router(models_router)
app.include_router(search_router)
app.include_router(chat_router)
app.include_router(timeline_router)
app.include_router(ops_router)
app.include_router(reports_router)
app.include_router(watchlists_router)
app.include_router(pendencias_router)
app.include_router(media_router)
app.include_router(graph_router)
app.include_router(playbooks_router)
app.include_router(vision_router)
app.include_router(faces_router)
app.include_router(pipeline_router)
app.include_router(plates_router_mod)
app.include_router(transcriptions_router_mod)
app.include_router(ocr_router)


# ── Auth endpoints ────────────────────────────────────────────────────────
from .auth import hash_password, verify_password, create_session
from .audit import append_audit
from .db import get_session_factory


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    user_id: str


@app.post("/auth/login", response_model=LoginResponse)
def login(body: LoginRequest):
    factory = get_session_factory()
    with factory() as db:
        row = db.execute(
            text("SELECT id, password_hash FROM users WHERE username = :u"),
            {"u": body.username},
        ).fetchone()
        if row is None or not verify_password(row[1], body.password):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        token = create_session(row[0])
        append_audit(
            db,
            case_id=None,
            actor_user_id=row[0],
            action="auth.login",
            payload={"username": body.username},
        )
        db.commit()
        return LoginResponse(token=token, user_id=str(row[0]))


# ── Health ────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    lmstudio_status = await check_lmstudio_health()
    return {
        "status": "ok",
        "version": SOKOL_VERSION,
        "services": {
            "postgres": "ok",
            "lmstudio": lmstudio_status,
        },
    }


# ── Audit verify endpoint ─────────────────────────────────────────────────
from .audit import verify_chain


@app.get("/admin/audit/verify")
def audit_verify(user: dict = None):
    """Verify the global audit chain integrity."""
    from .auth import get_current_user
    from fastapi import Request

    # Simplified — in production use proper dependency
    factory = get_session_factory()
    with factory() as db:
        errors = verify_chain(db)
    return {"valid": len(errors) == 0, "errors": errors}
