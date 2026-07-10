"""add plate_detections and transcriptions tables

Revision ID: 012
Revises: 011
Create Date: 2026-07-10
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS plate_detections (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES cases(id),
            media_hash TEXT NOT NULL,
            plate_text TEXT NOT NULL,
            confidence FLOAT,
            bbox JSONB,
            label TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.create_index("ix_plate_detections_case_id", "plate_detections", ["case_id"])
    op.create_index(
        "ix_plate_detections_plate_text", "plate_detections", ["plate_text"]
    )

    op.execute("""
        CREATE TABLE IF NOT EXISTS transcriptions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id UUID NOT NULL REFERENCES cases(id),
            media_hash TEXT NOT NULL,
            text TEXT NOT NULL,
            segments JSONB,
            language TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (case_id, media_hash)
        )
    """)
    op.create_index("ix_transcriptions_case_id", "transcriptions", ["case_id"])

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_transcriptions_text_gin
        ON transcriptions USING gin(to_tsvector('portuguese', text))
    """)


def downgrade() -> None:
    op.drop_table("transcriptions")
    op.drop_table("plate_detections")
