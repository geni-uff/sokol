<p align="center">
  <img src="logo_sokol.png" alt="SOKOL" width="480" />
</p>

<h3 align="center">Plataforma de Análise e Investigação Forense</h3>

<p align="center">
  Sistema Operacional de Conhecimento e Organização Local — ingestão, enriquecimento,
  busca, chat investigativo e geração de relatórios a partir de evidências digitais.
</p>

---

## Visão Geral

O SOKOL transforma evidências brutas (UFDR, arquivos, bancos de dados forenses)
em dados estruturados, pesquisáveis e auditáveis. Tudo roda localmente via
Docker Compose — sem dependência de serviços externos.

### Principais Capacidades

| Capacidade | Descrição |
|-----------|-----------|
| **Ingestão estrutural** | Parsing de UFDR (Cellebrite) com extração de mensagens, chamadas, localizações, web history e mídia |
| **Busca híbrida** | Combinação de busca lexical (tsvector) e semântica (pgvector) com reranking |
| **Chat investigativo** | Agente com ferramentas SQL parametrizadas que responde com fontes e citations |
| **Pipeline de detecção** | Detecção paralela automática — YOLO (armas, facas, granadas, explosivos), rostos (InsightFace), placas (YOLO+OCR), transcrição (Whisper) |
| **Reconhecimento facial** | Detecção, embedding e busca cross-case de rostos com InsightFace |
| **Extração de placas** | Detecção de placas veiculares com regex Mercosul |
| **Transcrição de áudio** | ASR com faster-whisper para áudio e vídeo |
| **Timeline unificada** | Eventos estruturados como espinha dorsal — tudo referenciado a origem |
| **Playbooks** | Fluxos de investigação executáveis (análise de contatos, temporal, busca de pessoas) |
| **Watchlists** | Listas globais de monitoramento cross-case |
| **Auditoria** | Hash-chain append-only para todas as ações relevantes |

---

## Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR (Web)                          │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP
┌──────────────────────────▼──────────────────────────────────────┐
│                     sokol-api (FastAPI)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │  Auth    │ │  Search  │ │   Chat   │ │ Pipeline │           │
│  │  Cases   │ │  Hybrid  │ │  Agent   │ │ YOLO     │           │
│  │ Timeline │ │ pgvector │ │  Tools   │ │ Faces    │           │
│  │ Playbooks│ │          │ │          │ │ Plates   │           │
│  └──────────┘ └──────────┘ └──────────┘ │ ASR      │           │
│                                          └──────────┘           │
└───┬──────────┬───────────┬───────────┬───────────┬──────────────┘
    │          │           │           │           │
    ▼          ▼           ▼           ▼           ▼
┌────────┐ ┌─────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Postgres│ │sokol-   │ │sokol-  │ │sokol-  │ │sokol-  │
│  16    │ │embed    │ │vision  │ │face    │ │ocr     │
│+pgvec  │ │ Qwen3   │ │YOLO v8n│ │Insight │ │Paddle  │
│+postgis│ │Embedding│ │3 model │ │Face    │ │OCR     │
└────────┘ └─────────┘ └────────┘ └────────┘ └────────┘

┌────────┐ ┌────────┐
│sokol-  │ │sokol-  │
│asr     │ │plate   │
│Whisper │ │YOLO+OCR│
└────────┘ └────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     LM Studio (host)                             │
│              LLM para chat e reasoning                           │
└──────────────────────────────────────────────────────────────────┘
```

### Componentes

| Serviço | Porta | Responsabilidade |
|---------|-------|-----------------|
| `sokol-api` | `8000` | API gateway — auth, CRUD, busca, chat, pipeline, playbooks |
| `sokol-postgres` | `5433` | Banco de dados — pgvector + postgis |
| `sokol-embed` | `8001` | Serviço de embeddings (API OpenAI-compatible) |
| `sokol-vision` | `8007` | Detecção de objetos via YOLO (3 modelos) |
| `sokol-face` | `8011` | Reconhecimento facial com InsightFace |
| `sokol-ocr` | `8008` | OCR com PaddleOCR |
| `sokol-asr` | `8009` | Transcrição de áudio com faster-whisper |
| `sokol-plate` | `8010` | Detecção de placas veiculares |
| `sokol-web` | `5173` (dev) / `3000` (prod) | Frontend React + Vite |
| LM Studio | `1234` | LLM para chat (roda no host) |

---

## Pré-requisitos

- **Docker** e **Docker Compose** v2+
- **GPU** (opcional mas recomendado) — NVIDIA com CUDA para embeddings, YOLO e face
- **LM Studio** rodando no host com pelo menos um modelo LLM carregado
- **Git** para clonar o repositório

---

## Quick Start

### 1. Clonar e configurar

```bash
git clone https://github.com/geni-uff/sokol.git
cd sokol
cp deploy/env.example .env
# Edite .env conforme necessário
```

### 2. Iniciar a stack

```bash
cd deploy
docker compose --env-file ../.env up --build -d
```

### 3. Aplicar migrações do banco

```bash
docker exec sokol-api alembic upgrade head
```

### 4. Verificar saúde

```bash
curl http://localhost:8000/health
```

### 5. Acessar o frontend

Abra `http://localhost:3000` no navegador.

