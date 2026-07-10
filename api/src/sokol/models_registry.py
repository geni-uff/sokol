"""SOKOL models — registry in models.yaml + admin API for LLM/reranker switching."""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import httpx
import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from .auth import CurrentUser, get_current_user
from .audit import append_audit
from .db import get_session_factory

router = APIRouter(prefix="/admin/models", tags=["admin", "models"])

MODELS_PATH = Path(__file__).parent.parent.parent.parent / "config" / "models.yaml"

# ── Defaults ──────────────────────────────────────────────────────────────
DEFAULT_REGISTRY = {
    "llm_models": [
        {
            "id": "default-llm",
            "provider": "lmstudio",
            "model": "google/gemma-4-12b-qat",
            "context_length": 32768,
            "enabled": True,
            "active": True,
        }
    ],
    "embedding_models": [
        {
            "id": "qwen3-embedding-0_6b",
            "provider": "sokol-embed",
            "model": "Qwen/Qwen3-Embedding-0.6B",
            "dimensions": 1024,
            "context_length": 32768,
            "enabled": True,
            "active": True,
            "readonly": True,
        }
    ],
    "rerank_models": [
        {
            "id": "qwen3-reranker-0_6b",
            "provider": "rerank-service",
            "model": "Qwen/Qwen3-Reranker-0.6B",
            "enabled": True,
            "active": True,
        }
    ],
}


def _load_registry() -> dict:
    if MODELS_PATH.exists():
        return yaml.safe_load(MODELS_PATH.read_text()) or DEFAULT_REGISTRY
    return DEFAULT_REGISTRY


def _save_registry(reg: dict) -> None:
    MODELS_PATH.parent.mkdir(parents=True, exist_ok=True)
    MODELS_PATH.write_text(yaml.dump(reg, default_flow_style=False, allow_unicode=True))


# ── Schemas ───────────────────────────────────────────────────────────────
class ModelInfo(BaseModel):
    id: str
    provider: str
    model: str
    enabled: bool
    active: bool
    context_length: int | None = None
    dimensions: int | None = None
    readonly: bool = False


class ModelListResponse(BaseModel):
    llm_models: list[ModelInfo]
    embedding_models: list[ModelInfo]
    rerank_models: list[ModelInfo]


class SwitchRequest(BaseModel):
    model_id: str


class SwitchResponse(BaseModel):
    ok: bool
    model_type: str
    model_id: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────
@router.get("", response_model=ModelListResponse)
def list_models(user: CurrentUser = Depends(get_current_user)):
    reg = _load_registry()
    return ModelListResponse(
        llm_models=[ModelInfo(**m) for m in reg.get("llm_models", [])],
        embedding_models=[ModelInfo(**m) for m in reg.get("embedding_models", [])],
        rerank_models=[ModelInfo(**m) for m in reg.get("rerank_models", [])],
    )


async def _validate_model_endpoint(provider: str, model_id: str) -> bool:
    """Check that the model endpoint responds."""
    if provider == "lmstudio":
        base_url = os.getenv("SOKOL_LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/models")
                if resp.status_code == 200:
                    models = [m["id"] for m in resp.json().get("data", [])]
                    return model_id in models
        except Exception:
            return False
    elif provider == "sokol-embed":
        base_url = os.getenv("SOKOL_EMBED_BASE_URL", "http://sokol-embed:8001")
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
    return True  # Unknown provider — pass validation


@router.post("/llm/switch", response_model=SwitchResponse)
async def switch_llm(
    body: SwitchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    reg = _load_registry()
    llm_models = reg.get("llm_models", [])
    target = next((m for m in llm_models if m["id"] == body.model_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"LLM model '{body.model_id}' not found")
    if not target.get("enabled", True):
        raise HTTPException(status_code=400, detail=f"LLM model '{body.model_id}' is disabled")

    # Validate endpoint
    ok = await _validate_model_endpoint(target["provider"], target["model"])
    if not ok:
        raise HTTPException(status_code=502, detail=f"Model '{target['model']}' did not respond at endpoint")

    previous = next((m["id"] for m in llm_models if m.get("active")), None)
    for m in llm_models:
        m["active"] = m["id"] == body.model_id
    _save_registry(reg)

    # Audit
    factory = get_session_factory()
    with factory() as db:
        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="model.changed",
            payload={
                "model_type": "llm",
                "previous_model": previous,
                "new_model": body.model_id,
                "requires_reindex": False,
            },
        )
        db.commit()

    return SwitchResponse(ok=True, model_type="llm", model_id=body.model_id, message="LLM switched")


@router.post("/reranker/switch", response_model=SwitchResponse)
async def switch_reranker(
    body: SwitchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    reg = _load_registry()
    rerank_models = reg.get("rerank_models", [])
    target = next((m for m in rerank_models if m["id"] == body.model_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Reranker model '{body.model_id}' not found")
    if not target.get("enabled", True):
        raise HTTPException(status_code=400, detail=f"Reranker model '{body.model_id}' is disabled")

    previous = next((m["id"] for m in rerank_models if m.get("active")), None)
    for m in rerank_models:
        m["active"] = m["id"] == body.model_id
    _save_registry(reg)

    factory = get_session_factory()
    with factory() as db:
        append_audit(
            db,
            case_id=None,
            actor_user_id=user.user_id,
            action="model.changed",
            payload={
                "model_type": "reranker",
                "previous_model": previous,
                "new_model": body.model_id,
                "requires_reindex": False,
            },
        )
        db.commit()

    return SwitchResponse(ok=True, model_type="reranker", model_id=body.model_id, message="Reranker switched")


@router.post("/embedding/switch")
def switch_embedding_rejected(
    body: SwitchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Embedding switching is blocked per ADR-0006."""
    raise HTTPException(
        status_code=400,
        detail="Embedding models are fixed at deploy time per ADR-0006. "
               "To change embedding, reindex offline and update models.yaml directly.",
    )
