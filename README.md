# SOKOL

Sistema forense local para transformar evidências digitais em dados
estruturados, pesquisáveis e auditáveis.

## Quick start

### Prerequisites

- Docker & Docker Compose
- A `.env` file (copy `deploy/env.example` to `.env` and adjust)

### Start the stack

```bash
cd deploy
cp env.example ../.env   # edit as needed
docker compose --env-file ../.env up --build
```

### Verify

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "postgres": "ok"
  }
}
```

### Stop

```bash
docker compose --env-file ../.env down
```

## Project layout

```
api/          FastAPI gateway
web/          Frontend (React + Vite)
worker/       Ingest & enrichment jobs
services/     Dockerized ML services
db/           Alembic migrations
deploy/       Docker Compose + env config
ops/          Setup, backup, restore scripts
evals/        Golden tests
synth/        Synthetic evidence generator
docs/         ADRs and documentation
```

## Development

Each service has its own dependency management. The API uses `uv`:

```bash
cd api
uv sync
uv run uvicorn src.sokol.main:app --reload --port 8000
```

## License

Private – not for distribution.
