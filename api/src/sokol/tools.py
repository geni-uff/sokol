"""SOKOL tools — structured query tools for the investigative agent.

All tools use parameterized SQL. No free-form SQL from LLM.
Each tool returns results with sources (ref_table, ref_id).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


# ── Tool result schema ─────────────────────────────────────────────────────
@dataclass
class ToolResult:
    tool_name: str
    data: list[dict]
    sources: list[dict]  # [{ref_table, ref_id, summary}]
    count: int
    error: str | None = None


# ── Parameter schemas ──────────────────────────────────────────────────────
class TimelineParams(BaseModel):
    case_id: UUID
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    kind: str | None = None  # "message", "call", "location", "web_visit"
    app: str | None = None
    limit: int = 100


class MessagesParams(BaseModel):
    case_id: UUID
    chat_id: str | None = None
    sender: str | None = None
    counterpart: str | None = None
    app: str | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    limit: int = 50


class CallsParams(BaseModel):
    case_id: UUID
    phone: str | None = None
    direction: str | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    limit: int = 50


class MediaParams(BaseModel):
    case_id: UUID
    kind: str | None = None  # "image", "audio", "video", "document"
    mime_type: str | None = None
    limit: int = 50


class GeoParams(BaseModel):
    case_id: UUID
    lat_min: float | None = None
    lat_max: float | None = None
    lon_min: float | None = None
    lon_max: float | None = None
    start_ts: datetime | None = None
    end_ts: datetime | None = None
    limit: int = 100


class SemanticSearchParams(BaseModel):
    case_id: UUID
    query: str
    k: int = 20


# ── Tool implementations ───────────────────────────────────────────────────
def query_timeline(db, params: TimelineParams) -> ToolResult:
    """Query the unified timeline (events table)."""
    from sqlalchemy import text as sql_text

    conditions = ["e.case_id = :cid"]
    bind = {"cid": params.case_id, "limit": params.limit}

    if params.start_ts:
        conditions.append("e.ts >= :start_ts")
        bind["start_ts"] = params.start_ts
    if params.end_ts:
        conditions.append("e.ts <= :end_ts")
        bind["end_ts"] = params.end_ts
    if params.kind:
        conditions.append("e.kind = :kind")
        bind["kind"] = params.kind
    if params.app:
        conditions.append("e.app = :app")
        bind["app"] = params.app

    where = " AND ".join(conditions)
    rows = db.execute(
        sql_text(f"""
            SELECT e.id, e.ts, e.kind, e.actor, e.counterpart, e.app,
                   e.summary, e.ref_table, e.ref_id, e.meta
            FROM events e
            WHERE {where}
            ORDER BY e.ts ASC
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        entry = {
            "id": str(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "kind": r[2],
            "actor": r[3],
            "counterpart": r[4],
            "app": r[5],
            "summary": r[6],
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": r[7],
                "ref_id": str(r[8]),
                "summary": r[6],
            }
        )

    return ToolResult(
        tool_name="query_timeline",
        data=data,
        sources=sources,
        count=len(data),
    )


