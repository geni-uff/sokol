"""SOKOL LLM client — OpenAI-compatible chat completions via LM Studio."""
from __future__ import annotations

import os
import httpx

DEFAULT_BASE_URL = "http://host.docker.internal:1234/v1"
DEFAULT_TIMEOUT = 120.0


def _get_base_url() -> str:
    return os.getenv("SOKOL_LMSTUDIO_BASE_URL", DEFAULT_BASE_URL)


def _get_model() -> str:
    return os.getenv("SOKOL_DEFAULT_LLM_MODEL", "change_me")


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


async def check_lmstudio_health() -> str:
    """Return 'ok' or 'down' based on LM Studio /v1/models endpoint."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
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
