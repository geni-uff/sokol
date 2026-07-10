"""image_detections table for vision service results.

Revision ID: 009
Revises: 008
Create Date: 2026-07-09
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision = "009"
down_revision = "008"


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    op.create_table(
        "image_detections",
        sa.Column(
            "id",
            sa.Text,
            primary_key=True,
            server_default=sa.text("uuid_generate_v4()::text"),
        ),
        sa.Column(
            "case_id", UUID, sa.ForeignKey("cases.id"), nullable=False, index=True
        ),
        sa.Column(
            "media_hash",
            sa.Text,
            sa.ForeignKey("media.hash"),
            nullable=False,
            index=True,
        ),
        sa.Column("model_name", sa.Text, nullable=False),
        sa.Column("class_name", sa.Text, nullable=False, index=True),
        sa.Column("class_id", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, nullable=False, index=True),
        sa.Column("bbox", JSONB, nullable=False),
        sa.Column("pipeline_version", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )

    # Indexes for common queries
    op.create_index(
        "ix_image_detections_case_class", "image_detections", ["case_id", "class_name"]
    )
    op.create_index(
        "ix_image_detections_case_confidence",
        "image_detections",
        ["case_id", "confidence"],
    )
    op.create_index(
        "ix_image_detections_media", "image_detections", ["media_hash", "class_name"]
    )


def downgrade() -> None:
    op.drop_table("image_detections")
