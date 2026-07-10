"""SOKOL chunker — groups messages into embeddable chunks with context.

Chunks are created per chat, with configurable window size.
Each chunk gets a contextual header, message_ids, and tsvector.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

# Chunk configuration
CHUNK_MAX_MESSAGES = 30  # max messages per chunk
CHUNK_MAX_CHARS = 2000  # max characters per chunk
CHUNK_TIME_WINDOW_MIN = 60  # max minutes gap between messages in same chunk


def _build_chunk_header(
    chat_id: str,
    app: str,
    sender: str,
    counterpart: str,
    first_ts: datetime | None,
    last_ts: datetime | None,
) -> str:
    """Build a contextual header for the chunk."""
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


def _tsvector_text(text_content: str) -> str:
    """Prepare text for tsvector generation (Portuguese-aware)."""
    # Remove excessive whitespace
    text_content = re.sub(r"\s+", " ", text_content).strip()
    return text_content


def chunk_messages(
    db: Session,
    case_id: UUID,
    embedding_model_id: str,
    embedding_dim: int,
    embed_fn=None,
) -> int:
    """
    Create chunks from messages in the case.

    Args:
        db: Database session
        case_id: Case to chunk
        embedding_model_id: Active embedding model ID
        embedding_dim: Expected embedding dimension
        embed_fn: Callable(list[str]) -> list[list[float]] for embedding

    Returns:
        Number of chunks created
    """
    # Fetch all messages for the case, ordered by chat_id and ts
    rows = db.execute(
        text("""
            SELECT id, device_id, app, chat_id, sender, counterpart, ts, direction, text
            FROM messages
            WHERE case_id = :cid AND text IS NOT NULL AND text != ''
            ORDER BY case_id, chat_id, ts ASC
        """),
        {"cid": case_id},
    ).fetchall()

    if not rows:
        return 0

    # Group by chat_id
    chats: dict[str, list] = {}
    for row in rows:
        chat_id = row[3] or "_no_chat"
        chats.setdefault(chat_id, []).append(row)

    chunk_count = 0
    all_chunks = []  # (text, message_ids, chat_id, meta)

    for chat_id, messages in chats.items():
        # Split into windows
        windows = _split_into_windows(messages)

        for window in windows:
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
                direction = r[7] or ""
                text_content = r[8] or ""
                prefix = "→" if direction == "outgoing" else "←"
                body_parts.append(f"{prefix} {text_content}")

            chunk_text = header + "\n\n" + "\n".join(body_parts)

            meta = {
                "chat_id": chat_id,
                "app": app,
                "first_ts": first_ts.isoformat() if first_ts else None,
                "last_ts": last_ts.isoformat() if last_ts else None,
                "message_count": len(window),
            }

            all_chunks.append((chunk_text, msg_ids, meta))
            chunk_count += 1

    if not all_chunks:
        return 0

    # Batch embed
    texts = [c[0] for c in all_chunks]
    embeddings = None
    if embed_fn:
        embeddings = embed_fn(texts)
        if embeddings and len(embeddings[0]) != embedding_dim:
            raise ValueError(
                f"Embedding dimension mismatch: expected {embedding_dim}, "
                f"got {len(embeddings[0])}"
            )

    # Insert chunks
    for i, (chunk_text, msg_ids, meta) in enumerate(all_chunks):
        chunk_id = uuid4()
        embedding = embeddings[i] if embeddings else None
        now = datetime.utcnow()

        db.execute(
            text("""
                INSERT INTO chunks (id, case_id, text, embedding, embedding_model_id,
                                    embedding_dim, tsv, ref, message_ids, created_at)
                VALUES (:id, :cid, :text, :emb, :model, :dim,
                        to_tsvector('portuguese', :text), :ref, :mids, :now)
            """),
            {
                "id": chunk_id,
                "cid": case_id,
                "text": chunk_text,
                "emb": str(embedding) if embedding else None,
                "model": embedding_model_id,
                "dim": embedding_dim,
                "ref": __import__("json").dumps(meta),
                "mids": [UUID(mid) for mid in msg_ids],
                "now": now,
            },
        )

    db.commit()
    return chunk_count


def _split_into_windows(messages: list) -> list[list]:
    """Split messages into windows based on count and time gaps."""
    windows = []
    current = []
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
