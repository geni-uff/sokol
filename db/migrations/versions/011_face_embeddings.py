"""add face embeddings table

Revision ID: 011
Revises: 010
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.execute("""
        CREATE TABLE face_embeddings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES cases(id),
            media_hash TEXT NOT NULL,
            bbox JSONB NOT NULL,
            embedding vector(512) NOT NULL,
            confidence FLOAT,
            label TEXT,
            age INTEGER,
            gender VARCHAR(1),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)

    op.create_index("ix_face_embeddings_case_id", "face_embeddings", ["case_id"])
    op.create_index("ix_face_embeddings_media_hash", "face_embeddings", ["media_hash"])
    op.execute("""
        CREATE INDEX ix_face_embeddings_embedding_hnsw
        ON face_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 200)
    """)


def downgrade() -> None:
    op.drop_table("face_embeddings")
