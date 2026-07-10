"""Add users table for authentication

Revision ID: 002
Revises: 001
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("password_hash", sa.Text, nullable=False),
        sa.Column("display_name", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # Seed default admin user (password: admin — change in production)
    from argon2 import PasswordHasher
    ph = PasswordHasher()
    import hashlib
    from datetime import datetime, timezone
    from uuid import uuid4

    admin_id = uuid4()
    pw_hash = ph.hash("admin")
    now = datetime.now(timezone.utc)
    op.execute(f"""
        INSERT INTO users (id, username, password_hash, display_name, created_at)
        VALUES ('{admin_id}', 'admin', '{pw_hash}', 'Administrator', '{now.isoformat()}')
    """)


def downgrade() -> None:
    op.drop_table("users")
