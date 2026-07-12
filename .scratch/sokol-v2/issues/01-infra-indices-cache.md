# 01 — Infra: índices, cache Redis e otimização de busca

Status: ready-for-agent
Tipo: AFK
Prioridade: P0

## Parent

`.scratch/sokol-v2/PRD.md` — pré-requisito das issues 02, 03 e 05.

## What to build

Preparar o banco e a API para queries analíticas cross-case e de agregação:

1. **Migração Alembic nova** (`db/`) adicionando índices que ainda não existam (verifique com `\di` antes — vários já existem desde a migração inicial):
   - `entities(kind, value)` sem `case_id` no prefixo (para lookup cross-case por valor);
   - `messages(case_id, sender)` e `messages(case_id, chat_id)`;
   - `events(case_id, kind, ts)` composto;
   - GIN em `messages.tsv` se ausente.
2. **Módulo de cache** `api/src/sokol/cache.py`: wrapper fino sobre o Redis já existente na stack (`sokol-redis`, ver `api/src/sokol/queue.py` para o padrão de conexão). Funções: `cache_get(key)`, `cache_set(key, value, ttl_seconds)`, `cache_invalidate(prefix)`. Serialização JSON. Se o Redis estiver fora, degradar silenciosamente (cache miss, logar warning).
3. Aplicar cache nos endpoints de stats existentes (`/events/stats` em `timeline.py`) com TTL de 60 s e invalidação no fim de uma ingestão (`worker/ingest_worker.py` ou no handler de conclusão do job).

## Before you start

- `docker exec -it sokol-postgres psql -U sokol -d sokol` → `\di` e `\d events`, `\d entities`, `\d messages`. Só crie índice que não exista.
- Leia `api/src/sokol/queue.py` para reusar a conexão Redis (não crie um segundo client global).

## Acceptance criteria

- [ ] `alembic upgrade head` aplica a migração em banco existente sem erro (e `downgrade` remove os índices)
- [ ] `cache.py` funciona com Redis de pé e degrada sem quebrar com Redis parado
- [ ] Segunda chamada a `/events/stats` dentro de 60 s não toca o Postgres (verificável por log)
- [ ] Nenhum índice duplicado criado

## Blocked by

None — can start immediately
