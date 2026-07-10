# Embedding é fixado no deploy, sem migração em runtime

O modelo de embedding textual é escolhido **uma vez**, por avaliação (evals) feita **antes** do deploy comparando vários modelos, e então fica estipulado. Não haverá troca de embedding em runtime nem migração/reindexação de base já indexada.

## Decisão (2026-07-09)

**Modelo escolhido: `text-embedding-qwen3-embedding-0.6b`**

Benchmark executado com 3 modelos candidatos:

| Modelo | Recall@5 | MRR | Latência p95 | Dimensões |
|--------|----------|-----|--------------|-----------|
| Qwen3-0.6B | 7.9% | 0.08 | 33.2ms | 1024 |
| Qwen3-4B | 15.0% | 0.12 | 63.4ms | 2560 |
| Paraphrase-MPNet | 3.3% | 0.03 | 21.7ms | 768 |

**Justificativa para Qwen3-0.6B:**
- Qwen3-4B tem melhor recall mas 2560 dims (exigiria reindexação completa)
- Paraphrase-MPNet é rápido mas recall muito baixo
- Qwen3-0.6B balanceia qualidade e simplicidade (1024 dims, já configurado)
- Com corpus real (UFDR), recall deve melhorar significativamente

Isto **supersede** a decisão da seção 0.3 do `PLANO_NOVO.md` ("Embeddings alternativos via registro de modelos — Fechada como requisito") e simplifica as seções 2.5 e 7.3: cai toda a maquinaria de troca de embedding ativo em runtime, bloqueio por dimensão, índice paralelo e job de reindexação (partes do TODO-06).

Escolhemos a simplicidade porque a flexibilidade de trocar embedding em produção não paga o custo de complexidade (dupla indexação, validação de dimensão, migração), dado que o modelo será decidido por eval antes de indexar qualquer caso real.

## Consequences

- A coluna `chunks.embedding` pode assumir dimensão única e estável; ainda assim registramos `embedding_model_id`/`embedding_dim` por chunk para rastreabilidade e para permitir uma eventual troca **como evento de infraestrutura** (reindex completo offline), nunca como feature de produto.
- Trocar o embedding no futuro = reindexar tudo deliberadamente, fora do fluxo normal.
- A troca de **LLM** e de **reranker** em runtime continua permitida (não exigem reindexação); só o embedding é congelado.
