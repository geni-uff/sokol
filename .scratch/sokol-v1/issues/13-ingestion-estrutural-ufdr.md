# 13 — Ingestion estrutural UFDR (messages/events/media)

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-11 (etapas 4–12); seções 6.1; ADR-0001; `CONTEXT.md` (Ingestion).

## What to build

A fase de **Ingestion** do glossário, sem DOCX intermediário: inventariar o ZIP pelo central directory (sem extração massiva), classificar membros, SHA-256 dos relevantes, criar Documents/Artifacts, parse streaming de `report.xml`, extrair SQLites necessários para staging, popular `messages`, `events` e `media` (dedupe por SHA-256) — projetando **um Event por ocorrência**, incluindo cada Message (ADR-0001), com `tz_original` preservado. Gera `tsv` (marco consultável). Enfileira jobs de Enrichment por Artifact. Progresso via SSE. Reingestão idempotente.

## Acceptance criteria

- [ ] UFDR sintético popula `messages`/`events`/`media` e fica consultável antes de qualquer Enrichment
- [ ] Cada Message tem seu Event `kind='message'` com `ref_table/ref_id` (ADR-0001)
- [ ] Crash do worker no meio retoma pelo checkpoint sem duplicar Events
- [ ] Reingestão do mesmo UFDR deduplica Media e pula trabalho concluído
- [ ] `tz_original` gravado nos Events

## Blocked by

- 07-corpus-sintetico-golden-set
- 12-import-inbox-staging
