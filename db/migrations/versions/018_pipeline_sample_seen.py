"""Track which media hashes a sample pipeline batch already consumed.

Revision ID: 018
Revises: 017
"""

from alembic import op

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE pipeline_sample_seen (
            case_id UUID NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
            media_hash TEXT NOT NULL,
            kind TEXT NOT NULL,
            seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (case_id, media_hash, kind)
        )
    """)
    op.execute(
        "CREATE INDEX ix_pipeline_sample_seen_case_kind ON pipeline_sample_seen (case_id, kind)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_pipeline_sample_seen_case_kind")
    op.execute("DROP TABLE IF EXISTS pipeline_sample_seen")
