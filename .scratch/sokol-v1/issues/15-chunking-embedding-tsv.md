# 15 — Chunking de Conversation + embedding batch

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-13; seções 6.2 e 7.2; ADR-0006; `CONTEXT.md` (Chunk, Enrichment).

## What to build

Job de Enrichment que gera **Chunks**: janelas de Conversation por chat/período/participantes com cabeçalho contextual e `message_ids` (rastreável até a Message), embedadas em batch via `sokol-embed` com o modelo fixado. Grava `embedding`, `embedding_model_id`, `embedding_dim` e `tsv`. Bloqueia indexação se a dimensão retornada divergir do perfil.

## Acceptance criteria

- [ ] Corpus sintético gera Chunks com Sources resolvíveis até a Message original
- [ ] Todo Chunk gravado tem `embedding_model_id` e `embedding_dim` corretos
- [ ] Dimensão divergente aborta a indexação com erro explícito
- [ ] Embedding roda em batch (não 1 request por chunk)

## Blocked by

- 09-sokol-embed-docker
- 13-ingestion-estrutural-ufdr
