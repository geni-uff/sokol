# 09 — sokol-embed Docker com /v1/embeddings batch

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-07A; seção 2.4; ADR-0006.

## What to build

Serviço `sokol-embed` no compose expondo `POST /v1/embeddings` (OpenAI-compatible) e `GET /health`, com batch de textos como cidadão de primeira classe, carregando `Qwen/Qwen3-Embedding-0.6B` por default e permitindo perfil alternativo (`BAAI/bge-m3`) via configuração — o perfil serve ao **eval pré-deploy** (issue 11), não a troca em runtime (ADR-0006). Retorna dimensão validável; GPU via variável resolvida pelo setup.

## Acceptance criteria

- [ ] `POST /v1/embeddings` com batch retorna vetores com dimensão declarada do perfil
- [ ] Healthcheck do compose passa
- [ ] Worker consegue embedar lote via `SOKOL_EMBED_BASE_URL` sem depender do LM Studio
- [ ] Throughput medido com corpus sintético registrado no README do serviço

## Blocked by

- 01-monorepo-compose-minimo
