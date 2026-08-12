"""Case comments table (issue v2-08).

Revision ID: 016
Revises: 015
"""

from alembic import op

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS case_comments (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            case_id uuid NOT NULL REFERENCES cases(id),
            author_user_id uuid NOT NULL REFERENCES users(id),
            target_kind text NOT NULL
                CHECK (target_kind IN ('case', 'event', 'media')),
            target_id uuid NULL,
            body text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            edited_at timestamptz NULL,
            deleted boolean NOT NULL DEFAULT false,
            CONSTRAINT case_comments_target_id_for_case
                CHECK (
                    (target_kind = 'case' AND target_id IS NULL)
                    OR (target_kind <> 'case' AND target_id IS NOT NULL)
                )
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_case_comments_target "
        "ON case_comments (case_id, target_kind, target_id)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_case_comments_target")
    op.execute("DROP TABLE IF EXISTS case_comments")
