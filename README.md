<p align="center">
  <img src="logo_sokol.png" alt="SOKOL" width="420" />
</p>

<h1 align="center">SOKOL</h1>

<p align="center">
  <strong>Sistema Operacional de Conhecimento e Organização Local</strong><br />
  Plataforma forense local para ingestão, análise e laudo de evidências digitais.
</p>

<p align="center">
  <img alt="versão" src="https://img.shields.io/badge/versão-0.8.2-1a1a1a?style=flat-square" />
  <img alt="licença" src="https://img.shields.io/badge/licença-privada-6b6b6b?style=flat-square" />
  <img alt="stack" src="https://img.shields.io/badge/stack-Docker_Compose-2496ED?style=flat-square" />
  <img alt="dados" src="https://img.shields.io/badge/dados-100%25_local-2e7d32?style=flat-square" />
</p>

<p align="center">
  <a href="#início-rápido">Início rápido</a> ·
  <a href="INSTRUCOES.md">Manual do operador</a> ·
  <a href="#arquitetura">Arquitetura</a> ·
  <a href="#autoria">Autoria</a>
</p>

---

## Autoria

O SOKOL foi feito por **Matheus C. Pestana**, do **GENI/UFF** (Universidade Federal Fluminense), **em parceria com a Polícia Federal**.

Uso interno. Os dados do caso **não saem da máquina**. Não há serviço de nuvem.

---

## O que é

O SOKOL transforma um extract Cellebrite (**UFDR**), PDF ou mídia avulsa em dados estruturados, pesquisáveis e auditáveis.

Tudo fica no **Caso** (`case_id`). A stack sobe com Docker Compose. O LLM do **Agent** corre no **LM Studio** no host.

| Capacidade | Função |
|---|---|
| **Ingestion** | Parse de UFDR (XML + FileSystem/iCloud), mensagens, chamadas, contatos, GPS, web, e-mail, mídia |
| **Busca híbrida** | Palavra (`tsvector`) + vetor (`pgvector`) |
| **Agent** | Pergunta com tools SQL e **Sources** (aba Chat) |
| **Pipeline de detecção** | Visão, rostos, placas, OCR, transcrição — aba **Mídia** |
| **Índice** | **Indexar texto** (lexical) e **Indexar vetores** (Agent) |
| **Timeline e mapa** | Events no fuso do Caso; geo PostGIS |
| **Playbooks e relatórios** | Fluxos fixos e HTML com cadeia de custódia |
| **Watchlists e Pendências** | Seletores; fila humana Indicator → Fact |
| **Identidades e cross-case** | `resolves_to` sem apagar nós; cross-case só Admin, com auditoria |
| **Auditoria** | `audit_log` append-only com hash-chain |

**Versão:** 0.8.2 (arquivo `VERSION`).

**Login de desenvolvimento:** `admin` / `admin123`.

Manual passo a passo: [`INSTRUCOES.md`](INSTRUCOES.md) (redação ASD-STE100 em português).  
Vocabulário: [`CONTEXT.md`](CONTEXT.md). ADRs: [`docs/adr/`](docs/adr/). Versão: [`docs/VERSIONING.md`](docs/VERSIONING.md).

---

## Requisitos

- Linux (nativo) **ou** Windows **11/10 com WSL2 + Ubuntu** (a stack não corre no Docker Desktop nativo)
- Docker Compose v2 **no Linux** (no Windows: Docker Engine **dentro** do Ubuntu)
- Git
- LM Studio no **mesmo** Linux (nativo ou Ubuntu WSL), porta **1234**, contexto **32768**
- Disco para modelos ML (dezenas de GB na primeira subida)
- ~32 GB de RAM (conforto)
- GPU NVIDIA + Container Toolkit (visão, ASR e faces; sem GPU esses serviços ficam lentos)

---

## Início rápido

**Windows:** não use o Docker Desktop nativo. Instale **Ubuntu no WSL2**, Docker **dentro** do Ubuntu e o LM Studio Linux. Guia: [`INSTRUCOES.md`](INSTRUCOES.md) seção 6.0. Depois, no Explorador, `SOKOL.bat` só chama o WSL.

**Linux / Ubuntu no WSL:**

1. Clone o repositório.

```bash
git clone https://github.com/geni-uff/sokol.git
cd sokol
```

2. Copie `deploy/env.example` para `.env`. Defina `POSTGRES_PASSWORD`.
3. Crie as pastas de dados.

