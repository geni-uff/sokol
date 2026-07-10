"""SOKOL embed — OpenAI-compatible embedding service."""
from __future__ import annotations

import os
import time
from contextlib import asynccontextmanager

import numpy as np
import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer

SOKOL_VERSION = "0.1.0"

# ── Configuration ──────────────────────────────────────────────────────────
DEFAULT_MODEL = os.getenv("SOKOL_DEFAULT_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")
ACTIVE_MODEL = os.getenv("SOKOL_ACTIVE_EMBED_MODEL", DEFAULT_MODEL)
EMBED_DIM = int(os.getenv("SOKOL_EMBED_DIM", "1024"))
GPU_DEVICE = os.getenv("SOKOL_GPU_AUX", "auto")

_model: SentenceTransformer | None = None


def _resolve_device() -> str:
    if GPU_DEVICE != "auto":
        try:
            idx = int(GPU_DEVICE)
            return f"cuda:{idx}"
        except ValueError:
            pass
    if torch.cuda.is_available():
        return "cuda:0"
    return "cpu"


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    device = _resolve_device()
    print(f"Loading embedding model {ACTIVE_MODEL} on {device}...")
    _model = SentenceTransformer(ACTIVE_MODEL, device=device)
    print(f"Model loaded. Dimension: {_model.get_sentence_embedding_dimension()}")
    yield
    _model = None


app = FastAPI(title="SOKOL Embed", version=SOKOL_VERSION, lifespan=lifespan)


# ── OpenAI-compatible schemas ─────────────────────────────────────────────
class EmbeddingRequest(BaseModel):
    input: str | list[str]
    model: str | None = None
    encoding_format: str | None = None


class EmbeddingObject(BaseModel):
    object: str = "embedding"
    embedding: list[float]
    index: int


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: list[EmbeddingObject]
    model: str
    usage: EmbeddingUsage


# ── Endpoints ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    if _model is None:
        return {"status": "loading", "version": SOKOL_VERSION}
    return {
        "status": "ok",
        "version": SOKOL_VERSION,
        "model": ACTIVE_MODEL,
        "dimension": _model.get_sentence_embedding_dimension(),
        "device": str(_model.device),
    }


@app.post("/v1/embeddings", response_model=EmbeddingResponse)
def create_embeddings(body: EmbeddingRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded yet")

    texts = body.input if isinstance(body.input, list) else [body.input]
    if not texts:
        raise HTTPException(status_code=400, detail="Empty input")

    t0 = time.time()
    embeddings = _model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    elapsed = time.time() - t0

    # Validate dimension
    actual_dim = embeddings.shape[1]
    if actual_dim != EMBED_DIM:
        raise HTTPException(
            status_code=500,
            detail=f"Dimension mismatch: expected {EMBED_DIM}, got {actual_dim}",
        )

    data = [
        EmbeddingObject(embedding=emb.tolist(), index=i)
        for i, emb in enumerate(embeddings)
    ]

    # Rough token count (words approximation)
    total_words = sum(len(t.split()) for t in texts)

    return EmbeddingResponse(
        data=data,
        model=body.model or ACTIVE_MODEL,
        usage=EmbeddingUsage(prompt_tokens=total_words, total_tokens=total_words),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
