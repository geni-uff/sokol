"""Revoke UPDATE/DELETE on audit_log from application role

Revision ID: 003
Revises: 002
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Revoke UPDATE and DELETE on audit_log from the application role
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM sokol")
    # Also revoke from public to prevent direct SQL access
    op.execute("REVOKE UPDATE, DELETE ON audit_log FROM PUBLIC")


def downgrade() -> None:
    op.execute("GRANT UPDATE, DELETE ON audit_log TO sokol")
