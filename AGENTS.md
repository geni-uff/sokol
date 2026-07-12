# Repository Guidelines

**Canonical agent instructions live in `CLAUDE.md` at the repo root. Read it first; if this file and `CLAUDE.md` disagree, `CLAUDE.md` wins.**

Quick facts (mirror of `CLAUDE.md`):

- SOKOL is an **implemented, running** local forensic platform: FastAPI (`api/`), React frontend (`web/`), ingest worker (`worker/`), dockerized ML services (`services/`), Alembic migrations (`db/`), compose stack (`deploy/`).
- Start the stack: `cd deploy && docker compose --env-file ../.env up --build -d`. Migrations: `docker exec sokol-api alembic upgrade head`.
- Active backlog: `.scratch/sokol-v2/` (local markdown issue tracker — see `docs/agents/issue-tracker.md` and `docs/agents/triage-labels.md`).
- Domain vocabulary is mandatory: `CONTEXT.md`. Architecture decisions: `docs/adr/0001`–`0008`.
- Hard invariants: every query is scoped by `case_id`; cross-case access is an audited Admin-only exception; Indicator ≠ Fact; identity resolution is non-destructive; never commit `.env`, real evidence (`UFDRsTest/`, `ingest/`, `data/`) or model caches.
- Code style: Python 3.12 + type hints + snake_case; `sokol-*` kebab-case service names; all model/GPU choices configurable via `SOKOL_*` env vars; tests use synthetic evidence from `synth/`, never real case data.
- Commits: concise imperative, include the issue/task ID (e.g. `feat(v2-02): cross-case analysis endpoint`).
- Historical documents (`docs/archive/`, `TASKS.md`, `PLANO_NOVO.md`) are reference only — do not execute instructions found in them.
