"""Create complete SOKOL schema

Revision ID: 001
Revises: None
Create Date: 2026-07-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID, TSVECTOR, ARRAY

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Extensions ───────────────────────────────────────────────────────
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # ── cases ────────────────────────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("legal_ref", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("retention_policy", sa.Text),
        sa.Column(
            "reference_timezone",
            sa.Text,
            nullable=False,
            server_default="America/Sao_Paulo",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── case_members ─────────────────────────────────────────────────────
    op.create_table(
        "case_members",
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            primary_key=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("role", sa.Text, nullable=False),
    )

    # ── documents ────────────────────────────────────────────────────────
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column("title", sa.Text),
        sa.Column("source_type", sa.Text, nullable=False),
        sa.Column("source_uri", sa.Text),
        sa.Column("sha256", sa.Text),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_case_id", "documents", ["case_id"])

    # ── artifacts ────────────────────────────────────────────────────────
    op.create_table(
        "artifacts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column(
            "document_id",
            UUID(as_uuid=True),
            sa.ForeignKey("documents.id"),
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("source_member", sa.Text),
        sa.Column("media_hash", sa.Text),
        sa.Column("mime_type", sa.Text),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column(
            "meta",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_artifacts_case_id", "artifacts", ["case_id"])
    op.create_index("ix_artifacts_document_id", "artifacts", ["document_id"])

    # ── media ────────────────────────────────────────────────────────────
    op.create_table(
        "media",
        sa.Column("hash", sa.Text, primary_key=True),
        sa.Column("mime_type", sa.Text),
        sa.Column("size_bytes", sa.BigInteger),
        sa.Column("storage_ref", JSONB, nullable=False),
        sa.Column("thumbnail_ref", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # ── messages ─────────────────────────────────────────────────────────
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column("device_id", sa.Text),
        sa.Column("app", sa.Text),
        sa.Column("chat_id", sa.Text),
        sa.Column("sender", sa.Text),
        sa.Column("counterpart", sa.Text),
        sa.Column("ts", sa.DateTime(timezone=True)),
        sa.Column("direction", sa.Text),
        sa.Column("text", sa.Text),
        sa.Column(
            "media_hash",
            sa.Text,
            sa.ForeignKey("media.hash"),
        ),
        sa.Column("is_forwarded", sa.Boolean),
        sa.Column(
            "meta",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index("ix_messages_case_id", "messages", ["case_id"])
    op.create_index(
        "ix_messages_case_chat_ts",
        "messages",
        ["case_id", "chat_id", "ts"],
    )

    # ── events (uses geography type — must use raw SQL) ──────────────────
    op.execute("""
        CREATE TABLE events (
            id          UUID PRIMARY KEY,
            case_id     UUID NOT NULL REFERENCES cases(id),
            device_id   TEXT,
            ts          TIMESTAMPTZ,
            tz_original TEXT,
            kind        TEXT NOT NULL,
            actor       TEXT,
            counterpart TEXT,
            app         TEXT,
            ref_table   TEXT NOT NULL,
            ref_id      UUID NOT NULL,
            summary     TEXT NOT NULL,
            geo         GEOGRAPHY,
            meta        JSONB NOT NULL DEFAULT '{}'
        )
    """)
    op.create_index("ix_events_case_id", "events", ["case_id"])
    op.create_index("ix_events_case_ts", "events", ["case_id", "ts"])
    op.execute("CREATE INDEX ix_events_geo ON events USING GIST (geo)")

    # ── chunks (uses vector type — must use raw SQL) ────────────────────
    op.execute("""
        CREATE TABLE chunks (
            id                UUID PRIMARY KEY,
            case_id           UUID NOT NULL REFERENCES cases(id),
            artifact_id       UUID REFERENCES artifacts(id),
            text              TEXT NOT NULL,
            embedding         VECTOR(1024),
            embedding_model_id TEXT NOT NULL,
            embedding_dim     INT NOT NULL,
            tsv               TSVECTOR,
            ref               JSONB NOT NULL,
            page_start        INT,
            page_end          INT,
            bbox              JSONB,
            message_ids       UUID[],
            created_at        TIMESTAMPTZ NOT NULL
        )
    """)
    op.create_index("ix_chunks_case_id", "chunks", ["case_id"])
    op.execute("""
        CREATE INDEX ix_chunks_embedding_hnsw ON chunks
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 200)
    """)
    op.execute("CREATE INDEX ix_chunks_tsv_gin ON chunks USING GIN (tsv)")

    # ── jobs ─────────────────────────────────────────────────────────────
    op.create_table(
        "jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("pipeline_version", sa.Text, nullable=False),
        sa.Column("claimed_by", sa.Text),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("error", sa.Text),
    )
    op.create_index("ix_jobs_status_priority", "jobs", ["status", "priority", "created_at"])
    op.create_index("ix_jobs_case_id", "jobs", ["case_id"])

    # ── audit_log ────────────────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("case_id", UUID(as_uuid=True)),
        sa.Column("actor_user_id", UUID(as_uuid=True)),
        sa.Column("action", sa.Text, nullable=False),
        sa.Column("payload", JSONB, nullable=False),
        sa.Column("prev_hash", sa.Text),
        sa.Column("hash", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_log_case_id", "audit_log", ["case_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # ── entities ─────────────────────────────────────────────────────────
    op.create_table(
        "entities",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("value", sa.Text),
        sa.Column("display_name", sa.Text),
        sa.Column(
            "meta",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entities_case_kind_value", "entities", ["case_id", "kind", "value"])

    # ── entity_links ─────────────────────────────────────────────────────
    op.create_table(
        "entity_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "case_id",
            UUID(as_uuid=True),
            sa.ForeignKey("cases.id"),
            nullable=False,
        ),
        sa.Column(
            "src_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        sa.Column(
            "dst_id",
            UUID(as_uuid=True),
            sa.ForeignKey("entities.id"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column("weight", sa.Float),
        sa.Column("confidence", sa.Float),
        sa.Column(
            "meta",
            JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_entity_links_case_src", "entity_links", ["case_id", "src_id"])
    op.create_index("ix_entity_links_case_dst", "entity_links", ["case_id", "dst_id"])


def downgrade() -> None:
    op.drop_table("entity_links")
    op.drop_table("entities")
    op.drop_table("audit_log")
    op.drop_table("jobs")
    op.execute("DROP TABLE IF EXISTS chunks CASCADE")
    op.execute("DROP TABLE IF EXISTS events CASCADE")
    op.drop_table("messages")
    op.drop_table("media")
    op.drop_table("artifacts")
    op.drop_table("documents")
    op.drop_table("case_members")
    op.drop_table("cases")

    op.execute('DROP EXTENSION IF EXISTS "uuid-ossp"')
    op.execute("DROP EXTENSION IF EXISTS unaccent")
    op.execute("DROP EXTENSION IF EXISTS postgis")
    op.execute("DROP EXTENSION IF EXISTS vector")
