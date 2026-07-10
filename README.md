# SOKOL — Sistema Operacional de Konhecimento e Organização Local

Plataforma forense local para ingestão, enriquecimento, busca, chat investigativo
e geração de relatórios a partir de evidências digitais.

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
| **Visão computacional** | Detecção de objetos via YOLO (armas, facas, granadas, explosivos) em imagens |
| **Timeline unificada** | Eventos estruturados como espinha dorsal — tudo referenciado a origem |
| **Auditoria** | Hash-chain append-only para todas as ações relevantes |
| **Relatórios** | Geração de laudos com cadeia de custódia |

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
│  │  Auth    │ │  Search  │ │   Chat   │ │  Media   │           │
│  │  Cases   │ │  Hybrid  │ │  Agent   │ │  Vision  │           │
│  │ Timeline │ │ pgvector │ │  Tools   │ │  YOLO    │           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘           │
└───┬──────────────┬───────────────┬──────────────────────────────┘
    │              │               │
    ▼              ▼               ▼
┌────────┐  ┌───────────┐  ┌──────────────┐
│Postgres│  │sokol-embed│  │sokol-vision  │
│  16    │  │  Qwen3    │  │  YOLO v8n    │
│+pgvec  │  │ Embedding │  │  3 modelos   │
│+postgis│  └───────────┘  └──────────────┘
└────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     LM Studio (host)                             │
│              LLM para chat e reasoning                           │
└──────────────────────────────────────────────────────────────────┘
```

### Componentes

| Serviço | Porta | Responsabilidade |
|---------|-------|-----------------|
| `sokol-api` | `8000` | API gateway — auth, CRUD, busca, chat, mídia, visão |
| `sokol-postgres` | `5433` | Banco de dados — pgvector + postgis |
| `sokol-embed` | `8001` | Serviço de embeddings (API OpenAI-compatible) |
| `sokol-vision` | `8007` | Detecção de objetos via YOLO |
| `sokol-web` | `5173` (dev) / `3000` (prod) | Frontend React + Vite |
| `sokol-worker` | — | Worker de ingestão e enriquecimento |
| LM Studio | `1234` | LLM para chat (roda no host) |

---

## Pré-requisitos

- **Docker** e **Docker Compose** v2+
- **GPU** (opcional mas recomendado) — NVIDIA com CUDA para embeddings e YOLO
- **LM Studio** rodando no host com pelo menos um modelo LLM carregado
- **Git** para clonar o repositório

### GPU

O sistema detecta automaticamente GPUs disponíveis. Para forçar um device:

```bash
# No .env
SOKOL_GPU_PRIMARY=cuda:0
SOKOL_GPU_AUX=cuda:0
```

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

Resposta esperada:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "postgres": "ok",
    "lmstudio": "ok"
  }
}
```

### 5. Acessar o frontend

Abra `http://localhost:3000` no navegador.

**Login padrão:** `admin` / `admin123`

### 6. Parar

```bash
cd deploy
docker compose --env-file ../.env down
```

---

## Módulos Detalhados

### API (`api/`)

Gateway FastAPI com todos os endpoints da aplicação.

```bash
# Desenvolvimento local
cd api
uv sync
uv run uvicorn src.sokol.main:app --reload --port 8000

# Produção (Docker)
docker build -t sokol-api -f api/Dockerfile .
docker run -p 8000:8000 --env-file .env sokol-api
```

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
| `/vision/{case_id}/detections` | GET | Detecções visuais |
| `/ingest` | POST | Ingerir UFDR |

### Banco de Dados (`db/`)

Postgres 16 com extensões `pgvector` (busca vetorial) e `postgis` (geoespacial).

```bash
# Rodar migrações
docker exec sokol-api alembic upgrade head

# Criar nova migração
cd api
uv run alembic revision --autogenerate -m "descrição"
```

**Principais tabelas:**

