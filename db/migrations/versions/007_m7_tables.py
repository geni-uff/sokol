"""M7: Add tables for reports, watchlists, pendencias, playbooks.

Revision ID: 007_m7_tables
Revises: 006_job_progress
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "007"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Bookmarks
    op.create_table(
        "bookmarks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("color", sa.Text, server_default="blue"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_bookmarks_case", "bookmarks", ["case_id"])

    # Reports
    op.create_table(
        "reports",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("generated_by", UUID(as_uuid=True), nullable=False),
        sa.Column("sha256", sa.Text, nullable=False),
        sa.Column(
            "generated_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_reports_case", "reports", ["case_id"])

    # Watchlists
    op.create_table(
        "watchlists",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("watch_type", sa.Text, nullable=False),
        sa.Column("patterns", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_watchlists_case", "watchlists", ["case_id"])

    # Watchlist hits
    op.create_table(
        "watchlist_hits",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "watchlist_id",
            UUID(as_uuid=True),
            sa.ForeignKey("watchlists.id"),
            nullable=False,
        ),
        sa.Column("event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("matched_pattern", sa.Text, nullable=False),
        sa.Column("matched_text", sa.Text, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False),
        sa.Column("acknowledged", sa.Boolean, server_default="false"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_watchlist_hits_watchlist", "watchlist_hits", ["watchlist_id"])

    # Pendências
    op.create_table(
        "pendencias",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("priority", sa.Text, server_default="medium"),
        sa.Column("status", sa.Text, server_default="open"),
        sa.Column("assigned_to", sa.Text, nullable=True),
        sa.Column("related_event_id", UUID(as_uuid=True), nullable=True),
        sa.Column("related_message_id", UUID(as_uuid=True), nullable=True),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_pendencias_case", "pendencias", ["case_id"])

    # Playbooks
    op.create_table(
        "playbooks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.Text, server_default="general"),
        sa.Column("steps", JSONB, nullable=False),
        sa.Column("is_template", sa.Boolean, server_default="false"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )

    # Playbook executions
    op.create_table(
        "playbook_executions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "playbook_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbooks.id"),
            nullable=False,
        ),
        sa.Column(
            "case_id", UUID(as_uuid=True), sa.ForeignKey("cases.id"), nullable=False
        ),
        sa.Column("status", sa.Text, server_default="pending"),
        sa.Column("current_step", sa.Text, nullable=True),
        sa.Column("results", JSONB, server_default="{}"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index("ix_playbook_executions_case", "playbook_executions", ["case_id"])

    # Playbook results
    op.create_table(
        "playbook_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "execution_id",
            UUID(as_uuid=True),
            sa.ForeignKey("playbook_executions.id"),
            nullable=False,
        ),
        sa.Column("step_id", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("output", JSONB, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_playbook_results_execution", "playbook_results", ["execution_id"]
    )


def downgrade() -> None:
    op.drop_table("playbook_results")
    op.drop_table("playbook_executions")
    op.drop_table("playbooks")
    op.drop_table("pendencias")
    op.drop_table("watchlist_hits")
    op.drop_table("watchlists")
    op.drop_table("reports")
    op.drop_table("bookmarks")
