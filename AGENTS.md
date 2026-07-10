# Repository Guidelines

## Project Structure & Module Organization

This repository currently contains the planning material for SOKOL, not the
implementation. Treat `PLANO_NOVO.md` as the active source of truth. Historical
reference material lives in `OLD_DOCS/` and must not drive new architecture.

Planned implementation directories are described in `PLANO_NOVO.md`:

- `api/` for the FastAPI gateway.
- `web/` for the operational frontend.
- `worker/` for ingest and enrichment jobs.
- `services/` for Dockerized ML services.
- `db/` for Alembic migrations.
- `deploy/` for the new Docker Compose and environment examples.
- `ops/` for setup, backup, restore, and operational scripts.
- `evals/` and `synth/` for golden tests and synthetic evidence.

## Build, Test, and Development Commands

There is no runnable application yet. Do not invent commands without adding the
supporting files.

Current commands:

- `python -m synth --seed 42 --output ./synth/output` generates a synthetic
  UFDR package (report.xml, files/, golden_set.json, synthetic_data.json).
  Same seed always produces identical output.

Expected future commands:

- `docker compose --env-file deploy/.env -f deploy/docker-compose.yml up`
  starts the SOKOL stack.
- `uv run pytest` runs Python tests.
- `uv run alembic upgrade head` applies database migrations.

## Coding Style & Naming Conventions

Use clear `sokol-*` service/container names. Do not reuse `cerebro_*` names.
Prefer Python 3.12, type hints, small modules, and explicit contracts. Use
snake_case for Python identifiers and kebab-case for Docker service names.

All model and GPU choices must be configurable. Defaults are allowed; hardcoded
hardware assumptions are not.

## Testing Guidelines

Build tests around synthetic evidence, not real case data. Golden tests should
cover ingestion, event extraction, search recall, citations, model switching,
and chat grounding. Test files should use names like `test_ingest_ufdr.py` and
`test_search_hybrid.py`.

## Commit & Pull Request Guidelines

This directory has no Git history, so no existing commit convention is known.
Use concise imperative commits, for example `Add SOKOL model registry plan`.

Pull requests should include: summary, affected TODOs from `PLANO_NOVO.md`,
tests run, migration notes, and screenshots for UI changes.

## Security & Configuration Tips

Never commit real `.env` files, credentials, case evidence, model caches, or
generated forensic exports. The Google Drive upload helper, when needed on this
machine, is `/Users/mateuspestana/Documents/Datasets/GDriveUPloader/` and should
be run with `uv run main.py <comando>` from that project.

## Agent skills

### Issue tracker

Issues and PRDs live as local markdown files under `.scratch/<feature>/` in this repo (no Git remote required). See `docs/agents/issue-tracker.md`.

### Triage labels

Uses the five canonical triage roles verbatim (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`), recorded as a `Status:` line in each issue file. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