```bash
mkdir -p data/media-cache data/staging data/backups
```

4. Abra o **LM Studio**. Carregue o LLM com contexto **32768**. Ligue o servidor na porta **1234**.
5. Suba a stack e aplique as migrações.

```bash
cd deploy && docker compose --env-file ../.env up --build -d
docker exec sokol-api alembic upgrade head
curl http://localhost:8000/health
```

6. Abra **http://localhost:3000**. Entre com `admin` / `admin123`.

O procedimento completo (inbox, ingestão, pipeline, vetores, Agent, backup) está em [`INSTRUCOES.md`](INSTRUCOES.md).

---

## Portas

| Endereço | Serviço |
|---|---|
| **http://localhost:3000** | UI operacional (`sokol-web`, nginx) |
| http://localhost:5173 | UI de desenvolvimento (Vite; `cd web && npm run dev`) |
| http://localhost:8000 | API FastAPI (`/docs`, `/health`) |
| localhost:5433 | Postgres 16 + pgvector + PostGIS |
| localhost:1234 | LM Studio (host) |

Depois de mudar o frontend, reconstrua o container. Senão a porta **3000** fica velha:

```bash
cd deploy && docker compose --env-file ../.env up -d --build sokol-web
```

---

## Arquitetura

```
Navegador
  :5173  Vite (dev)  ──proxy /api──┐
  :3000  nginx       ─proxy /api──┤
                                   ▼
                         sokol-api :8000
                                   │
     Postgres :5433   Redis :6379   Worker   ML :8001–8011   LM Studio :1234
```

| Container | Porta | Função |
|---|---|---|
| `sokol-web` | 3000 | SPA React |
| `sokol-api` | 8000 | API |
| `sokol-postgres` | 5433 | Banco |
| `sokol-redis` | 6379 | Fila |
| `sokol-worker` | — | Ingestion e job `embed` |
| `sokol-embed` | 8001 | Embeddings (Qwen3-Embedding-0.6B, 1024-d) |
| `sokol-vision` | 8007 | YOLO |
| `sokol-ocr` | 8008 | PaddleOCR |
| `sokol-asr` | 8009 | faster-whisper |
| `sokol-plate` | 8010 | Placas |
| `sokol-face` | 8011 | InsightFace |
| LM Studio | 1234 | LLM do Agent (**fora** do Docker) |

`sokol-api`, `sokol-worker` e `sokol-web` usam `network_mode: host`.

---

## Configuração

Copie `deploy/env.example` → `.env`. Não commite `.env` nem extracts reais (`UFDRsTest/`, `ingest/`, `data/`).

Inbox no host: `SOKOL_INGEST_DIR` (default `../UFDRsTest` relativo a `deploy/`). Copie UFDRs com a stack no ar. Só recrie o Compose se **mudar** esse caminho.

Papéis **por Caso:** Admin, Analista, Leitor.  
Papel **de plataforma:** `users.is_platform_admin` → `/admin` (backup, LLM, auditoria).

---

## Regras de domínio

1. Todo dado tem `case_id`. Mídia exige `?case_id=` e membership.
2. Cross-case é exceção: Admin + justificativa + `audit_log`.
3. **Indicator ≠ Fact.** Detecção automática não entra no laudo como fato.
4. Identidade: arestas `resolves_to`. Não apague nós.
5. **Source** aponta para Message, Media (SHA-256) ou Document+página. Não use Event como canônico.
6. Preserve `tz_original`. Consulte no fuso do Caso.
7. Contagem e fato vêm de SQL. Busca semântica não conta.

---

## Desenvolvimento

```bash
cd web && npm run dev      # UI :5173
cd web && npm run lint
cd web && npm run test:e2e # stack no ar
cd synth && python -m synth --seed 42 --output ./output
docker logs -f sokol-api
docker logs -f sokol-worker
```

Código: `api/src/sokol/`, `web/src/`, `worker/`, `services/`, `db/migrations/`.

---

## Estado

Operacional em **0.8.2**. Backlog v2 concluído. Assinatura RSA de laudo: fora de escopo até decisão jurídica.

---

## Licença

Privado — uso interno GENI/UFF e parceria com a Polícia Federal. Não distribuir.

---

## Créditos

| | |
|---|---|
| **Autor** | Matheus C. Pestana |
| **Instituição** | GENI / UFF |
| **Parceria** | Polícia Federal |
| **Repositório** | https://github.com/geni-uff/sokol |
