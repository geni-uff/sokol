# 14 — Contrato de parser + parsers estruturados

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-12; ADR-0002, ADR-0008.

## What to build

Contrato comum de parser (entrada, Artifacts gerados, Events gerados, erros recuperáveis) e implementações: WhatsApp, SMS, chamadas, **contatos** (populando `entities` kind=`contact`/`phone` com vínculo `contact_of` — ADR-0002), localizações (com `geo`) e histórico web. Cada parser popula tabelas estruturadas e projeta Events com `ref_table`/`ref_id`. Testes por fixture do corpus sintético. Deixar SkyECC/Cellebrite XLS apenas planejados como entradas equivalentes.

## Acceptance criteria

- [ ] Cada parser tem teste por fixture cobrindo caso feliz e erro recuperável
- [ ] Parser de contatos cria `entities` (`contact`, `phone`) e `entity_links`
- [ ] Localizações geram Events com `geo` consultável via PostGIS
- [ ] Todos os Events criados apontam à origem por `ref_table`/`ref_id`

## Blocked by

- 13-ingestion-estrutural-ufdr
