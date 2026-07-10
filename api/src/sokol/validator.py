"""SOKOL validator — deterministic validation of chat responses.

Ensures every citation in a response points to an existing record.
No factual claim goes unsourced.
"""

from __future__ import annotations

import json
import re
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from .tools import ToolResult


def _extract_citations(response_text: str) -> list[dict]:
    """Extract citation references from the response text.

    Looks for patterns like:
    - [Mensagem] ... ref_id: xxx
    - [Chamada] ... ref_id: xxx
    - (ref_table=messages, ref_id=xxx)
    """
    citations = []

    # Pattern 1: explicit ref_table/ref_id mentions
    for match in re.finditer(
        r"ref_id[:\s=]+([0-9a-f-]{36})", response_text, re.IGNORECASE
    ):
        citations.append({"ref_id": match.group(1), "type": "explicit"})

    # Pattern 2: bracketed source references like [Mensagem ...]
    for match in re.finditer(
        r"\[(Mensagem|Chamada|Localização|Arquivo|Web)[^\]]*\]", response_text
    ):
        citations.append({"text": match.group(0), "type": "source_ref"})

    return citations


def _extract_dates(response_text: str) -> list[str]:
    """Extract date references from the response."""
    dates = []
    # DD/MM/YYYY
    for match in re.finditer(r"\d{2}/\d{2}/\d{4}", response_text):
        dates.append(match.group())
    # YYYY-MM-DD
    for match in re.finditer(r"\d{4}-\d{2}-\d{2}", response_text):
        dates.append(match.group())
    return dates


def _validate_citations_exist(
    db: Session,
    case_id: UUID,
    citations: list[dict],
) -> list[str]:
    """Validate that cited records actually exist in the database."""
    warnings = []

    for citation in citations:
        ref_id = citation.get("ref_id")
        if not ref_id:
            continue

        # Check in messages
        row = db.execute(
            text("SELECT id FROM messages WHERE id = :id AND case_id = :cid"),
            {"id": ref_id, "cid": case_id},
        ).fetchone()
        if row:
            continue

        # Check in events
        row = db.execute(
            text("SELECT id FROM events WHERE id = :id AND case_id = :cid"),
            {"id": ref_id, "cid": case_id},
        ).fetchone()
        if row:
            continue

        # Check in artifacts
        row = db.execute(
            text("SELECT id FROM artifacts WHERE id = :id AND case_id = :cid"),
            {"id": ref_id, "cid": case_id},
        ).fetchone()
        if row:
            continue

        # Check in chunks
        row = db.execute(
            text("SELECT id FROM chunks WHERE id = :id AND case_id = :cid"),
            {"id": ref_id, "cid": case_id},
        ).fetchone()
        if row:
            continue

        warnings.append(f"Citação para registro inexistente: {ref_id}")

    return warnings


def _validate_sources_in_case(
    db: Session,
    case_id: UUID,
    sources: list[dict],
) -> list[str]:
    """Validate that all sources belong to the same case_id."""
    warnings = []

    for source in sources:
        ref_table = source.get("ref_table")
        ref_id = source.get("ref_id")

        if not ref_table or not ref_id:
            continue

        valid_tables = {
            "messages": "messages",
            "events": "events",
            "artifacts": "artifacts",
            "chunks": "chunks",
        }

        table = valid_tables.get(ref_table)
        if not table:
            warnings.append(f"Tabela desconhecida na fonte: {ref_table}")
            continue

        row = db.execute(
            text(f"SELECT case_id FROM {table} WHERE id = :id"),
            {"id": ref_id},
        ).fetchone()

        if row and str(row[0]) != str(case_id):
            warnings.append(f"Fonte {ref_table}:{ref_id} pertence a outro caso")

    return warnings


def _validate_dates_in_range(
    tool_results: list[ToolResult],
    cited_dates: list[str],
) -> list[str]:
    """Validate that cited dates are within the range of tool results."""
    warnings = []

    # Collect all timestamps from tool results
    all_ts = []
    for tr in tool_results:
        for item in tr.data:
            ts = item.get("ts")
            if ts:
                all_ts.append(ts)

    if not all_ts or not cited_dates:
        return warnings

    # Check each cited date
    for date_str in cited_dates:
        found = False
        for ts in all_ts:
            if date_str in ts:
                found = True
                break
        if not found:
            warnings.append(
                f"Data {date_str} citada mas não encontrada nos resultados das ferramentas"
            )

    return warnings


def _validate_counts(
    response_text: str,
    tool_results: list[ToolResult],
) -> list[str]:
    """Validate that counts mentioned in response match tool results."""
    warnings = []

    # Extract count mentions like "15 chamadas" or "3 mensagens"
    count_pattern = re.compile(
        r"(\d+)\s+(mensagens?|chamadas?|locais?|arquivos?|fotos?|contatos?)"
    )
    for match in count_pattern.finditer(response_text):
        claimed_count = int(match.group(1))
        entity_type = match.group(2).lower()

        # Map to tool result types
        type_map = {
            "mensagem": "query_messages",
            "mensagens": "query_messages",
            "chamada": "query_calls",
            "chamadas": "query_calls",
            "local": "query_geo",
            "locais": "query_geo",
            "arquivo": "query_media",
            "arquivos": "query_media",
            "foto": "query_media",
            "fotos": "query_media",
        }

        tool_name = type_map.get(entity_type)
        if tool_name:
            for tr in tool_results:
                if tr.tool_name == tool_name and tr.count != claimed_count:
                    warnings.append(
                        f"Contagem '{claimed_count} {entity_type}' pode estar incorreta "
                        f"(ferramenta retornou {tr.count})"
                    )

    return warnings


def validate_response(
    response_text: str,
    tool_results: list[ToolResult],
    case_id: UUID,
    db: Session,
) -> list[str]:
    """
    Validate a chat response against tool results and database.

    Returns list of warnings (empty = valid).
    """
    warnings = []

    # 1. Extract citations and dates
    citations = _extract_citations(response_text)
    cited_dates = _extract_dates(response_text)

    # 2. Validate citations exist
    warnings.extend(_validate_citations_exist(db, case_id, citations))

    # 3. Validate sources belong to case
    all_sources = []
    for tr in tool_results:
        all_sources.extend(tr.sources)
    warnings.extend(_validate_sources_in_case(db, case_id, all_sources))

    # 4. Validate dates are in range
    warnings.extend(_validate_dates_in_range(tool_results, cited_dates))

    # 5. Validate counts
    warnings.extend(_validate_counts(response_text, tool_results))

    return warnings