- `cases` — Casos investigativos
- `events` — Eventos estruturados (espinha da timeline)
- `messages` — Mensagens extraídas
- `chunks` — Chunks para busca com embeddings vetoriais
- `media` — Arquivos de mídia
- `entities` — Entidades (pessoas, números, etc.)
- `artifacts` — Artefatos brutos
- `image_detections` — Detecções de visão computacional
- `audit_log` — Log de auditoria com hash-chain

### Worker (`worker/`)

Worker de ingestão e enriquecimento de dados.

```bash
# Rodar worker
cd worker
python -m worker

# Ingerir um caso específico
python -m worker --case-id <uuid>
```

**Pipeline de ingestão:**

1. **Parsing** — Extrai dados do UFDR (XML → eventos, mensagens, entidades)
2. **Chunking** — Divide texto em chunks para embedding
3. **Embedding** — Gera vetores via sokol-embed
4. **Vision** — Roda detecção YOLO nas imagens
5. **Indexação** — Salva tudo no Postgres com pgvector

**Parsers disponíveis:** WhatsApp, SMS, Chamadas, Contatos, Localização, Web History, Contratos

### Serviço de Embeddings (`services/embed/`)

Serviço Docker que expõe API OpenAI-compatible para geração de embeddings.

```bash
# Build
cd services/embed
docker build -t sokol-embed .

# Run
docker run -p 8001:8001 sokol-embed
```

**Modelo padrão:** `Qwen/Qwen3-Embedding-0.6B` (1024 dimensões)

### Serviço de Visão (`services/vision/`)

Serviço Docker com 3 modelos YOLO para detecção de objetos:

| Modelo | Classes | Uso |
|--------|---------|-----|
| **COCO** (yolov8n) | 80 classes padrão | Pessoas, carros, celulares |
| **Firearm Detection** | Armas de fogo | Detecção de armas |
| **Threat Detection** | Armas, explosivos, granadas | Triagem de ameaças |

```bash
# Build
cd services/vision
docker build -t sokol-vision .

# Run
docker run -p 8007:8007 -v ./data/media-cache:/data/media-cache sokol-vision
```

### Frontend (`web/`)

Aplicação React + Vite + TypeScript com interface operacional.

```bash
# Desenvolvimento
cd web
npm install
npm run dev   # http://localhost:5173

# Build para produção
npm run build
# Os arquivos ficam em web/dist/
```

**Abas disponíveis:**

| Aba | Função |
|-----|--------|
| Timeline | Visualização cronológica de todos os eventos |
| Busca | Busca híbrida com filtros por tipo |
| Chat | Chat investigativo com IA |
| Dados | Resumo estatístico do caso |
| Bookmarks | Marcadores do investigador |
| Watchlists | Alertas de monitoramento |
| Pendências | Itens que precisam de atenção |
| Mídia | Visualização de imagens com filtros de detecção |
| Grafo | Mapa de relações entre entidades |
| Playbooks | Fluxos de investigação |
| Relatórios | Geração de laudos |
| Operação | Status dos serviços |

### Dados Sintéticos (`synth/`)

Gerador de UFDR sintético para testes reproduzíveis.

```bash
# Gerar corpus sintético
cd synth
python -m synth --seed 42 --output ./output

# O output inclui:
# - report.xml (estrutura UFDR)
# - files/ (imagens, áudios, vídeos sintéticos)
# - golden_set.json (ground truth para testes)
# - synthetic_data.json
```

### Scripts Operacionais (`ops/`)

| Script | Função |
|--------|--------|
| `setup` | Setup inicial — detecta GPU, gera `.env` |
| `backup.py` | Backup do banco de dados |
| `extract_media.py` | Extrai imagens de UFDR para cache |

```bash
# Setup inicial
cd ops
./setup

# Backup
python backup.py --output ./backups/

# Extrair mídia
python extract_media.py --ufdr /caminho/para/ufdr --output ../data/media-cache/
```

### Avaliações (`evals/`)