**Login padrão:** `admin` / `admin123`

### 6. Ingerir um caso

```bash
# Copie um arquivo .ufdr para o inbox
cp caso.ufdr ingest/

# Ingieira via API
curl -X POST http://localhost:8000/ingest \
  -H "Authorization: Bearer <token>" \
  -F "file=@caso.ufdr"
```

### 7. Rodar pipeline de detecção

Após ingestão, clique em **"Rodar Pipeline"** na aba Mídias para executar em paralelo:
- Detecção de objetos (YOLO)
- Reconhecimento facial (InsightFace)
- Detecção de placas
- Transcrição de áudio (ASR)

### 8. Parar

```bash
cd deploy
docker compose --env-file ../.env down
```

---

## Módulos Detalhados

### API (`api/`)

Gateway FastAPI com todos os endpoints da aplicação.

**Endpoints principais:**

| Rota | Método | Descrição |
|------|--------|-----------|
| `/health` | GET | Health check geral |
| `/auth/login` | POST | Autenticação, retorna JWT |
| `/cases` | GET/POST | Listar/criar casos |
| `/events/timeline` | GET | Timeline de eventos |
| `/search/exact` | GET | Busca exata |
| `/search/scan` | GET | Busca híbrida (lexical + semântica) |
| `/chat/agent` | POST | Chat investigativo com ferramentas |
| `/media/{case_id}` | GET | Listar mídia do caso |
| `/media/file/{hash}` | GET | Servir arquivo de mídia |
| `/detect/pipeline/{case_id}` | POST | Lançar pipeline de detecção paralelo |
| `/detect/status` | GET | Status dos jobs do pipeline |
| `/faces/{case_id}` | GET | Listar rostos detectados |
| `/faces/{case_id}/search` | POST | Busca cross-case de rostos |
| `/playbooks/` | GET/POST | Listar/criar playbooks |
| `/playbooks/{id}/execute` | POST | Executar playbook |
| `/plates/{case_id}` | GET | Listar placas detectadas |
| `/transcriptions/{case_id}` | GET | Listar transcrições (busca full-text) |
| `/watchlists/` | GET/POST | Watchlists globais |
| `/ingest` | POST | Ingerir UFDR |

### Banco de Dados (`db/`)

Postgres 16 com extensões `pgvector` (busca vetorial) e `postgis` (geoespacial).

**Principais tabelas:**

- `cases` — Casos investigativos
- `events` — Eventos estruturados (espinha da timeline)
- `messages` — Mensagens extraídas
- `chunks` — Chunks para busca com embeddings vetoriais
- `media` — Arquivos de mídia (hash, mime_type, size_bytes, storage_ref)
- `entities` — Entidades (pessoas, números, etc.)
- `artifacts` — Artefatos brutos
- `image_detections` — Detecções YOLO (armas, facas, etc.)
- `face_embeddings` — Embeddings faciais (InsightFace, 512-dim)
- `plate_detections` — Placas veiculares detectadas
- `transcriptions` — Transcrições de áudio (busca full-text)
- `playbooks` / `playbook_executions` / `playbook_results` — Playbooks investigativos
- `watchlists` — Listas de monitoramento globais
- `audit_log` — Log de auditoria com hash-chain

### Pipeline de Detecção (`api/src/sokol/pipeline.py`)

Executa 4 jobs em paralelo via threads:

1. **YOLO** — Processa imagens em batches de 16, salva em `image_detections`
2. **Faces** — InsightFace `buffalo_l`, salva embeddings em `face_embeddings`
3. **Placas** — YOLO + OCR + regex Mercosul, salva em `plate_detections`
4. **ASR** — faster-whisper com VAD, salva em `transcriptions`

Progresso rastreado via SSE (`_job_events`).

### Frontend (`web/`)

