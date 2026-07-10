# 18 — Agent v1 (tool-calling + síntese + SSE)

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-16; seções 5.7 e 7.4; ADR-0003, ADR-0004, ADR-0005.

## What to build

`POST /chat/agent`: o **Agent** do glossário — recebe pergunta, escolhe Structured tools via tool-calling (ADR-0005), backend executa, LLM sintetiza com **Sources de origem** (ADR-0003), streaming SSE, sessões por caso. Prompt de sistema com regras de aterramento: fatos numéricos só de ferramentas; sem fonte → "não há registro"; Indicators nunca redigidos como fato (ADR-0004). Auditoria de plano, chamadas, parâmetros e fontes.

## Acceptance criteria

- [ ] "O que ocorreu em 12/03?" chama `query_timeline`, não busca vetorial pura
- [ ] Resposta inclui `sources` (formato origem+event_id) e `tool_calls` com `rows_returned`
- [ ] Pergunta sem dados responde que não há registro, sem inventar
- [ ] Streaming SSE funciona; resposta completa auditada no hash-chain

## Blocked by

- 08-client-llm-lmstudio
- 17-structured-tools