Benchmarks e golden tests para validação do sistema.

```bash
cd evals
python bench_embeddings.py        # Benchmark de embeddings
python generate_corpus_100.py     # Gerar corpus de 100 documentos
```

---

## Variáveis de Ambiente

Copie `deploy/env.example` para `.env` e ajuste:

```bash
# Banco de dados
POSTGRES_DB=sokol
POSTGRES_USER=sokol
POSTGRES_PASSWORD=sua_senha
DATABASE_URL=postgresql://sokol:sua_senha@localhost:5433/sokol

# LM Studio (roda no host)
SOKOL_LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1

# GPU
SOKOL_GPU_PRIMARY=auto
SOKOL_GPU_AUX=auto

# Embedding
SOKOL_DEFAULT_EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B
SOKOL_EMBED_DIM=1024

# Vision
SOKOL_VISION_CONF=0.25

# Auth
SOKOL_JWT_SECRET=secret_mudar_em_producao
```

---

## Desenvolvimento

### Estrutura do Repositório

```
sokol/
├── api/              # FastAPI gateway
├── worker/           # Ingestão e enriquecimento
├── services/         # Serviços Docker (embed, vision)
├── web/              # Frontend React
├── db/               # Migrações Alembic
├── deploy/           # Docker Compose
├── ops/              # Scripts operacionais
├── synth/            # Gerador sintético
├── evals/            # Benchmarks e testes
├── docs/             # ADRs e documentação
├── config/           # Configurações
├── ingest/           # Inbox para UFDRs
└── .scratch/         # Issue tracker local
```

### Comandos Úteis

```bash
# Ver logs da API
docker logs -f sokol-api

# Ver logs do worker
docker logs -f sokol-worker

# Reconstruir apenas a API
cd deploy && docker compose up -d --build sokol-api

# Acessar o banco
docker exec -it sokol-postgres psql -U sokol -d sokol

# Rodar migração
docker exec sokol-api alembic upgrade head
```

### Testes

```bash
# Gerar dados sintéticos
cd synth && python -m synth --seed 42 --output ./output

# Benchmark de embeddings
cd evals && python bench_embeddings.py

# Testar busca
curl "http://localhost:8000/search/scan?case_id=<uuid>&q=arma&mode=hybrid"
```

---

## Segurança

- **Nunca** commite arquivos `.env`, credenciais ou evidências forenses
- O `.gitignore` exclui `data/`, `*.ufdr`, `.env`, caches de modelo
- Senhas devem ser definidas via variáveis de ambiente
- Em produção, mude `SOKOL_JWT_SECRET` e `POSTGRES_PASSWORD`
- Logs de auditoria são append-only com hash-chain para integridade

---

## Status

Versão atual: **v0.1.0** (MVP funcional)

### Implementado

- [x] Stack Docker completa (API, Postgres, Worker, Frontend)
- [x] Autenticação JWT
- [x] CRUD de casos
- [x] Ingestão de UFDR com parsers estruturados
- [x] Timeline unificada de eventos
- [x] Busca híbrida (lexical + semântica)
- [x] Chat investigativo com ferramentas
- [x] Serviço de embeddings (sokol-embed)
- [x] Serviço de visão (sokol-vision) com 3 modelos YOLO
- [x] Detecção de armas, facas, granadas, explosivos
- [x] Visualização de mídia com filtros de detecção
- [x] Frontend React com todas as abas
- [x] Gerador de dados sintéticos
- [x] Scripts de backup e setup

### Pendente

- [ ] Embedding de chunks na ingestão (só eventos por enquanto)
- [ ] Reconhecimento facial (InsightFace)
- [ ] OCR otimizado para documentos
- [ ] ASR para áudio/vídeo
- [ ] Extração de placas veiculares
- [ ] Relatórios PDF com cadeia de custódia
- [ ] Export de casos
- [ ] Backup automatizado

---

## Licença

Privado — uso interno da GENI/UFF. Não distribuir.
