"""Add ocr_results table for document text extraction.

Revision ID: 013
Revises: 012
Create Date: 2026-07-10
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE ocr_results (
            id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            case_id     UUID NOT NULL REFERENCES cases(id),
            media_hash  TEXT NOT NULL,
            text        TEXT NOT NULL,
            confidence  DOUBLE PRECISION,
            language    TEXT,
            lines       JSONB DEFAULT '[]',
            created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (case_id, media_hash)
        )
    """)
    op.create_index("ix_ocr_results_case_id", "ocr_results", ["case_id"])


def downgrade() -> None:
    op.drop_index("ix_ocr_results_case_id", table_name="ocr_results")
    op.drop_table("ocr_results")
