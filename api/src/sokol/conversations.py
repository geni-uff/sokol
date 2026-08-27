"""SOKOL — Conversations: browse messages table by case."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import text

from .app_filter import app_filter_sql, app_filter_value
from .auth import CurrentUser, get_current_user
from .cases import require_case_member
from .db import get_session_factory

router = APIRouter(prefix="/conversations", tags=["conversations"])


class MessageItem(BaseModel):
    id: str
    app: str | None
    chat_id: str | None
    sender: str | None
    counterpart: str | None
    ts: str | None
    direction: str | None
    text: str | None
    media_hash: str | None
    is_forwarded: bool | None


class MessagesResponse(BaseModel):
    messages: list[MessageItem]
    total: int
    case_id: str


class ChatSummary(BaseModel):
    chat_id: str | None
    app: str | None
    participant: str | None
    message_count: int
    first_ts: str | None
    last_ts: str | None


@router.get("/chats", response_model=list[ChatSummary])
def list_chats(
    case_id: UUID,
    app: str | None = None,
    user: CurrentUser = Depends(get_current_user),
):
    """List distinct conversations (chat_id) in a case."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        conditions = ["case_id = :cid"]
        bind: dict = {"cid": case_id}
        if app:
            conditions.append(app_filter_sql("app"))
            bind["app"] = app_filter_value(app)

        where = " AND ".join(conditions)
        rows = db.execute(
            text(f"""
                SELECT
                    chat_id,
                    (ARRAY_AGG(app ORDER BY ts DESC NULLS LAST)
                     FILTER (WHERE app IS NOT NULL))[1] AS app,
                    (ARRAY_AGG(counterpart ORDER BY ts DESC NULLS LAST)
                     FILTER (WHERE counterpart IS NOT NULL))[1] AS participant,
                    COUNT(*) AS message_count,
                    MIN(ts)::text AS first_ts,
                    MAX(ts)::text AS last_ts
                FROM messages m
                WHERE {where}
                GROUP BY chat_id
                ORDER BY MAX(ts) DESC NULLS LAST
                LIMIT 200
            """),
            bind,
        ).fetchall()

    return [
        ChatSummary(
            chat_id=r[0],
            app=r[1],
            participant=r[2],
            message_count=r[3],
            first_ts=r[4],
            last_ts=r[5],
        )
        for r in rows
    ]


@router.get("/messages", response_model=MessagesResponse)
def list_messages(
    case_id: UUID,
    app: str | None = None,
    chat_id: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: CurrentUser = Depends(get_current_user),
):
    """List messages in a case, optionally filtered by app/chat_id/search."""
    factory = get_session_factory()
    with factory() as db:
        require_case_member(db, case_id, user.user_id)

        conditions = ["case_id = :cid"]
        bind: dict = {"cid": case_id, "limit": limit, "offset": offset}

        if app:
            conditions.append(app_filter_sql("app"))
            bind["app"] = app_filter_value(app)
        if chat_id:
            conditions.append("chat_id = :chat_id")
            bind["chat_id"] = chat_id
        if q:
            conditions.append("text ILIKE :q")
            bind["q"] = f"%{q}%"

        where = " AND ".join(conditions)

        total = db.execute(
            text(f"""
                SELECT COUNT(*) FROM (
                    SELECT DISTINCT ON (COALESCE(chat_id,''), ts, COALESCE(text,''), COALESCE(direction,''), COALESCE(sender,''))
                        id
                    FROM messages
                    WHERE {where}
                    ORDER BY COALESCE(chat_id,''), ts, COALESCE(text,''), COALESCE(direction,''), COALESCE(sender,''), id
                ) d
            """),
            bind,
        ).scalar()

        rows = db.execute(
            text(f"""
                SELECT id, app, chat_id, sender, counterpart,
                       ts, direction, text, media_hash, is_forwarded
                FROM (
                    SELECT DISTINCT ON (COALESCE(chat_id,''), ts, COALESCE(text,''), COALESCE(direction,''), COALESCE(sender,''))
                        id, app, chat_id, sender, counterpart,
                        ts, direction, text, media_hash, is_forwarded
                    FROM messages
                    WHERE {where}
                    ORDER BY COALESCE(chat_id,''), ts, COALESCE(text,''), COALESCE(direction,''), COALESCE(sender,''), id
                ) dedup
                ORDER BY ts ASC NULLS LAST
                LIMIT :limit OFFSET :offset
            """),
            bind,
        ).fetchall()

    msgs = [
        MessageItem(
            id=str(r[0]),
            app=r[1],
            chat_id=r[2],
            sender=r[3],
            counterpart=r[4],
            ts=r[5].isoformat() if r[5] else None,
            direction=r[6],
            text=r[7],
            media_hash=r[8],
            is_forwarded=r[9],
        )
        for r in rows
    ]
    return MessagesResponse(messages=msgs, total=total, case_id=str(case_id))
