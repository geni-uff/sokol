"""SOKOL search — API endpoints for hybrid search."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/search", tags=["search"])


class SearchRequest(BaseModel):
    case_id: UUID
    query: str
    k: int = 20
    mode: str = "hybrid"  # "vector", "lexical", "exact", "hybrid"


class SearchResultItem(BaseModel):
    chunk_id: str
    text: str
    score: float
    ref: dict
    message_ids: list[str]
    source_type: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResultItem]
    total: int
    mode: str
    embedding_model_id: str | None = None


@router.post("/scan", response_model=SearchResponse)
def search_scan(
    body: SearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Hybrid search across chunks (vector + lexical + exact)."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, body.case_id, user.user_id)

        from .search_core import search_hybrid

        result = search_hybrid(
            db,
            body.case_id,
            body.query,
            body.k,
            body.mode,
        )

        return SearchResponse(
            query=result.query,
            results=[
                SearchResultItem(
                    chunk_id=r.chunk_id,
                    text=r.text,
                    score=r.score,
                    ref=r.ref,
                    message_ids=r.message_ids,
                    source_type=r.source_type,
                )
                for r in result.results
            ],
            total=result.total,
            mode=result.mode,
            embedding_model_id=result.embedding_model_id,
        )


@router.post("/exact", response_model=SearchResponse)
def search_exact(
    body: SearchRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Exact text search with unaccent normalization."""
    body.mode = "exact"
    return search_scan(body, user)
