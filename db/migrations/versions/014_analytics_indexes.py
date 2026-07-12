"""Add analytics indexes for cross-case queries and aggregations.

Revision ID: 014
Revises: 013
Create Date: 2026-07-12
"""

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Cross-case entity lookup by (kind, value) without case_id prefix.
    # The existing ix_entities_case_kind_value starts with case_id so it
    # cannot be used for cross-case scans.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_entities_kind_value "
        "ON entities (kind, value)"
    )

    # Filter messages by sender within a case (contact-frequency queries).
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_messages_case_sender "
        "ON messages (case_id, sender)"
    )

    # Filter events by kind within a case with time ordering (heatmaps,
    # anomaly detection, analytics).
    # ix_events_case_ts only covers (case_id, ts) — kind is not included.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_events_case_kind_ts "
        "ON events (case_id, kind, ts)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_events_case_kind_ts")
    op.execute("DROP INDEX IF EXISTS ix_messages_case_sender")
    op.execute("DROP INDEX IF EXISTS ix_entities_kind_value")
