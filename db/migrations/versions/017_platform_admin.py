"""Add users.is_platform_admin for true platform-admin gates (v2 polish).

Revision ID: 017
Revises: 016
"""

from alembic import op

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_platform_admin boolean NOT NULL DEFAULT false
    """)
    # Bootstrap: the seeded admin account is the platform admin.
    op.execute("""
        UPDATE users SET is_platform_admin = true WHERE username = 'admin'
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_platform_admin")
