"""SOKOL event embedder — generates embeddings for event summaries for semantic search."""

from __future__ import annotations

from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

BATCH_SIZE = 64


def embed_events(
    db: Session,
    case_id: UUID,
    embedding_model_id: str,
    embedding_dim: int,
    embed_fn,
) -> int:
    """Generate embeddings for all events in a case that lack them.

    Returns the number of events embedded.
    """
    rows = db.execute(
        text("""
            SELECT id, summary
            FROM events
            WHERE case_id = :case_id
              AND embedding IS NULL
            ORDER BY ts NULLS LAST
        """),
        {"case_id": str(case_id)},
    ).fetchall()

    if not rows:
        return 0

    total = 0
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        event_ids = [r[0] for r in batch]
        summaries = [r[1] for r in batch]

        embeddings = embed_fn(summaries)

        for event_id, emb in zip(event_ids, embeddings):
            emb_str = "[" + ",".join(str(v) for v in emb) + "]"
            db.execute(
                text("""
                    UPDATE events
                    SET embedding = CAST(:embedding AS vector),
                        embedding_model_id = :model_id
                    WHERE id = :id
                """),
                {
                    "embedding": emb_str,
                    "model_id": embedding_model_id,
                    "id": event_id,
                },
            )
            total += 1

        db.commit()

    return total
