"""SOKOL chat — investigative chat agent with tool calling."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.orm import Session

from .tools import TOOLS, get_tool_schemas, execute_tool, ToolResult
from .audit import append_audit

SYSTEM_PROMPT = """Você é um assistente investigativo do SOKOL, uma plataforma forense.
Você TEM que usar ferramentas para buscar dados antes de responder.

REGRA ABSOLUTA: Toda pergunta sobre evidências DEVE usar uma ferramenta primeiro.
Mesmo que o usuário digite APENAS um nome, URL, ou palavra-chave, VOCÊ DEVE usar uma ferramenta.

FERRAMENTAS DISPONÍVEIS:
- semantic_search_events: Busca semântica nos eventos por similaridade. USE ESTA como PRIMEIRA OPÇÃO para nomes, sites, locais, ou qualquer termo específico. Retorna os top-K mais relevantes.
- query_timeline: Consulta linha do tempo com filtros SQL. Use quando o usuário pedir "tudo de [tipo]" ou um intervalo de datas.
- semantic_search: Busca semântica em chunks de mensagens (conversas, textos).
- query_messages: Consulta mensagens com filtros específicos.
- query_calls: Consulta chamadas telefônicas.
- query_media: Consulta arquivos de mídia.
- query_geo: Consulta localizações GPS.

EXEMPLOS:
- "TudoGostoso" → semantic_search_events(query="TudoGostoso")
- "WhatsApp" → semantic_search_events(query="WhatsApp") + query_timeline(kind="message")
- "localização" → semantic_search_events(query="localização") + query_geo()
- "ligações" → query_calls()
- "sites visitados" → query_timeline(kind="web_visit")
- "o que aconteceu" → query_timeline()

REGRAS:
1. SEMPRE use ferramentas. NUNCA invente. NUNCA diga "não sei" sem antes usar ferramenta.
2. Cite as fontes de cada afirmação.
3. Se a ferramenta não retornar dados, diga que não há evidências.
4. Responda em português brasileiro.
5. Seja preciso com datas, nomes e valores.
6. NUNCA compartille dados de outros casos.
7. Ao encontrar o dado pedido, responda DIRETAMENTE sobre ele. Não liste tudo que encontrou.

FORMATAÇÃO DE FONTES:
- [Mensagem] remetente → destinatário, data: "trecho..."
- [Chamada] direção, duração, data
- [Localização] endereço, data
- [Web Visit] URL, data
- [Arquivo] nome, tipo
"""


def _get_llm_config() -> tuple[str, str]:
    base_url = os.getenv(
        "SOKOL_LMSTUDIO_BASE_URL", "http://host.docker.internal:1234/v1"
    )
    model = os.getenv("SOKOL_DEFAULT_LLM_MODEL", "change_me")
    return base_url, model


def _llm_chat(
    messages: list[dict], tools: list[dict] | None = None, stream: bool = False
) -> dict:
    """Call LLM with tool support."""
    base_url, model = _get_llm_config()

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": False,
    }
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    resp = httpx.post(
        f"{base_url}/chat/completions",
        json=payload,
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def _execute_tool_calls(
    db: Session, case_id: UUID, tool_calls: list[dict]
) -> list[dict]:
    """Execute tool calls from LLM and return results."""
    results = []
    for tc in tool_calls:
        fn = tc.get("function", {})
        name = fn.get("name", "")
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except json.JSONDecodeError:
            args = {}

        result = execute_tool(db, name, args, case_id)
        results.append(
            {
                "tool_call_id": tc.get("id", ""),
                "role": "tool",
                "content": json.dumps(
                    {
                        "tool_name": result.tool_name,
                        "count": result.count,
                        "data": result.data,
                        "sources": result.sources,
                        "error": result.error,
                    },
                    default=str,
                ),
            }
        )

    return results


def _validate_response(
    response_text: str, tool_results: list[ToolResult], case_id: UUID, db: Session
) -> list[str]:
    """Validate that citations in the response are supported by tool results."""
    from .validator import validate_response

    return validate_response(response_text, tool_results, case_id, db)


def chat_agent(
    db: Session,
    case_id: UUID,
    user_message: str,
    history: list[dict] | None = None,
    max_tool_rounds: int = 3,
) -> dict:
    """
    Run the investigative chat agent.

    Returns:
        {
            "response": str,
            "tool_calls": list[dict],
            "sources": list[dict],
            "validation_warnings": list[str],
            "audit_payload": dict,
        }
    """
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    tool_schemas = get_tool_schemas()
    all_tool_calls = []
    all_sources = []
    tool_results_collected = []

    for round_num in range(max_tool_rounds):
        # Call LLM
        llm_response = _llm_chat(messages, tools=tool_schemas)
        choice = llm_response["choices"][0]
        message = choice["message"]

        # Check for tool calls
        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            # No tool calls — final response
            response_text = message.get("content", "")
            break

        # Execute tool calls
        messages.append(message)
        tool_results = _execute_tool_calls(db, case_id, tool_calls)
        messages.extend(tool_results)

        # Track tool usage
        for tc in tool_calls:
            fn = tc.get("function", {})
            all_tool_calls.append(
                {
                    "name": fn.get("name"),
                    "arguments": fn.get("arguments"),
                    "round": round_num,
                }
            )

        # Collect sources from tool results
        for tr in tool_results:
            try:
                content = json.loads(tr["content"])
                all_sources.extend(content.get("sources", []))
                # Collect ToolResult objects for validation
                tool_results_collected.append(
                    ToolResult(
                        tool_name=content.get("tool_name", ""),
                        data=content.get("data", []),
                        sources=content.get("sources", []),
                        count=content.get("count", 0),
                    )
                )
            except (json.JSONDecodeError, KeyError):
                pass

        response_text = message.get("content", "")
    else:
        # Exhausted tool rounds without a final text response — force one
        messages.append(
            {
                "role": "user",
                "content": "Com base nas ferramentas já chamadas, responda agora.",
            }
        )
        llm_response = _llm_chat(messages, tools=[])
        response_text = llm_response["choices"][0]["message"].get("content", "")

    # Validate response
    warnings = _validate_response(
        response_text,
        tool_results_collected,
        case_id,
        db,
    )

    # Audit
    audit_payload = {
        "case_id": str(case_id),
        "user_message": user_message[:500],
        "tool_calls": all_tool_calls,
        "source_count": len(all_sources),
        "validation_warnings": warnings,
        "rounds": round_num + 1,
    }
    append_audit(
        db,
        case_id=case_id,
        actor_user_id=None,
        action="chat.agent_query",
        payload=audit_payload,
    )
    db.commit()

    return {
        "response": response_text,
        "tool_calls": all_tool_calls,
        "sources": all_sources,
        "validation_warnings": warnings,
        "audit_payload": audit_payload,
    }
