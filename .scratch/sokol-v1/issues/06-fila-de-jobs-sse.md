# 06 — Fila de jobs retomável + progresso SSE

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-09; seções 4.5 e 5.4; `CONTEXT.md` (Job).

## What to build

Repositório de Jobs com claim por `FOR UPDATE SKIP LOCKED`, estados `pending/running/done/failed/cancelled`, `attempts`/`max_attempts` com backoff, heartbeat e retomada de jobs órfãos. Endpoints `GET /jobs/{id}` e `GET /events/jobs/{id}` via SSE emitindo `{stage, status, progress, message}`. Sem polling de arquivo. Worker genérico demonstrado com um job de exemplo.

## Acceptance criteria

- [ ] Matar o worker no meio de um job faz outro worker retomar sem duplicar resultado
- [ ] SSE entrega progresso incremental de um job de exemplo
- [ ] Job que excede `max_attempts` termina `failed` com `error` preenchido
- [ ] Dois workers concorrentes nunca pegam o mesmo job (teste de SKIP LOCKED)

## Blocked by

- 03-migrations-schema-completo
