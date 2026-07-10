"""add face embeddings table

Revision ID: 011
Revises: 010
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "face_embeddings",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "case_id",
            sa.dialects.postgresql.UUID(),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column("media_hash", sa.Text(), nullable=False),
        sa.Column("bbox", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("embedding", Vector(512), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("age", sa.Integer(), nullable=True),
        sa.Column("gender", sa.String(1), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("ix_face_embeddings_case_id", "face_embeddings", ["case_id"])
    op.create_index("ix_face_embeddings_media_hash", "face_embeddings", ["media_hash"])
    op.create_index(
        "ix_face_embeddings_embedding_hnsw",
        "face_embeddings",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_with={"m": "16", "ef_construction": "200"},
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_table("face_embeddings")
