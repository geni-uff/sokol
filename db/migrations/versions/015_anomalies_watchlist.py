"""Anomalies table + watchlist_hits case_id/match_type (issues v2-06, v2-07).

Revision ID: 015
Revises: 014
"""

from alembic import op

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS anomalies (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id uuid NOT NULL REFERENCES cases(id),
            kind text NOT NULL,
            severity text NOT NULL,
            score double precision NOT NULL,
            explanation text NOT NULL,
            ref_event_ids uuid[] NOT NULL DEFAULT '{}',
            dismissed boolean NOT NULL DEFAULT false,
            created_at timestamptz NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_anomalies_case_dismissed ON anomalies (case_id, dismissed)"
    )
    op.execute(
        "ALTER TABLE watchlist_hits ADD COLUMN IF NOT EXISTS case_id uuid REFERENCES cases(id)"
    )
    op.execute(
        "ALTER TABLE watchlist_hits ADD COLUMN IF NOT EXISTS match_type text NOT NULL DEFAULT 'exact'"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_watchlist_hits_case ON watchlist_hits (case_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_watchlist_hits_case")
    op.execute("ALTER TABLE watchlist_hits DROP COLUMN IF EXISTS match_type")
    op.execute("ALTER TABLE watchlist_hits DROP COLUMN IF EXISTS case_id")
    op.execute("DROP INDEX IF EXISTS ix_anomalies_case_dismissed")
    op.execute("DROP TABLE IF EXISTS anomalies")