Aplicação React + Vite + TypeScript com interface operacional.

**Abas disponíveis:**

| Aba | Função |
|-----|--------|
| Timeline | Visualização cronológica de todos os eventos |
| Busca | Busca híbrida com filtros por tipo |
| Chat | Chat investigativo com IA |
| Dados | Resumo estatístico do caso |
| Mídia | Visualização de imagens + botão "Rodar Pipeline" |
| Rostos | Rostos detectados, busca cross-case, labeling |
| Placas | Placas veiculares detectadas |
| Voz | Transcrições de áudio com busca full-text |
| Playbooks | Fluxos de investigação executáveis |
| Relatórios | Geração de laudos |
| Operação | Status dos serviços |

### Watchlists (`api/src/sokol/watchlists.py`)

Listas globais de monitoramento que funcionam cross-case:

- Pessoas, organizações, placas, telefones, emails, IPs, CNPJ, CPF
- Endpoint de scan que verifica watchlists contra todos os casos
- Frontend com criação, edição e resultado de scan

### Playbooks (`api/src/sokol/playbooks.py`)

Fluxos de investigação com ações executáveis:

| Ação | Descrição |
|------|-----------|
| `extract_contacts` | Extrai contatos do caso |
| `map_communications` | Mapeia comunicações (actor/counterpart) |
| `analyze_patterns` | Analisa padrões por tipo de evento |
| `extract_timeline` | Extrai timeline completa |
| `detect_peaks` | Identifica picos de atividade |
| `search_mentions` | Busca menções a termos |
| `search_entity` | Busca entidades específicas |
| `generate_report` | Gera relatório |

### Dados Sintéticos (`synth/`)

```bash
cd synth
python -m synth --seed 42 --output ./output
```

---

## Variáveis de Ambiente

Copie `deploy/env.example` para `.env` e ajuste:

```bash
# Banco de dados
DATABASE_URL=postgresql://sokol:sua_senha@localhost:5433/sokol

# LM Studio (roda no host)
SOKOL_LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1

# GPU
SOKOL_GPU_PRIMARY=auto

# Embedding
SOKOL_DEFAULT_EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B

# Auth
SOKOL_JWT_SECRET=secret_mudar_em_producao
```

---

## Comandos Úteis

```bash
# Ver logs da API
docker logs -f sokol-api

# Reconstruir apenas a API
cd deploy && docker compose up -d --build sokol-api

# Acessar o banco
docker exec -it sokol-postgres psql -U sokol -d sokol

# Rodar migração
docker exec sokol-api alembic upgrade head

# Limpar imagens Docker não usadas
docker image prune -f
```

---

## Status

Versão atual: **v0.2.0** (Pipeline + ML services)

### Implementado

- [x] Stack Docker completa (API, Postgres, Frontend)
- [x] Autenticação JWT com Argon2
- [x] CRUD de casos com RBAC
- [x] Ingestão de UFDR com parsers estruturados (WhatsApp, SMS, chamadas, contatos, localização, web history)
- [x] Timeline unificada de eventos
- [x] Busca híbrida (lexical + semântica com pgvector)
- [x] Chat investigativo com ferramentas SQL
- [x] Serviço de embeddings — Qwen3-Embedding-0.6B
- [x] Serviço de visão — 3 modelos YOLO (COCO, firearm, threat)
- [x] Serviço de face — InsightFace buffalo_l (512-dim)
- [x] Serviço de OCR — PaddleOCR
- [x] Serviço de ASR — faster-whisper com VAD
- [x] Serviço de placas — YOLO + OCR + regex Mercosul
- [x] Pipeline de detecção paralelo (4 jobs simultâneos)
- [x] Reconhecimento facial com busca cross-case
- [x] Watchlists globais (10 tipos de entidades)
- [x] Playbooks investigativos (10+ ações executáveis)
- [x] Frontend React com 12 abas operacionais
- [x] Logo SOKOL no login e sidebar
- [x] Gerador de dados sintéticos
- [x] Scripts de backup e setup
- [x] Auditoria com hash-chain

### Pendente

- [ ] Worker de ingestão em container Docker
- [ ] Reranking de resultados de busca
- [ ] Relatórios PDF com cadeia de custódia
- [ ] Export de casos
- [ ] Backup automatizado via UI
- [ ] Testes E2E com Playwright
- [ ] Observabilidade (/ops page)
- [ ] Pendências UI — workflow de revisão de faces e placas

---

## Licença

Privado — uso interno da GENI/UFF. Não distribuir.
