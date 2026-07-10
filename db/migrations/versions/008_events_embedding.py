"""M8: Add embedding column to events for semantic search.

Revision ID: 008_events_embedding
Revises: 007_m7_tables
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE events ADD COLUMN embedding_model_id text;
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            ALTER TABLE events ADD COLUMN embedding vector(1024);
        EXCEPTION WHEN duplicate_column THEN NULL;
        END $$;
    """)


def downgrade() -> None:
    op.drop_column("events", "embedding")
    op.drop_column("events", "embedding_model_id")
