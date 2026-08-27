"""Fill NULL embeddings on chunks and events for Agent semantic search.

Runs in the worker (kind=embed). Never on the API request thread — 30k events
would block uvicorn the same way media extraction already does.

Author: Matheus C. Pestana
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

try:
    from .event_embedder import embed_events
    from .chunker import chunk_messages
except ImportError:
    from event_embedder import embed_events
    from chunker import chunk_messages

CHUNK_BATCH = 16
# CPU encode of 20k-char chunks times out; semantic search only needs a prefix.
MAX_EMBED_CHARS = int(os.getenv("SOKOL_EMBED_MAX_CHARS", "512"))
EMBED_HTTP_BATCH = int(os.getenv("SOKOL_EMBED_HTTP_BATCH", "4"))
EMBED_TIMEOUT = float(os.getenv("SOKOL_EMBED_TIMEOUT", "180"))
ProgressFn = Callable[[str, int, int], None]
logger = logging.getLogger("sokol.worker.embed")


def embed_config() -> tuple[str, str, int]:
    base = os.getenv("SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1")
    model = os.getenv(
        "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
    )
    dim = int(os.getenv("SOKOL_EMBED_DIM", "1024"))
    return base, model, dim


def _embeddings_url(base_url: str) -> str:
    return (
        f"{base_url}/embeddings"
        if base_url.endswith("/v1")
        else f"{base_url}/v1/embeddings"
    )


def _embed_urls(primary_base: str) -> list[str]:
    """Primary first; sokol-embed if LM Studio cannot load the Qwen 0.6B model.

    LM Studio often fails to load the embedding GGUF while a large LLM occupies
    VRAM. sokol-embed (:8001) already serves the same 1024-dim model on CPU.
    Set SOKOL_EMBED_FALLBACK_URL= to disable.
    """
    urls = [_embeddings_url(primary_base)]
    fallback = os.getenv("SOKOL_EMBED_FALLBACK_URL", "http://localhost:8001/v1").strip()
    if fallback:
        fb = _embeddings_url(fallback)
        if fb not in urls:
            urls.append(fb)
    return urls


def _clip_texts(texts: list[str]) -> list[str]:
    out: list[str] = []
    for t in texts:
        s = t if (t and t.strip()) else "."
        out.append(s[:MAX_EMBED_CHARS])
    return out


def make_embed_fn(base_url: str, model_id: str, expected_dim: int):
    urls = _embed_urls(base_url)
    chosen: dict[str, str | None] = {"url": None}
    dead: set[str] = set()

    def _embed_once(cleaned: list[str]) -> list[list[float]]:
        payload = {"input": cleaned, "model": model_id}
        last_detail = ""
        candidates = [chosen["url"]] if chosen["url"] else urls
        for url in candidates:
            if url is None or url in dead:
                continue
            try:
                resp = httpx.post(url, json=payload, timeout=EMBED_TIMEOUT)
            except httpx.TimeoutException as exc:
                dead.add(url)
                last_detail = f"timeout {url}: {exc}"
                logger.warning("Embedding timeout em %s, tentando o próximo", url)
                continue
            if resp.is_success:
                data = resp.json()
                vectors = [item["embedding"] for item in data["data"]]
                if vectors and len(vectors[0]) != expected_dim:
                    raise ValueError(
                        f"Dimensão do embedding {len(vectors[0])} ≠ {expected_dim}"
                    )
                if chosen["url"] != url:
                    logger.info("Embeddings via %s", url)
                    chosen["url"] = url
                return vectors
            last_detail = f"{resp.status_code} {url}: {resp.text[:300]}"
            if resp.status_code in (400, 404, 503):
                dead.add(url)
                logger.warning("Embedding recusado em %s (%s)", url, resp.status_code)
                continue
            raise httpx.HTTPStatusError(
                last_detail,
                request=resp.request,
                response=resp,
            )
        raise RuntimeError(f"Nenhum endpoint de embedding respondeu: {last_detail}")

    def _embed(texts: list[str]) -> list[list[float]]:
        cleaned = _clip_texts(texts)
        if len(cleaned) <= EMBED_HTTP_BATCH:
            return _embed_once(cleaned)
        out: list[list[float]] = []
        for i in range(0, len(cleaned), EMBED_HTTP_BATCH):
            out.extend(_embed_once(cleaned[i : i + EMBED_HTTP_BATCH]))
        return out

    return _embed


def pending_counts(db: Session, case_id: UUID) -> dict[str, int]:
    chunks_total = db.execute(
        text("SELECT count(*) FROM chunks WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    chunks_null = db.execute(
        text(
            "SELECT count(*) FROM chunks WHERE case_id = :cid AND embedding IS NULL"
        ),
        {"cid": case_id},
    ).scalar() or 0
    events_total = db.execute(
        text("SELECT count(*) FROM events WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar() or 0
    events_null = db.execute(
        text(
            "SELECT count(*) FROM events WHERE case_id = :cid AND embedding IS NULL"
        ),
        {"cid": case_id},
    ).scalar() or 0
    return {
        "chunks_total": int(chunks_total),
        "chunks_pending": int(chunks_null),
        "events_total": int(events_total),
        "events_pending": int(events_null),
    }


def embed_chunks(
    db: Session,
    case_id: UUID,
    embedding_model_id: str,
    embed_fn,
    on_progress: ProgressFn | None = None,
) -> int:
    rows = db.execute(
        text("""
            SELECT id, text
            FROM chunks
            WHERE case_id = :cid AND embedding IS NULL
            ORDER BY created_at
        """),
        {"cid": str(case_id)},
    ).fetchall()
    if not rows:
        return 0

    total = 0
    n = len(rows)
    for i in range(0, n, CHUNK_BATCH):
        batch = rows[i : i + CHUNK_BATCH]
        ids = [r[0] for r in batch]
        texts = [r[1] or "." for r in batch]
        vectors = embed_fn(texts)
        for chunk_id, emb in zip(ids, vectors):
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            db.execute(
                text("""
                    UPDATE chunks
                    SET embedding = CAST(:embedding AS vector),
                        embedding_model_id = :model_id
                    WHERE id = :id AND case_id = :cid
                """),
                {
                    "embedding": emb_str,
                    "model_id": embedding_model_id,
                    "id": chunk_id,
                    "cid": case_id,
                },
            )
            total += 1
        db.commit()
        if on_progress:
            on_progress("chunks", total, n)
    return total


def run_embed_case(
    db: Session,
    case_id: UUID,
    on_progress: ProgressFn | None = None,
) -> dict[str, int]:
    base, model_id, dim = embed_config()
    embed_fn = make_embed_fn(base, model_id, dim)

    counts = pending_counts(db, case_id)
    if counts["chunks_total"] == 0:
        created = chunk_messages(
            db,
            case_id,
            embedding_model_id=model_id,
            embedding_dim=dim,
            embed_fn=None,
        )
        counts["chunks_total"] = created
        counts["chunks_pending"] = created

    chunks_done = embed_chunks(
        db, case_id, model_id, embed_fn, on_progress=on_progress
    )

    def _events_progress(done: int, total: int) -> None:
        if on_progress:
            on_progress("events", done, total)

    events_done = _embed_events_with_progress(
        db, case_id, model_id, dim, embed_fn, _events_progress
    )
    return {
        "chunks_embedded": chunks_done,
        "events_embedded": events_done,
        **pending_counts(db, case_id),
    }


def _embed_events_with_progress(
    db: Session,
    case_id: UUID,
    model_id: str,
    dim: int,
    embed_fn,
    on_progress: Callable[[int, int], None] | None,
) -> int:
    total_pending = db.execute(
        text(
            "SELECT count(*) FROM events WHERE case_id = :cid AND embedding IS NULL"
        ),
        {"cid": str(case_id)},
    ).scalar() or 0
    if not total_pending:
        return 0

    done_holder = {"n": 0}

    def wrapping_embed(texts: list[str]) -> list[list[float]]:
        out = embed_fn(texts)
        done_holder["n"] += len(texts)
        if on_progress:
            on_progress(done_holder["n"], int(total_pending))
        return out

    return embed_events(
        db,
        case_id,
        embedding_model_id=model_id,
        embedding_dim=dim,
        embed_fn=wrapping_embed,
    )
