# 31 — Mapa geoespacial + grafo de vínculos (UI)

Status: done
Tipo: AFK
Prioridade: P3

## Parent

`PLANO_NOVO.md` seção 8.2 (Mapa, Grafo); ADR-0002, ADR-0008.

## What to build

Tela de Mapa: Events georreferenciados (PostGIS via `query_geo`), filtros por período/dispositivo/pessoa/tipo, ações "Traçar rota", "Ver eventos próximos", "Enviar seleção ao Agent"; suporte a tiles locais/offline quando definido. Tela de Grafo: `entities`/`entity_links` com filtros por tipo e força do vínculo, "Expandir 1-hop", "Caminho entre entidades", arestas `resolves_to` visualmente distintas de vínculos de comunicação; layout legível sem animações excessivas.

## Acceptance criteria

- [ ] Eventos com `geo` do corpus sintético plotados e filtráveis
- [ ] Grafo mostra Identity com suas observações ligadas por `resolves_to`
- [ ] "Enviar seleção ao Agent" injeta escopo na sessão do Agent
- [ ] Caminho entre duas entities renderizado

## Blocked by

- 17-structured-tools
- 21-ui-operacional-nucleo
