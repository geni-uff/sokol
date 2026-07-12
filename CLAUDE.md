# SOKOL — Instruções para agentes

Plataforma forense local: ingere evidências digitais (UFDR Cellebrite, documentos, mídia), estrutura em Postgres, e oferece busca híbrida, timeline, mapa, detecções ML e chat investigativo com fontes. Tudo roda em Docker Compose, sem serviços externos.

**Este arquivo é a fonte canônica de instruções.** Se outro documento contradisser este, este vence.

## Estado atual (2026-07-12)

- Sistema **implementado e funcional** (v0.3.x): API FastAPI, frontend React, worker de ingestão, 6 serviços ML, Postgres 16 (pgvector + postgis), Redis.
- Backlog ativo: `.scratch/sokol-v2/` (issues 01–10). O backlog v1 (`.scratch/sokol-v1/`) está concluído, exceto a issue 20 (`ready-for-human`).
- `TASKS.md` e tudo em `docs/archive/` são **históricos** — não execute instruções deles.

## Mapa de diretórios

| Caminho | Conteúdo |
|---|---|
| `api/src/sokol/` | Backend FastAPI — 1 módulo por domínio (`cases.py`, `ingest.py`, `timeline.py`, `search_core.py`, `pipeline.py`, `playbooks.py`, `media.py`...). Routers registrados em `main.py` |
| `web/src/` | Frontend React + Vite + TypeScript. Abas do caso em `web/src/components/case/` |
| `worker/` | Ingestão e enriquecimento (`ingest_worker.py`, `ufdr_parser.py`, `parsers/`, `seed_locations.py`) |
| `services/` | Serviços ML dockerizados (embed, vision, face, ocr, asr, plate) |
| `db/` | Migrações Alembic |
| `deploy/` | `docker-compose.yml`, `env.example` |
| `ops/` | Scripts de setup/backup/restore |
| `synth/` | Gerador de UFDR sintético para testes |
| `docs/adr/` | Decisões de arquitetura (0001–0008) — **leia antes de mexer em timeline, entities, sources, indicators ou timezone** |
| `CONTEXT.md` | Glossário do domínio — vocabulário obrigatório |
| `.scratch/` | Issue tracker local (ver seção abaixo) |
| `PLANO_NOVO.md` | Design original v1 — referência histórica das issues v1, não é backlog |
| `docs/archive/` | Relatórios e handoffs antigos — somente leitura |

## Comandos

```bash
# Subir a stack (na raiz do repo)
cd deploy && docker compose --env-file ../.env up --build -d

# Migrações
docker exec sokol-api alembic upgrade head

# Health check
curl http://localhost:8000/health

# Logs / banco
docker logs -f sokol-api
docker exec -it sokol-postgres psql -U sokol -d sokol

# Frontend dev (hot reload)
cd web && npm run dev        # porta 5173; produção via compose na 3000

# Lint / E2E frontend
cd web && npm run lint       # oxlint
cd web && npm run test:e2e   # Playwright (stack precisa estar de pé)

# UFDR sintético
cd synth && python -m synth --seed 42 --output ./output
```

Não há suite de testes Python ainda (`api/tests/` está vazio) — se criar testes, use `uv run pytest` a partir de `api/`.

## Serviços e portas

| Serviço | Porta host | Função |
|---|---|---|
| sokol-api | 8000 | API gateway |
| sokol-postgres | 5433 | Postgres 16 + pgvector + postgis |
| sokol-web | 3000 (prod) / 5173 (dev) | Frontend |
| sokol-worker | — | Ingestão em background (fila Redis) |
| sokol-redis | 6379 | Fila de jobs |
| sokol-embed | 8001 | Embeddings (Qwen3-Embedding-0.6B) |
| sokol-vision | 8007 | YOLO (armas, facas, ameaças) |
| sokol-ocr | 8008 | PaddleOCR |
| sokol-asr | 8009 | faster-whisper |
| sokol-plate | 8010 | Placas (YOLO + OCR + regex Mercosul) |
| sokol-face | 8011 | InsightFace (512-dim) |
| LM Studio | 1234 (host) | LLM do chat — roda fora do Docker |

Login padrão de dev: `admin` / `admin123`.

## Ingestão de UFDR

