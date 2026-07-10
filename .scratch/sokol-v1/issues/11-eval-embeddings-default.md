# 11 — Eval de embeddings para fixar o default (decisão)

Status: done
Tipo: HITL
Prioridade: P0

## Parent

ADR-0006; `PLANO_NOVO.md` seções 2.2 e 11.2.

## What to build

Rodar o harness de evals comparando candidatos a embedding (`Qwen/Qwen3-Embedding-0.6B`, `BAAI/bge-m3`, e outros que o usuário indicar) sobre o corpus sintético/golden set: recall@k, MRR, citações válidas, latência p50/p95. Produzir tabela comparativa e **apresentar ao usuário para decisão final** — o modelo escolhido fica estipulado como default fixo (ADR-0006) antes de qualquer indexação de caso.

Candidato provável: `Qwen/Qwen3-Embedding-0.6B`.

## Acceptance criteria

- [ ] Tabela comparativa com métricas por modelo sobre o golden set
- [ ] Decisão do usuário registrada (atualizar ADR-0006 com o modelo fixado)
- [ ] `models.yaml` e `.env` refletem o default decidido
- [ ] Nenhum caso indexado antes da decisão

## Blocked by

- 07-corpus-sintetico-golden-set
- 09-sokol-embed-docker
