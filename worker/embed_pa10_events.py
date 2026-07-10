"""Embed PA10 events for semantic search."""

import os
import sys
from uuid import UUID

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from event_embedder import embed_events

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol"
)
EMBED_BASE_URL = os.getenv("SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1")
EMBED_MODEL_ID = os.getenv(
    "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
)
EMBED_DIM = int(os.getenv("SOKOL_EMBED_DIM", "1024"))

CASE_ID = UUID("445f495a-4dea-40d3-b845-90ed3c4f5b1b")  # PA10 case


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts using LM Studio."""
    embed_url = (
        f"{EMBED_BASE_URL}/embeddings"
        if EMBED_BASE_URL.endswith("/v1")
        else f"{EMBED_BASE_URL}/v1/embeddings"
    )
    resp = httpx.post(
        embed_url,
        json={"input": texts, "model": EMBED_MODEL_ID},
        timeout=120.0,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def main():
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        # Count events without embeddings
        count = db.execute(
            text("""
                SELECT COUNT(*) FROM events
                WHERE case_id = :case_id AND embedding IS NULL
            """),
            {"case_id": str(CASE_ID)},
        ).scalar()

        print(f"PA10 case: {count} events without embeddings")

        if count == 0:
            print("All events already embedded.")
            return

        print(f"Embedding events using {EMBED_MODEL_ID}...")
        embedded = embed_events(
            db=db,
            case_id=CASE_ID,
            embedding_model_id=EMBED_MODEL_ID,
            embedding_dim=EMBED_DIM,
            embed_fn=embed_batch,
        )
        print(f"Embedded {embedded} events.")


if __name__ == "__main__":
    main()
