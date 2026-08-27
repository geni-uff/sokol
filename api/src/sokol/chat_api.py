"""SOKOL chat — API endpoint for investigative chat."""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .auth import CurrentUser, get_current_user, require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatRequest(BaseModel):
    case_id: UUID
    message: str
    history: list[dict] | None = None


class ChatResponse(BaseModel):
    response: str
    tool_calls: list[dict]
    sources: list[dict]
    validation_warnings: list[str]


@router.post("/agent", response_model=ChatResponse)
def chat_agent_endpoint(
    body: ChatRequest,
    user: CurrentUser = Depends(get_current_user),
):
    """Investigative chat with tool calling and source validation."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, body.case_id, user.user_id)

        from .chat import chat_agent

        try:
            result = chat_agent(
                db,
                body.case_id,
                body.message,
                body.history,
            )
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(
                status_code=502, detail=f"Falha no Agent: {e}"
            ) from e

        return ChatResponse(**result)
