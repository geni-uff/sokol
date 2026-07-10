# 01 — Monorepo + compose mínimo com healthchecks

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-01, TODO-02 (parcial); seções 2.1 e 10.

## What to build

Esqueleto físico do SOKOL: diretórios `api/`, `web/`, `worker/`, `services/`, `db/`, `deploy/`, `ops/`, `evals/`, `synth/`, `docs/`; Python 3.12 com `uv`; `deploy/docker-compose.yml` escrito do zero (nomes `sokol-*`, sem nada `cerebro_*`) subindo **postgres** (16 + pgvector + postgis) e **api** stub FastAPI com `GET /health` respondendo o formato da seção 5.1. `deploy/env.example` só com variáveis `SOKOL_*`. `.gitignore` cobrindo `.env`, dados, caches, modelos.

Fatia demoável: `docker compose --env-file deploy/.env -f deploy/docker-compose.yml up` sobe a stack mínima e `GET /health` retorna `postgres: ok`.

## Acceptance criteria

- [ ] Compose sobe postgres+api com healthchecks passando
- [ ] `GET /health` reporta status do Postgres no formato da seção 5.1
- [ ] Nenhuma referência a imagens/nomes antigos (`cerebro_*`, Weaviate, Ollama)
- [ ] Volumes nomeados; dados sob `./data`
- [ ] `README.md` com comandos mínimos de desenvolvimento

## Blocked by

None - can start immediately
