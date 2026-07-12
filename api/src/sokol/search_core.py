"""SOKOL search — hybrid search (vector + lexical + exact) with RRF and rerank."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session


@dataclass
class SearchResult:
    chunk_id: str
    text: str
    score: float
    ref: dict
    message_ids: list[str]
    source_type: str  # "vector", "lexical", "exact", "hybrid"
    highlight: str | None = None


@dataclass
class SearchResponse:
    query: str
    results: list[SearchResult]
    total: int
    mode: str  # "vector", "lexical", "exact", "hybrid"
    embedding_model_id: str | None = None


def _get_embed_config() -> tuple[str, str, int]:
    """Get active embedding config: (base_url, model_id, dim)."""
    import os

    base_url = os.getenv("SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1")
    model_id = os.getenv(
        "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
    )
    dim = int(os.getenv("SOKOL_EMBED_DIM", "1024"))
    return base_url, model_id, dim


def _embed_query(query: str) -> list[float] | None:
    """Embed a query string using the active embedding model."""
    try:
        base_url, model_id, _ = _get_embed_config()
        # base_url may already include /v1, handle both cases
        embed_url = (
            f"{base_url}/embeddings"
            if base_url.endswith("/v1")
            else f"{base_url}/v1/embeddings"
        )
        resp = httpx.post(
            embed_url,
            json={"input": query, "model": model_id},
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["data"][0]["embedding"]
    except Exception:
        return None


def _get_active_model_id() -> str:
    import os

    return os.getenv("SOKOL_ACTIVE_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B")


def search_vector(
    db: Session,
    case_id: UUID,
    query: str,
    k: int = 20,
    model_id: str | None = None,
) -> list[SearchResult]:
    """Vector search using pgvector cosine similarity."""
    embedding = _embed_query(query)
    if embedding is None:
        return []

    model_id = model_id or _get_active_model_id()

    rows = db.execute(
        text("""
            SELECT id, text, ref, message_ids,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM chunks
            WHERE case_id = :cid
              AND embedding_model_id = :model
              AND embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :k
        """),
        {"cid": case_id, "emb": str(embedding), "model": model_id, "k": k},
    ).fetchall()

    return [
        SearchResult(
            chunk_id=str(r[0]),
            text=r[1],
            score=float(r[4]),
            ref=r[2] if isinstance(r[2], dict) else json.loads(r[2]) if r[2] else {},
            message_ids=[str(mid) for mid in (r[3] or [])],
            source_type="vector",
        )
        for r in rows
    ]


def search_lexical(
    db: Session,
    case_id: UUID,
    query: str,
    k: int = 20,
) -> list[SearchResult]:
    """Lexical search using tsvector with ts_rank."""
    rows = db.execute(
        text("""
            SELECT id, text, ref, message_ids,
                   ts_rank(tsv, plainto_tsquery('portuguese', :query)) AS rank
            FROM chunks
            WHERE case_id = :cid
              AND tsv @@ plainto_tsquery('portuguese', :query)
            ORDER BY rank DESC
            LIMIT :k
        """),
        {"cid": case_id, "query": query, "k": k},
    ).fetchall()

    return [
        SearchResult(
            chunk_id=str(r[0]),
            text=r[1],
            score=float(r[4]),
            ref=r[2] if isinstance(r[2], dict) else json.loads(r[2]) if r[2] else {},
            message_ids=[str(mid) for mid in (r[3] or [])],
            source_type="lexical",
        )
        for r in rows
    ]


def search_exact(
    db: Session,
    case_id: UUID,
    query: str,
    k: int = 20,
) -> list[SearchResult]:
    """Exact text search with unaccent normalization."""
    normalized = query.strip().lower()
    rows = db.execute(
        text("""
            SELECT id, text, ref, message_ids,
                   ts_rank(tsv, plainto_tsquery('portuguese', :query)) AS rank
            FROM chunks
            WHERE case_id = :cid
              AND unaccent(lower(text)) LIKE unaccent(:pattern)
            ORDER BY rank DESC
            LIMIT :k
        """),
        {"cid": case_id, "query": query, "pattern": f"%{normalized}%", "k": k},
    ).fetchall()

    return [
        SearchResult(
            chunk_id=str(r[0]),
            text=r[1],
            score=float(r[4]),
            ref=r[2] if isinstance(r[2], dict) else json.loads(r[2]) if r[2] else {},
            message_ids=[str(mid) for mid in (r[3] or [])],
            source_type="exact",
        )
        for r in rows
    ]


def _rrf_fusion(
    result_lists: list[list[SearchResult]], k: int = 60
) -> list[SearchResult]:
    """Reciprocal Rank Fusion across multiple result lists."""
    scores: dict[str, float] = {}
    result_map: dict[str, SearchResult] = {}

    for results in result_lists:
        for rank, r in enumerate(results):
            key = r.chunk_id
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            if key not in result_map:
                result_map[key] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        SearchResult(
            chunk_id=key,
            text=result_map[key].text,
            score=score,
            ref=result_map[key].ref,
            message_ids=result_map[key].message_ids,
            source_type="hybrid",
        )
        for key, score in ranked
    ]


def _rerank(
    query: str, results: list[SearchResult], top_n: int = 10
) -> list[SearchResult]:
    """Rerank results by relevance score combination and query matching."""
    if not results:
        return results

    import re

    # Normalize query for matching
    query_terms = set(re.findall(r'\b\w+\b', query.lower()))
    query_pattern = re.compile(r'\b' + '|'.join(re.escape(t) for t in query_terms) + r'\b', re.IGNORECASE)

    # Rerank with improved scoring
    reranked = []
    for result in results:
        # Start with base score (normalized 0-1)
        base_score = min(result.score, 1.0)

        # Boost for exact term matches in text
        text_matches = len(query_pattern.findall(result.text))
        match_boost = min(text_matches * 0.1, 0.3)

        # Boost for query in source (higher relevance)
        source_boost = 0.2 if result.source_type == "exact" else (0.1 if result.source_type == "lexical" else 0.05)

        # Combined score
        final_score = base_score + match_boost + source_boost

        # Update result with new score
        result.score = final_score
        reranked.append(result)

    # Sort by reranked score
    reranked.sort(key=lambda r: r.score, reverse=True)

    return reranked[:top_n]


def search_hybrid(
    db: Session,
    case_id: UUID,
    query: str,
    k: int = 20,
    mode: str = "hybrid",
) -> SearchResponse:
    """
    Hybrid search combining vector, lexical, and exact.

    Args:
        mode: "vector", "lexical", "exact", or "hybrid"
    """
    model_id = _get_active_model_id()

    if mode == "vector":
        results = search_vector(db, case_id, query, k)
    elif mode == "lexical":
        results = search_lexical(db, case_id, query, k)
    elif mode == "exact":
        results = search_exact(db, case_id, query, k)
    else:  # hybrid
        vec_results = search_vector(db, case_id, query, k)
        lex_results = search_lexical(db, case_id, query, k)
        exa_results = search_exact(db, case_id, query, k)
        results = _rrf_fusion([vec_results, lex_results, exa_results])
        results = _rerank(query, results)

    return SearchResponse(
        query=query,
        results=results[:k],
        total=len(results),
        mode=mode,
        embedding_model_id=model_id,
    )
