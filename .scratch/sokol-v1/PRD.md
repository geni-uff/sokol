# SOKOL v1 — Índice de issues

Fonte: `PLANO_NOVO.md` (plano oficial), `CONTEXT.md` (glossário), `docs/adr/0001..0008`.
Convenções de triagem: `docs/agents/triage-labels.md`.

## Ondas

### Onda 1 — Fundação (P0)
- 01 Monorepo + compose mínimo com healthchecks
- 02 Setup com autodetecção de GPU
- 03 Migrations do schema completo
- 04 Auth local + casos + RBAC (3 papéis)
- 05 Audit log hash-chain
- 06 Fila de jobs + progresso SSE
- 07 Corpus sintético + golden set

### Onda 2 — Modelos (P0)
- 08 Client LLM (LM Studio host)
- 09 sokol-embed Docker
- 10 Registro de modelos (LLM/reranker runtime)
- 11 Eval de embeddings p/ fixar default (HITL)

### Onda 3 — Ingestão e busca (P1)
- 12 Import: inbox → staging
- 13 Ingestion estrutural UFDR
- 14 Parsers estruturados
- 15 Chunking + embedding + tsv
- 16 Busca híbrida com Sources
- 17 Structured tools
- 18 Agent v1
- 19 Validator determinístico

### Onda 4 — Produto (P2)
- 20 Frontend shell (HITL)
- 21 UI operacional núcleo
- 22 Relatórios (bookmarks + IPJ/laudo)
- 23 Watchlists + hits

### Onda 5 — Enrichment pesado (P2)
- 24 sokol-doc (OCR/docs)
- 25 sokol-asr (áudio/vídeo)
- 26 sokol-vision (+ keyframes)
- 27 sokol-face (Indicators)
- 28 sokol-plate (Indicators)
- 29 Pendências humanas (Indicator→Fact)
- 30 UI de mídia e viewers

### Onda 6 — Operação e extras (P3)
- 31 Mapa + grafo UI
- 32 Playbooks v1
- 33 /ops observabilidade
- 34 Backup/restore + export de caso

## Fora de escopo da v1 (TODO-00)
Grafo visual avançado, speaker-id, migração do sistema antigo, alta
disponibilidade, integrações externas, upload web, containerização do LM Studio.
