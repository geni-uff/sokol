"""Backfill chunks from messages when ingest skipped chunking."""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

CHUNK_MAX_MESSAGES = 30
CHUNK_MAX_CHARS = 2000
CHUNK_TIME_WINDOW_MIN = 60


def _build_chunk_header(
    chat_id: str,
    app: str,
    sender: str,
    counterpart: str,
    first_ts: datetime | None,
    last_ts: datetime | None,
) -> str:
    parts = [f"[{app or 'Mensagem'}]"]
    if chat_id:
        parts.append(f"Conversa: {chat_id}")
    if sender and counterpart:
        parts.append(f"Participantes: {sender}, {counterpart}")
    if first_ts:
        parts.append(f"Início: {first_ts.strftime('%Y-%m-%d %H:%M')}")
    if last_ts and last_ts != first_ts:
        parts.append(f"Fim: {last_ts.strftime('%Y-%m-%d %H:%M')}")
    return " | ".join(parts)


def _split_into_windows(messages: list) -> list[list]:
    windows: list[list] = []
    current: list = []
    last_ts = None

    for msg in messages:
        ts = msg[6]
        if current and (
            len(current) >= CHUNK_MAX_MESSAGES
            or (
                last_ts
                and ts
                and (ts - last_ts).total_seconds() > CHUNK_TIME_WINDOW_MIN * 60
            )
            or sum(len(m[8] or "") for m in current) + len(msg[8] or "")
            > CHUNK_MAX_CHARS
        ):
            windows.append(current)
            current = []
        current.append(msg)
        last_ts = ts

    if current:
        windows.append(current)
    return windows


def chunk_messages(db: Session, case_id: UUID) -> int:
    """Create lexical chunks from messages. Embeddings are best-effort."""
    existing = db.execute(
        text("SELECT COUNT(*) FROM chunks WHERE case_id = :cid"),
        {"cid": case_id},
    ).scalar()
    if existing:
        return int(existing)

    rows = db.execute(
        text("""
            SELECT id, device_id, app, chat_id, sender, counterpart, ts, direction, text
            FROM messages
            WHERE case_id = :cid AND text IS NOT NULL AND text != ''
            ORDER BY chat_id, ts ASC
        """),
        {"cid": case_id},
    ).fetchall()
    if not rows:
        return 0

    chats: dict[str, list] = {}
    for row in rows:
        chat_id = row[3] or "_no_chat"
        chats.setdefault(chat_id, []).append(row)

    all_chunks: list[tuple[str, list[str], dict]] = []
    for chat_id, messages in chats.items():
        for window in _split_into_windows(messages):
            msg_ids = [str(r[0]) for r in window]
            first_ts = window[0][6]
            last_ts = window[-1][6]
            app = window[0][2] or ""
            sender = window[0][4] or ""
            counterpart = window[0][5] or ""
            header = _build_chunk_header(
                chat_id, app, sender, counterpart, first_ts, last_ts
            )
            body_parts = []
            for r in window:
                prefix = "→" if (r[7] or "") == "outgoing" else "←"
                body_parts.append(f"{prefix} {r[8] or ''}")
            chunk_text = re.sub(r"\s+", " ", header) + "\n\n" + "\n".join(body_parts)
            meta = {
                "chat_id": chat_id,
                "app": app,
                "first_ts": first_ts.isoformat() if first_ts else None,
                "last_ts": last_ts.isoformat() if last_ts else None,
                "message_count": len(window),
            }
            all_chunks.append((chunk_text, msg_ids, meta))

    if not all_chunks:
        return 0

    model_id = os.getenv(
        "SOKOL_ACTIVE_EMBED_MODEL", "Qwen/Qwen3-Embedding-0.6B"
    )
    dim = int(os.getenv("SOKOL_EMBED_DIM", "1024"))
    now = datetime.utcnow()

    for chunk_text, msg_ids, meta in all_chunks:
        db.execute(
            text("""
                INSERT INTO chunks (id, case_id, text, embedding, embedding_model_id,
                                    embedding_dim, tsv, ref, message_ids, created_at)
                VALUES (:id, :cid, :text, NULL, :model, :dim,
                        to_tsvector('portuguese', :text), CAST(:ref AS jsonb), :mids, :now)
            """),
            {
                "id": uuid4(),
                "cid": case_id,
                "text": chunk_text,
                "model": model_id,
                "dim": dim,
                "ref": json.dumps(meta),
                "mids": [UUID(mid) for mid in msg_ids],
                "now": now,
            },
        )

    db.commit()
    return len(all_chunks)
