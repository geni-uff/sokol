"""SOKOL LLM client — OpenAI-compatible chat completions via LM Studio."""
from __future__ import annotations

import os
import httpx

DEFAULT_BASE_URL = "http://host.docker.internal:1234/v1"
DEFAULT_TIMEOUT = 120.0


def _get_base_url() -> str:
    return os.getenv("SOKOL_LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)


def get_active_llm_model() -> str:
    """Resolve the LLM id: registry active, then env, then the first LM Studio model."""
    try:
        from .models_registry import _load_registry

        reg = _load_registry()
        active = next((m for m in reg.get("llm_models", []) if m.get("active")), None)
        if active and active.get("model"):
            return str(active["model"])
    except Exception:
        pass
    for key in ("SOKOL_ACTIVE_LLM_MODEL", "SOKOL_DEFAULT_LLM_MODEL"):
        value = os.getenv(key, "").strip()
        if value and value != "change_me":
            return value
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{_get_base_url()}/models")
            resp.raise_for_status()
            models = resp.json().get("data") or []
            if models:
                return str(models[0]["id"])
    except Exception:
        pass
    raise RuntimeError(
        "Nenhum modelo LLM configurado. Defina SOKOL_DEFAULT_LLM_MODEL "
        "ou ative um modelo em Administração."
    )


def get_llm_context_length() -> int:
    """Effective n_ctx: registry, then env, default 32768."""
    try:
        from .models_registry import _load_registry

        reg = _load_registry()
        active = next((m for m in reg.get("llm_models", []) if m.get("active")), None)
        if active and active.get("context_length"):
            return int(active["context_length"])
    except Exception:
        pass
    for key in ("SOKOL_LLM_N_CTX", "SOKOL_LLM_CONTEXT_LENGTH"):
        raw = os.getenv(key, "").strip()
        if raw.isdigit():
            return int(raw)
    return 32768


def _get_model() -> str:
    return get_active_llm_model()


async def chat_completions(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    stream: bool = False,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """Non-streaming chat completion."""
    url = f"{_get_base_url()}/chat/completions"
    payload = {
        "model": model or _get_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        return resp.json()


async def chat_completions_stream(
    messages: list[dict],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
    timeout: float = DEFAULT_TIMEOUT,
):
    """Streaming chat completion — yields SSE chunks."""
    url = f"{_get_base_url()}/chat/completions"
    payload = {
        "model": model or _get_model(),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=timeout) as client:
        async with client.stream("POST", url, json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]


async def check_lmstudio_health(timeout: float = 1.0) -> str:
    """Return 'ok' or 'down' based on LM Studio /v1/models endpoint.

    Keep timeout short: Docker healthchecks call /health with a ~5s budget.
    A hanging host.docker.internal (LM Studio off) must not mark the API unhealthy.
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{_get_base_url()}/models")
            if resp.status_code == 200:
                return "ok"
            return "down"
    except Exception:
        return "down"


async def list_models() -> list[dict]:
    """List available models from LM Studio."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(f"{_get_base_url()}/models")
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", [])