1. Copiar o arquivo para `ingest/inbox/` (nome plano, ex.: `google_pa7.ufdr`).
2. `POST /ingest/batch` com `{"case_id": "<uuid>", "source_type": "ufdr", "inbox_refs": ["google_pa7.ufdr"]}` → retorna 201 com `{total, results:[{job_id, document_id}]}`.
3. O usuário precisa ser membro do caso (`case_members`), senão a API responde "Not a member of this case".
4. Progresso: `GET /ingest/progress` e aba Status do frontend.

## Invariantes do domínio (NUNCA violar)

1. **Todo dado é escopado por `case_id`.** Toda query nova em `events`, `messages`, `media`, `entities` etc. filtra por caso. Endpoints de mídia exigem `?case_id=` e `require_case_member()` — não reintroduza fallbacks globais (já causou vazamento de evidências entre casos).
2. **Cross-case é exceção auditada.** Qualquer feature que compare/consulte múltiplos casos exige papel Admin, justificativa e registro no `audit_log`. Nunca é o default.
3. **Indicator ≠ Fact** (ADR-0004). Detecção automática (face, placa, label) é *Indicator* — aparece rotulada, nunca é afirmada como fato pelo Agent nem entra em laudo. Vira *Fact* só via resolução humana de Pendência.
4. **Resolução de identidade é não-destrutiva** (ADR-0008). Nunca faça merge que apague/sobrescreva entidades: crie arestas `resolves_to`; mesclar Identities = repontar arestas, auditado.
5. **Source aponta para registro de origem** (ADR-0003): Message, Media (SHA-256) ou Document+página — nunca para um Event como referência canônica.
6. **Tempo** (ADR-0007): preservar `tz_original` do dado; consultas usam o fuso do caso (`reference_timezone`, default `America/Sao_Paulo`), não UTC.
7. **Vocabulário**: use os termos do `CONTEXT.md` (Document, Artifact, Media, Event, Conversation, Agent...). "Evidência" não é entidade; "chat" sozinho é proibido em prosa.
8. **Contagens e fatos vêm de structured tools (SQL)**, nunca de busca semântica (ADR-0005).

## Convenções de código

- Python 3.12, type hints, módulos pequenos; snake_case. Dependências da API em `api/pyproject.toml` (uv).
- Serviços/containers: nomes `sokol-*`, kebab-case. Nada de nomes `cerebro_*`.
- Modelos de ML e GPU sempre configuráveis por env `SOKOL_*`; nunca hardcodar hardware.
- Frontend: TypeScript, Tailwind v4. **Atenção**: tokens custom (`bg-surface-elevated` etc.) não resolvem em dev — use inline styles ou classes padrão (histórico: MapTab).
- Commits: imperativos, com ID da issue/task quando houver (ex.: `feat(v2-02): cross-case analysis endpoint`).
- Testes usam evidência sintética (`synth/`), nunca dados reais de caso.

## Issue tracker local (`.scratch/`)

- Uma feature por diretório: `.scratch/<slug>/` com `PRD.md` + `issues/NN-slug.md` (detalhes: `docs/agents/issue-tracker.md`).
- Cada issue tem linha `Status:` no topo: `needs-triage` | `needs-info` | `ready-for-agent` | `ready-for-human` | `wontfix` (`docs/agents/triage-labels.md`).
- Fluxo para implementar uma issue: (1) ler a issue inteira e o `Blocked by`; (2) verificar o schema/código citado antes de editar (a issue pode ter envelhecido); (3) implementar; (4) marcar os acceptance criteria; (5) mudar `Status:` para `done`; (6) commitar com o ID.

## Segurança

- **Nunca commitar**: `.env`, credenciais, evidências reais (`UFDRsTest/`, `ingest/`, `data/`), caches de modelo, exports forenses. Já estão no `.gitignore` — não os remova de lá.
- Dados reais de caso nunca saem da máquina (sem upload para serviços externos).

## Lacunas conhecidas (não são bugs novos)

- Relatórios: geração é HTML; PDF de verdade ficou adiado (`reports.py`).
- Backup via API (`case_backup.py`) é stub — agenda/lista, mas não executa backup real.
- `api/tests/` vazio; E2E cobre só auth e cases.
- Issue v1 nº 20 (frontend shell) está `ready-for-human`.
