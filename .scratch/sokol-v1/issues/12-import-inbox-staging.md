# 12 — Import: inbox → staging com SHA-256 e progresso

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-11 (etapas 1–3); seções 5.3 e 6.0; `CONTEXT.md` (Import).

## What to build

A fase de **Import** do glossário: `GET /ingest/inbox` lista a pasta montada (autenticado); `POST /ingest` aceita `inbox_ref` relativo (rejeita `../` e path absoluto), copia/hardlinka para `/data/staging`, calcula SHA-256 **antes de qualquer parser**, cria o Document e o Job de Ingestion. Progresso de Import (bytes/hash) separado do progresso de Ingestion, ambos via SSE. Auditoria da ingestão iniciada.

## Acceptance criteria

- [ ] `inbox_ref` com `../` ou path absoluto é rejeitado (teste de path traversal)
- [ ] Import emite progresso SSE próprio, distinto do job de Ingestion
- [ ] SHA-256 registrado no Document antes do primeiro parser
- [ ] Pasta montada inacessível produz erro claro, não silêncio

## Blocked by

- 04-auth-casos-rbac
- 06-fila-de-jobs-sse
