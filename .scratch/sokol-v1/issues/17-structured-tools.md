# 17 — Structured tools do Agent (views read-only)

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-15; seções 5.6 e 7.4; ADR-0005, ADR-0007.

## What to build

Views read-only e a biblioteca de **Structured tools**: `query_timeline` (com parâmetro de fuso, default = `reference_timezone` do caso — ADR-0007), `query_messages`, `query_calls`, `query_media`, `query_geo`, `query_graph` (sobre `entities`/`entity_links`) e `semantic_search` (que nunca responde contagem/agregação — ADR-0005). Schemas Pydantic de parâmetros; SQL parametrizado; nenhum SQL livre vindo do LLM. Também expostas como endpoints públicos da seção 5.6.

## Acceptance criteria

- [ ] Cada ferramenta tem teste com corpus sintético retornando Sources auditáveis
- [ ] `query_timeline` com "dia 12/03" usa a fronteira do fuso do caso (teste de borda de meia-noite, ADR-0007)
- [ ] Nenhuma ferramenta aceita string SQL como parâmetro
- [ ] `query_graph` percorre vínculos `resolves_to` (ADR-0008)

## Blocked by

- 13-ingestion-estrutural-ufdr
