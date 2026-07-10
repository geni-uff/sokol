# 03 — Migrations Alembic do schema completo

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-04; seção 4 completa (incl. 4.7); ADR-0001, ADR-0002, ADR-0007, ADR-0008.

## What to build

Alembic em `db/` com migrations que criam do zero: `cases` (com `reference_timezone`, ADR-0007), `case_members` (roles `admin`/`analista`/`leitor`), `documents`, `artifacts`, `media`, `messages`, `events`, `chunks`, `jobs`, `audit_log`, **`entities` e `entity_links`** (seção 4.7, ADR-0002/0008). Extensões `pgvector`, `postgis`, `unaccent`, UUID. Índices mínimos: HNSW/IVFFlat em `chunks.embedding`, GIN em `tsv`, btree em `case_id` e `events(case_id, ts)`, GIST em `events.geo`, `messages(case_id, chat_id, ts)`, `entities(case_id, kind, value)`. Seed opcional de admin local.

## Acceptance criteria

- [ ] `alembic upgrade head` cria o schema completo em banco limpo
- [ ] Extensões habilitadas por migration, não manualmente
- [ ] `entities`/`entity_links` presentes com índices
- [ ] Teste automatizado sobe banco efêmero e aplica migrations do zero

## Blocked by

- 01-monorepo-compose-minimo