def query_messages(db, params: MessagesParams) -> ToolResult:
    """Query messages with filters."""
    from sqlalchemy import text as sql_text

    conditions = ["m.case_id = :cid"]
    bind = {"cid": params.case_id, "limit": params.limit}

    if params.chat_id:
        conditions.append("m.chat_id = :chat_id")
        bind["chat_id"] = params.chat_id
    if params.sender:
        conditions.append("m.sender LIKE :sender")
        bind["sender"] = f"%{params.sender}%"
    if params.counterpart:
        conditions.append("m.counterpart LIKE :cp")
        bind["cp"] = f"%{params.counterpart}%"
    if params.app:
        conditions.append("m.app = :app")
        bind["app"] = params.app
    if params.start_ts:
        conditions.append("m.ts >= :start_ts")
        bind["start_ts"] = params.start_ts
    if params.end_ts:
        conditions.append("m.ts <= :end_ts")
        bind["end_ts"] = params.end_ts

    where = " AND ".join(conditions)
    rows = db.execute(
        sql_text(f"""
            SELECT m.id, m.ts, m.app, m.chat_id, m.sender, m.counterpart,
                   m.direction, m.text, m.meta
            FROM messages m
            WHERE {where}
            ORDER BY m.ts ASC
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        entry = {
            "id": str(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "app": r[2],
            "chat_id": r[3],
            "sender": r[4],
            "counterpart": r[5],
            "direction": r[6],
            "text": r[7],
        }
        data.append(entry)
        summary = f"[{r[2] or '?'}] {r[4] or '?'}: {(r[7] or '')[:80]}"
        sources.append(
            {
                "ref_table": "messages",
                "ref_id": str(r[0]),
                "summary": summary,
            }
        )

    return ToolResult(
        tool_name="query_messages",
        data=data,
        sources=sources,
        count=len(data),
    )


def query_calls(db, params: CallsParams) -> ToolResult:
    """Query call log."""
    from sqlalchemy import text as sql_text

    conditions = ["m.case_id = :cid", "m.meta->>'type' = 'call'"]
    bind = {"cid": params.case_id, "limit": params.limit}

    if params.phone:
        conditions.append("m.counterpart LIKE :phone")
        bind["phone"] = f"%{params.phone}%"
    if params.direction:
        conditions.append("m.direction = :dir")
        bind["dir"] = params.direction
    if params.start_ts:
        conditions.append("m.ts >= :start_ts")
        bind["start_ts"] = params.start_ts
    if params.end_ts:
        conditions.append("m.ts <= :end_ts")
        bind["end_ts"] = params.end_ts

    where = " AND ".join(conditions)
    rows = db.execute(
        sql_text(f"""
            SELECT m.id, m.ts, m.sender, m.counterpart, m.direction,
                   m.text, m.meta
            FROM messages m
            WHERE {where}
            ORDER BY m.ts ASC
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        meta = json.loads(r[6]) if r[6] else {}
        entry = {
            "id": str(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "sender": r[2],
            "counterpart": r[3],
            "direction": r[4],
            "summary": r[5],
            "duration_seconds": meta.get("duration_seconds"),
            "status": meta.get("status"),
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": "messages",
                "ref_id": str(r[0]),
                "summary": r[5],
            }
        )

    return ToolResult(
        tool_name="query_calls",
        data=data,
        sources=sources,
        count=len(data),
    )


def query_media(db, params: MediaParams) -> ToolResult:
    """Query media artifacts."""
    from sqlalchemy import text as sql_text

    conditions = ["a.case_id = :cid"]
    bind = {"cid": params.case_id, "limit": params.limit}

    if params.kind:
        conditions.append("a.kind = :kind")
        bind["kind"] = params.kind
    if params.mime_type:
        conditions.append("a.mime_type = :mime")
        bind["mime"] = params.mime_type

    where = " AND ".join(conditions)
    rows = db.execute(
        sql_text(f"""
            SELECT a.id, a.kind, a.mime_type, a.size_bytes, a.source_member, a.meta
            FROM artifacts a
            WHERE {where}
            ORDER BY a.id
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        meta = json.loads(r[5]) if r[5] else {}
        entry = {
            "id": str(r[0]),
            "kind": r[1],
            "mime_type": r[2],
            "size_bytes": r[3],
            "source_member": r[4],
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": "artifacts",
                "ref_id": str(r[0]),
                "summary": f"{r[1] or '?'}: {r[4] or '?'}",
            }
        )

    return ToolResult(
        tool_name="query_media",
        data=data,
        sources=sources,
        count=len(data),
    )


def query_geo(db, params: GeoParams) -> ToolResult:
    """Query location events with geographic bounds."""
    from sqlalchemy import text as sql_text

    conditions = ["e.case_id = :cid", "e.kind = 'location'", "e.geo IS NOT NULL"]
    bind = {"cid": params.case_id, "limit": params.limit}

    if params.lat_min is not None:
        conditions.append("ST_Y(e.geo::geometry) >= :lat_min")
        bind["lat_min"] = params.lat_min
    if params.lat_max is not None:
        conditions.append("ST_Y(e.geo::geometry) <= :lat_max")
        bind["lat_max"] = params.lat_max
    if params.lon_min is not None:
        conditions.append("ST_X(e.geo::geometry) >= :lon_min")
        bind["lon_min"] = params.lon_min
    if params.lon_max is not None:
        conditions.append("ST_X(e.geo::geometry) <= :lon_max")
        bind["lon_max"] = params.lon_max
    if params.start_ts:
        conditions.append("e.ts >= :start_ts")
        bind["start_ts"] = params.start_ts
    if params.end_ts:
        conditions.append("e.ts <= :end_ts")
        bind["end_ts"] = params.end_ts

    where = " AND ".join(conditions)
    rows = db.execute(
        sql_text(f"""
            SELECT e.id, e.ts, e.summary,
                   ST_Y(e.geo::geometry) AS lat,
                   ST_X(e.geo::geometry) AS lon,
                   e.meta
            FROM events e
            WHERE {where}
            ORDER BY e.ts ASC
            LIMIT :limit
        """),
        bind,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        entry = {
            "id": str(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "summary": r[2],
            "lat": r[3],
            "lon": r[4],
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": "events",
                "ref_id": str(r[0]),
                "summary": r[2],
            }
        )

    return ToolResult(
        tool_name="query_geo",
        data=data,
        sources=sources,
        count=len(data),
    )


def semantic_search(db, params: SemanticSearchParams) -> ToolResult:
    """Semantic search across chunks."""
    from .search import search_hybrid

    result = search_hybrid(db, params.case_id, params.query, params.k, "vector")

    data = []
    sources = []
    for r in result.results:
        entry = {
            "chunk_id": r.chunk_id,
            "text": r.text[:500],
            "score": r.score,
            "ref": r.ref,
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": "chunks",
                "ref_id": r.chunk_id,
                "summary": r.text[:120],
            }
        )

    return ToolResult(
        tool_name="semantic_search",
        data=data,
        sources=sources,
        count=len(data),
    )


class SemanticSearchEventsParams(BaseModel):
    case_id: UUID
    query: str
    k: int = 10
    kind: str | None = None


def semantic_search_events(db, params: SemanticSearchEventsParams) -> ToolResult:
    """Semantic search across event summaries using vector similarity."""
    from sqlalchemy import text as sql_text
    import httpx
    import os

    embed_base_url = os.getenv("SOKOL_EMBED_BASE_URL", "http://localhost:1234/v1")
    embed_model_id = os.getenv(
        "SOKOL_ACTIVE_EMBED_MODEL", "text-embedding-qwen3-embedding-0.6b"
    )

    embed_url = (
        f"{embed_base_url}/embeddings"
        if embed_base_url.endswith("/v1")
        else f"{embed_base_url}/v1/embeddings"
    )
    resp = httpx.post(
        embed_url,
        json={"input": [params.query], "model": embed_model_id},
        timeout=60.0,
    )
    resp.raise_for_status()
    query_embedding = resp.json()["data"][0]["embedding"]
    emb_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

    kind_filter = ""
    bind_params: dict = {
        "case_id": str(params.case_id),
        "query_emb": emb_str,
        "k": params.k,
    }
    if params.kind:
        kind_filter = "AND kind = :kind"
        bind_params["kind"] = params.kind

    rows = db.execute(
        sql_text(f"""
            SELECT id, ts, kind, actor, counterpart, app, summary, meta,
                   1 - (embedding <=> CAST(:query_emb AS vector)) AS similarity
            FROM events
            WHERE case_id = :case_id
              AND embedding IS NOT NULL
              {kind_filter}
            ORDER BY embedding <=> CAST(:query_emb AS vector)
            LIMIT :k
        """),
        bind_params,
    ).fetchall()

    data = []
    sources = []
    for r in rows:
        entry = {
            "id": str(r[0]),
            "ts": r[1].isoformat() if r[1] else None,
            "kind": r[2],
            "actor": r[3],
            "counterpart": r[4],
            "app": r[5],
            "summary": r[6],
            "meta": r[7] if isinstance(r[7], dict) else {},
            "score": round(r[8], 4) if r[8] else 0,
        }
        data.append(entry)
        sources.append(
            {
                "ref_table": "events",
                "ref_id": str(r[0]),
                "summary": r[6],
            }
        )

    return ToolResult(
        tool_name="semantic_search_events",
        data=data,
        sources=sources,
        count=len(data),
    )


# ── Tool registry ──────────────────────────────────────────────────────────
TOOLS = {
    "query_timeline": {
        "fn": query_timeline,
        "schema": TimelineParams,
        "description": "Consulta a linha do tempo unificada de eventos. Use para perguntas sobre 'o que aconteceu em [data]', 'quando [pessoa] fez [algo]', 'sites visitados', 'URLs acessadas', etc. Filtrar por kind: message, call, location, web_visit.",
    },
    "query_messages": {
        "fn": query_messages,
        "schema": MessagesParams,
        "description": "Consulta mensagens de conversas (WhatsApp, SMS, etc). Use para perguntas sobre 'o que [pessoa] disse', 'conversas sobre [assunto]', etc.",
    },
    "query_calls": {
        "fn": query_calls,
        "schema": CallsParams,
        "description": "Consulta o log de chamadas telefônicas. Use para perguntas sobre 'ligações para [numero]', 'quando [pessoa] ligou', etc.",
    },
    "query_media": {
        "fn": query_media,
        "schema": MediaParams,
        "description": "Consulta arquivos de mídia (imagens, áudios, vídeos, documentos). Use para perguntas sobre 'fotos de [data]', 'áudios', etc.",
    },
    "query_geo": {
        "fn": query_geo,
        "schema": GeoParams,
        "description": "Consulta localizações GPS. Use para perguntas sobre 'onde [pessoa] esteve', 'locais visitados', etc.",
    },
    "semantic_search": {
        "fn": semantic_search,
        "schema": SemanticSearchParams,
        "description": "Busca semântica no conteúdo textual (chunks de mensagens). Use para perguntas sobre conversas, textos, mensagens.",
    },
    "semantic_search_events": {
        "fn": semantic_search_events,
        "schema": SemanticSearchEventsParams,
        "description": "Busca semântica nos eventos (linhas do tempo, sites, localizações, chamadas). USE ESTA FERRAMENTA quando o usuário perguntar sobre algo específico como um nome, site, local, ou termo. Retorna os eventos mais relevantes por similaridade.",
    },
}


def get_tool_schemas() -> list[dict]:
    """Return OpenAI-compatible tool schemas for the LLM."""
    schemas = []
    for name, tool in TOOLS.items():
        pydantic_schema = tool["schema"].model_json_schema()
        # Convert Pydantic schema to OpenAI function format
        properties = pydantic_schema.get("properties", {})
        required = pydantic_schema.get("required", [])

        # Remove case_id from parameters (injected by backend)
        properties.pop("case_id", None)
        required = [r for r in required if r != "case_id"]

        schemas.append(
            {
                "type": "function",
                "function": {
                    "name": name,
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required,
                    },
                },
            }
        )
    return schemas


def execute_tool(db, tool_name: str, params: dict, case_id: UUID) -> ToolResult:
    """Execute a tool by name with params."""
    tool = TOOLS.get(tool_name)
    if not tool:
        return ToolResult(
            tool_name=tool_name,
            data=[],
            sources=[],
            count=0,
            error=f"Unknown tool: {tool_name}",
        )

    try:
        validated = tool["schema"](**params, case_id=case_id)
        return tool["fn"](db, validated)
    except Exception as e:
        return ToolResult(
            tool_name=tool_name,
            data=[],
            sources=[],
            count=0,
            error=str(e),
        )
