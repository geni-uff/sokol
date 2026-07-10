# PLANO_NOVO.md - SOKOL

> Plano oficial de implementação do SOKOL.
> Data: 2026-07-08.
> Status: documento fonte para implementação.
>
> Os documentos anteriores foram arquivados em `OLD_DOCS/` e devem ser tratados
> apenas como contexto histórico. O SOKOL deve ser implementado como sistema novo.

---

## 0. Resumo executivo

SOKOL é um sistema forense local para transformar evidências digitais em dados
estruturados, pesquisáveis e auditáveis. A v1 deve provar o fluxo completo:
subir a stack, criar caso, ingerir corpus sintético/UFDR, popular mensagens e
eventos, buscar com fontes, responder via chat com ferramentas e gerar relatório
com cadeia de custódia.

Decisões centrais:

- Docker Compose novo, sem reaproveitar o compose antigo.
- Runtime principal em Docker; LM Studio/llmster pode rodar no host na v1.
- O usuário interage só pelo navegador.
- Arquivos locais entram por pasta de entrada montada; não há upload web na v1.
- Postgres 16 + `pgvector` + `postgis` como fonte de verdade única.
- UFDR estruturado direto em banco; DOCX/PDF apenas como saída.
- LM Studio/OpenAI-compatible para LLM; embedding roda em serviço Docker próprio.
- Modelos padrão configuráveis; embedding default é
  `Qwen/Qwen3-Embedding-0.6B`, mas BGE-M3 e outros podem ser registrados.
- GPU em modo `auto`; usuário não precisa saber quantidade nem índice de GPUs.
- Chat investigativo usa ferramentas SQL parametrizadas e RAG como ferramenta,
  não como única fonte de resposta.
- Toda ação relevante deve ser auditada em hash-chain.

### 0.1 Primeiro corte implementável

O primeiro marco útil não é o sistema completo. O primeiro corte deve entregar:

1. compose novo com Postgres, API, worker e LM Studio;
2. setup que gera `.env` com autodetecção de GPU;
3. migrations iniciais;
4. autenticação local e casos;
5. jobs com SSE;
6. corpus sintético mínimo;
7. ingestão estrutural que popula `messages` e `events`;
8. busca simples sobre eventos/mensagens.

Só depois disso entram busca híbrida, agente, mídia pesada, frontend completo e
relatórios.

### 0.2 Marcos de implementação

| Marco | Resultado esperado | Depende de |
| --- | --- | --- |
| M0 - Stack mínima | Compose novo sobe Postgres, API, worker e LM Studio com healthchecks | TODO-01, TODO-02, TODO-03 |
| M1 - Banco confiável | Migrations, RBAC, casos, jobs e audit log funcionando | TODO-04, TODO-05, TODO-08, TODO-09 |
| M2 - Corpus de teste | UFDR sintético e golden set reproduzíveis | TODO-10 |
| M3 - Ingestão estrutural | UFDR sintético popula `messages`, `events`, `media` sem DOCX | TODO-11, TODO-12 |
| M4 - Busca v1 | Chunks, embedding ativo, busca exata/híbrida e fontes estruturadas | TODO-06, TODO-07, TODO-13, TODO-14 |
| M5 - Chat v1 | Agente chama ferramentas, responde com fontes e passa no validador | TODO-15, TODO-16, TODO-17 |
| M6 - Produto mínimo | UI operacional, pendências simples e relatório com hashes | TODO-19, TODO-20, TODO-21 |
| M7 - Operação | Observabilidade, backup, restore e export de caso | TODO-22, TODO-23 |

### 0.3 Decisões fechadas e pendentes

| Tipo | Decisão | Status |
| --- | --- | --- |
| Banco | Postgres 16 + `pgvector` + `postgis` | Fechada |
| Vetores | Sem Weaviate na v1 | Fechada |
| LLM serving | LM Studio/OpenAI-compatible | Fechada |
| Embedding serving | `sokol-embed` Docker com contrato OpenAI-compatible | Fechada |
| Embedding default | `Qwen/Qwen3-Embedding-0.6B` | Fechada como default |
| Embeddings alternativos | BGE-M3 e outros via registro de modelos | Superseded por ADR-0006 (embedding fixado no deploy, sem migração em runtime) |
| GPU | Autodetecção com override manual | Fechada |
| UFDR | Estruturado direto em banco, sem DOCX intermediário | Fechada |
| Auditoria | Hash-chain append-only | Fechada |
| LM Studio runtime v1 | Host/headless ou app local, acessado por HTTP | Fechada |
| LM Studio em Docker | Containerização futura | Pendente de validação |
| LLM default | Modelo inicial recomendado no setup | Pendente de evals |
| Reranker default | Qwen3 Reranker vs BGE reranker | Pendente de evals |
| Face recognition | InsightFace `buffalo_l` | Fechada |
| Frontend stack | Node + React + Vite + TypeScript | Fechada |

### 0.4 Prioridades

| Prioridade | Significado | Itens |
| --- | --- | --- |
| P0 | Bloqueia qualquer v1 | TODO-00 a TODO-10 |
| P1 | Torna a v1 útil para investigação | TODO-11 a TODO-17 |
| P2 | Completa experiência operacional | TODO-18 a TODO-21 |
| P3 | Endurece operação e escala execução | TODO-22 a TODO-24 |

---

## 1. Decisões de arquitetura

### 1.1 O que o SOKOL é

SOKOL é uma plataforma forense local para ingestão, enriquecimento, busca,
chat investigativo e geração de relatórios a partir de evidências digitais.

O sistema deve ser:

- local-first;
- auditável;
- orientado a casos;
- estruturado antes de ser vetorial;
- executado por Docker Compose;
- configurável para uma ou mais GPUs;
- sem dependência fixa de uma máquina com exatamente duas GPUs.

### 1.2 O que o SOKOL não deve copiar

O SOKOL não deve replicar a arquitetura antiga como está.

Decisões proibidas no novo desenho:

- não usar DOCX como formato intermediário de UFDR;
- não indexar UFDR apenas como texto corrido;
- não usar arquivo `status.log` como protocolo principal de progresso;
- não manter estado crítico em memória do processo web;
- não usar Weaviate como segunda fonte de verdade;
- não usar Ollama;
- não reutilizar o `deploy/docker-compose.yml` antigo;
- não manter nomes, imagens ou containers `cerebro_*`.

### 1.3 Fonte de verdade

Postgres 16 deve ser a fonte de verdade única para:

- metadados;
- casos;
- artefatos;
- jobs;
- eventos;
- mensagens;
- chunks;
- vetores via `pgvector`;
- busca lexical via `tsvector`;
- dados geoespaciais via `postgis`;
- auditoria com hash-chain.

Vetores não devem ficar em banco separado na v1.

### 1.4 Execução por Docker e exceção LM Studio

Todos os componentes de execução devem rodar via Docker sempre que possível. Na
v1, LM Studio/llmster pode ser exceção operacional e rodar no host, porque esse
é o caminho mais simples e estável para servir LLM/embeddings localmente.

Mesmo com essa exceção, o usuário final deve abrir apenas a interface web para
operar o sistema. A configuração do LM Studio é tarefa de setup/admin.

Componentes que devem rodar em Docker:

- embedding textual;
- reranker;
- OCR/document parser;
- ASR;
- visão/triagem visual;
- face recognition;
- YOLO/placas.

Componentes que podem rodar no host na v1:

- LM Studio ou `llmster`;
- modelos LLM servidos por LM Studio;
- pasta local de entrada de evidências, montada como volume no Docker.

Contrato obrigatório para a exceção:

- expor API OpenAI-compatible em URL configurável;
- API e workers Docker acessam essa URL via `SOKOL_LMSTUDIO_BASE_URL`;
- trocar host/porta/provedor não pode exigir mudança de código;
- se LM Studio for containerizado depois, o contrato HTTP permanece igual.

Exceções aceitáveis no host:

- Docker/Docker Desktop;
- driver NVIDIA/runtime de GPU;
- navegador do usuário;
- pasta local de entrada de evidências, quando configurada como volume.

O futuro `deploy/docker-compose.yml` deve ser escrito do zero a partir deste
plano. O compose antigo fica arquivado em `OLD_DOCS/deploy/` e não é base.

---

## 2. Stack alvo

### 2.1 Serviços

| Serviço | Responsabilidade | Porta padrão |
| --- | --- | --- |
| `sokol-api` | API FastAPI, autenticação, contratos públicos, SSE, chat, busca, relatórios | `8000` |
| `sokol-web` | Frontend web | `3000` |
| `sokol-worker-ingest` | Fila de ingestão, parsing, chunking, enriquecimento | interno |
| `sokol-postgres` | Postgres 16 + pgvector + postgis | `5432` |
| `sokol-embed` | Embeddings textuais via API OpenAI-compatible | `8001` |
| `sokol-rerank` | Reranking de resultados | `8002` |
| `sokol-doc` | Docling/OCR para PDF, DOCX e imagens | `8005` |
| `sokol-asr` | faster-whisper + VAD + batch | `8006` |
| `sokol-vision` | embeddings/labels visuais | `8007` |
| `sokol-face` | detecção e embeddings faciais | `8003` |
| `sokol-plate` | YOLO detect -> crop -> OCR -> regex de placas | `8004` |

Serviço externo na v1:

| Serviço | Responsabilidade | Endpoint padrão |
| --- | --- | --- |
| LM Studio/llmster no host | LLM via API OpenAI-compatible | `http://host.docker.internal:1234/v1` |

### 2.2 Modelos padrão

| Função | Modelo padrão inicial | Observações |
| --- | --- | --- |
| Embedding textual | `Qwen/Qwen3-Embedding-0.6B` | default recomendado; pode ser trocado por perfil compatível, como BGE-M3 |
| LLM | definido no setup | deve ser configurável e servido pelo LM Studio/OpenAI-compatible |
| Reranker | `Qwen/Qwen3-Reranker-0.6B` ou `BAAI/bge-reranker-v2-m3` | configurável; escolher default por evals |
| ASR | `faster-whisper` | VAD ligado |
| OCR/docs | Docling + fallback OCR | sem subprocess por imagem |
| Face | InsightFace `buffalo_l` | usar como padrão |
| Placas | YOLO de placas + OCR | OCR nunca deve rodar direto na imagem inteira como estratégia principal |
| Visão | SigLIP/Qwen-VL embedding ou equivalente local | usado para triagem visual |

Regra de produto: o usuário deve receber modelos padrão funcionais, mas deve
poder alterar o modelo usado para LLM, embedding textual e reranker sem editar
código. A troca deve acontecer por UI administrativa ou `.env`.

Trocar LLM não exige reindexação. Trocar embedding textual pode exigir novo
índice, porque dimensão, normalização, instrução de query/documento e espaço
vetorial podem mudar.

### 2.3 LM Studio

Na v1, LM Studio/llmster deve rodar preferencialmente no host, fora do Docker, e
ser consumido pelos containers por HTTP para geração LLM. Isso reduz risco
operacional e evita travar o projeto na containerização do LM Studio.

Contrato obrigatório:

- expor endpoint OpenAI-compatible em URL configurável;
- default em Docker Desktop: `http://host.docker.internal:1234/v1`;
- default em Linux pode exigir gateway configurado pelo setup;
- suportar `POST /v1/chat/completions`;
- permitir configuração de modelo por variável de ambiente;
- operar em modo headless quando possível;
- ter healthcheck na API/worker, mesmo sendo serviço externo ao compose;
- não exigir operação manual da GUI em produção.

Containerizar LM Studio fica como evolução futura. A decisão principal é o
contrato HTTP OpenAI-compatible, não o local exato onde o runtime roda.

### 2.4 Serviço de embedding

Embeddings textuais devem rodar em `sokol-embed`, dentro do Docker. O serviço
deve expor contrato OpenAI-compatible para reduzir acoplamento:

- `POST /v1/embeddings`;
- `GET /health`;
- batch de textos como cidadão de primeira classe;
- modelo ativo configurável por `.env`/registro de modelos;
- validação explícita de dimensão;
- suporte inicial a `Qwen/Qwen3-Embedding-0.6B`;
- suporte planejado a `BAAI/bge-m3`.

Motivo: indexação em massa exige throughput, batching e previsibilidade melhores
do que depender do LM Studio para embedding.

### 2.5 Registro de modelos

> Nota (ADR-0006): a troca de **embedding** em runtime e a reindexação/índice
> paralelo estão superseded — o embedding é decidido por evals antes do deploy e
> fica fixo. As regras abaixo sobre troca de embedding aplicam-se apenas a LLM e
> reranker; para embedding, trocar = reindexar tudo offline, fora do produto.

O SOKOL deve manter um registro de modelos disponíveis. Esse registro pode
começar em arquivo YAML versionado e depois migrar para tabela administrativa.

Exemplo conceitual:

```yaml
llm_models:
  - id: default-llm
    provider: lmstudio
    model: change_me
    context_length: 32768
    enabled: true

embedding_models:
  - id: qwen3-embedding-0_6b
    provider: sokol-embed
    model: Qwen/Qwen3-Embedding-0.6B
    dimensions: 1024
    context_length: 32768
    query_prefix: ""
    document_prefix: ""
    enabled: true
    default: true
  - id: bge-m3
    provider: sokol-embed
    model: BAAI/bge-m3
    dimensions: 1024
    context_length: 8192
    query_prefix: ""
    document_prefix: ""
    enabled: false

rerank_models:
  - id: qwen3-reranker-0_6b
    provider: rerank-service
    model: Qwen/Qwen3-Reranker-0.6B
    enabled: true
```

Regras:

- o modelo default deve ser escolhido no setup;
- a UI administrativa deve listar modelos disponíveis e qual está ativo;
- o backend deve validar se o modelo selecionado realmente responde no endpoint;
- embedding selecionado deve declarar dimensão antes de indexar;
- cada chunk deve registrar `embedding_model_id`;
- busca deve usar somente chunks gerados pelo mesmo embedding ativo, salvo
  fluxo explícito de comparação/migração;
- trocar embedding deve criar plano de reindexação ou novo índice paralelo;
- se um modelo de embedding não puder ser servido diretamente pelo `sokol-embed`,
  ele só pode entrar se houver adapter Docker com o mesmo contrato
  OpenAI-compatible.

---

## 3. Configuração e GPUs

### 3.1 Regra geral

O SOKOL deve detectar GPUs automaticamente. O usuário não deve precisar saber
quantas GPUs existem nem seus índices para conseguir instalar e subir o sistema.

A configuração manual de GPU deve existir apenas como override avançado.

Regras:

- o setup deve detectar GPUs com `nvidia-smi --query-gpu=index,name,memory.total`;
- se houver 2 ou mais GPUs, o default é recomendar a GPU de maior VRAM para LM
  Studio no host e configurar outra GPU para serviços auxiliares Docker;
- se houver 1 GPU, todos os serviços usam a mesma GPU com concorrência reduzida;
- se não houver GPU, o setup deve selecionar perfil CPU quando configurado ou
  falhar com mensagem clara;
- o `.env` gerado pelo setup deve conter o resultado detectado;
- `auto` deve ser o valor padrão para usuários que não sabem o hardware.

### 3.2 Variáveis obrigatórias e autodetecção

```env
SOKOL_ENV=local

POSTGRES_DB=sokol
POSTGRES_USER=sokol
POSTGRES_PASSWORD=change_me
DATABASE_URL=postgresql://sokol:change_me@sokol-postgres:5432/sokol

SOKOL_API_PORT=8000
SOKOL_WEB_PORT=3000
SOKOL_LMSTUDIO_PORT=1234

SOKOL_LMSTUDIO_BASE_URL=http://host.docker.internal:1234/v1
SOKOL_DEFAULT_LLM_MODEL=change_me
SOKOL_ACTIVE_LLM_MODEL=${SOKOL_DEFAULT_LLM_MODEL}
SOKOL_ALLOWED_LLM_MODELS=change_me

SOKOL_EMBED_BASE_URL=http://sokol-embed:8001/v1
SOKOL_DEFAULT_EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B
SOKOL_ACTIVE_EMBED_MODEL=${SOKOL_DEFAULT_EMBED_MODEL}
SOKOL_ALLOWED_EMBED_MODELS=Qwen/Qwen3-Embedding-0.6B,BAAI/bge-m3
SOKOL_EMBED_PROVIDER=sokol-embed
SOKOL_EMBED_DIM=1024
SOKOL_EMBED_CONTEXT_LENGTH=32768

SOKOL_DEFAULT_RERANK_MODEL=Qwen/Qwen3-Reranker-0.6B
SOKOL_ACTIVE_RERANK_MODEL=${SOKOL_DEFAULT_RERANK_MODEL}

SOKOL_LLM_CONTEXT_LENGTH=32768

SOKOL_GPU_MODE=auto
SOKOL_GPU_LMSTUDIO=auto
SOKOL_GPU_AUX=auto
SOKOL_GPU_RERANK=auto
SOKOL_GPU_DOC=auto
SOKOL_GPU_ASR=auto
SOKOL_GPU_VISION=auto
SOKOL_GPU_FACE=auto
SOKOL_GPU_PLATE=auto

SOKOL_MAX_LLM_CONCURRENCY=auto
SOKOL_MAX_AUX_CONCURRENCY=auto

SOKOL_DATA_DIR=/data
SOKOL_FINAL_DIR=/data/final
SOKOL_STAGING_DIR=/data/staging
SOKOL_MEDIA_CACHE_DIR=/data/media-cache
SOKOL_HOST_INGEST_DIR=auto
SOKOL_CONTAINER_INGEST_DIR=/ingest/inbox
```

### 3.3 Perfis de hardware

O script de setup deve resolver `auto` para valores concretos antes de subir a
stack. O compose deve consumir variáveis resolvidas apenas para serviços Docker,
por exemplo `SOKOL_RESOLVED_GPU_AUX`. O LM Studio no host deve ser validado por
healthcheck HTTP, não controlado diretamente pelo compose.

Perfil com duas GPUs:

- setup recomenda a GPU com maior VRAM para LM Studio/llmster no host;
- setup escolhe outra GPU para serviços auxiliares Docker;
- concorrência auxiliar pode ser maior.

Perfil com uma GPU:

- setup aponta todos os serviços para a única GPU detectada;
- a concorrência deve ser menor;
- jobs pesados devem respeitar fila.

Perfil CPU:

- não é o perfil padrão;
- serviços que exigem CUDA devem falhar de forma explícita se não houver modo
  CPU configurado.

### 3.4 Overrides manuais

Usuários avançados podem substituir a autodetecção:

```env
SOKOL_GPU_MODE=manual
SOKOL_GPU_LMSTUDIO=0
SOKOL_GPU_AUX=1
SOKOL_GPU_RERANK=1
SOKOL_GPU_DOC=1
SOKOL_GPU_ASR=1
SOKOL_GPU_VISION=1
SOKOL_GPU_FACE=1
SOKOL_GPU_PLATE=1
SOKOL_MAX_LLM_CONCURRENCY=1
SOKOL_MAX_AUX_CONCURRENCY=2
```

Se `SOKOL_GPU_MODE=manual`, o setup deve validar que os índices informados
existem. Se algum índice for inválido, a inicialização deve falhar antes de
subir containers.

---

## 4. Contratos de banco

Migrations devem usar Alembic desde o início. Não criar tabelas manualmente em
runtime.

### 4.1 Casos e acesso

```sql
cases(
  id uuid primary key,
  name text not null,
  legal_ref text,
  status text not null,
  retention_policy text,
  reference_timezone text not null default 'America/Sao_Paulo', -- ADR-0007: fronteira do "dia" em consultas temporais
  created_at timestamptz not null
)

case_members(
  case_id uuid references cases(id),
  user_id uuid not null,
  role text not null, -- 'admin' | 'analista' | 'leitor' (ver CONTEXT.md)
  primary key(case_id, user_id)
)
```

Todo artefato, busca e resposta deve estar dentro de um `case_id`.

Busca cross-case deve ser exceção auditada, com justificativa explícita.

### 4.2 Evidências e mídia

```sql
documents(
  id uuid primary key,
  case_id uuid references cases(id),
  title text,
  source_type text not null,
  source_uri text,
  sha256 text,
  status text not null,
  created_at timestamptz not null
)

artifacts(
  id uuid primary key,
  case_id uuid references cases(id),
  document_id uuid references documents(id),
  kind text not null,
  source_member text,
  media_hash text,
  mime_type text,
  size_bytes bigint,
  status text not null,
  meta jsonb not null default '{}'::jsonb
)

media(
  hash text primary key,
  mime_type text,
  size_bytes bigint,
  storage_ref jsonb not null,
  thumbnail_ref text,
  created_at timestamptz not null
)
```

Mídia deve ser deduplicada por SHA-256. UFDR deve continuar como armazenamento
de origem; extração completa de mídia só deve ocorrer sob demanda ou para cache.

### 4.3 Mensagens e eventos

```sql
messages(
  id uuid primary key,
  case_id uuid references cases(id),
  device_id text,
  app text,
  chat_id text,
  sender text,
  counterpart text,
  ts timestamptz,
  direction text,
  text text,
  media_hash text references media(hash),
  is_forwarded boolean,
  meta jsonb not null default '{}'::jsonb
)

events(
  id uuid primary key,
  case_id uuid references cases(id),
  device_id text,
  ts timestamptz,
  tz_original text,
  kind text not null,
  actor text,
  counterpart text,
  app text,
  ref_table text not null,
  ref_id uuid not null,
  summary text not null,
  geo geography,
  meta jsonb not null default '{}'::jsonb
)
```

Perguntas de timeline, datas, chamadas, localizações e rotina devem consultar
`events` por SQL. Não usar RAG vetorial para responder o que é agregação,
contagem ou filtro temporal.

### 4.4 Chunks e busca

```sql
chunks(
  id uuid primary key,
  case_id uuid references cases(id),
  artifact_id uuid references artifacts(id),
  text text not null,
  embedding vector(1024),
  embedding_model_id text not null,
  embedding_dim int not null,
  tsv tsvector,
  ref jsonb not null,
  page_start int,
  page_end int,
  bbox jsonb,
  message_ids uuid[],
  created_at timestamptz not null
)
```

Índices obrigatórios:

- HNSW/IVFFlat em `embedding`;
- GIN em `tsv`;
- btree em `case_id`;
- btree em `events(case_id, ts)`;
- GIST/SP-GIST em `events.geo`;
- índices por `messages(case_id, chat_id, ts)`.

Se o embedding ativo usar dimensão diferente de 1024, a implementação deve criar
uma migration/índice compatível antes de permitir a troca. Não é permitido
gravar embeddings de dimensões diferentes na mesma coluna sem migração explícita.

### 4.5 Jobs

```sql
jobs(
  id uuid primary key,
  case_id uuid references cases(id),
  kind text not null,
  payload jsonb not null,
  status text not null,
  priority int not null default 100,
  attempts int not null default 0,
  max_attempts int not null default 3,
  pipeline_version text not null,
  claimed_by text,
  heartbeat_at timestamptz,
  created_at timestamptz not null,
  updated_at timestamptz not null,
  error text
)
```

Workers devem buscar jobs com:

```sql
SELECT *
FROM jobs
WHERE status = 'pending'
ORDER BY priority, created_at
FOR UPDATE SKIP LOCKED
LIMIT 1;
```

### 4.6 Auditoria

```sql
audit_log(
  id uuid primary key,
  case_id uuid,
  actor_user_id uuid,
  action text not null,
  payload jsonb not null,
  prev_hash text,
  hash text not null,
  created_at timestamptz not null
)
```

Regras:

- append-only;
- role da aplicação sem `UPDATE`/`DELETE` na tabela;
- cada registro calcula `hash = sha256(prev_hash || canonical_json(payload))`;
- job diário valida a cadeia;
- toda resposta do agente grava ferramentas chamadas, parâmetros e fontes.

### 4.7 Entidades e vínculos

Camada de entidades persistentes que sustenta grafo, watchlists e resolução de
identidade. Ver ADR-0002 (modelo genérico) e ADR-0008 (resolução não-destrutiva).

```sql
entities(
  id uuid primary key,
  case_id uuid references cases(id),
  kind text not null, -- 'identity' | 'phone' | 'email' | 'account' | 'device' | 'plate' | 'face' | 'contact'
  value text,         -- número, e-mail, placa normalizada, handle...
  display_name text,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null
)

entity_links(
  id uuid primary key,
  case_id uuid references cases(id),
  src_id uuid references entities(id),
  dst_id uuid references entities(id),
  kind text not null, -- 'resolves_to' | 'communicated_with' | 'contact_of' | 'appears_in' | ...
  weight double precision,
  confidence double precision,
  meta jsonb not null default '{}'::jsonb,
  created_at timestamptz not null
)
```

Regras:

- observação (`phone`, `contact`, `face`, `account`) liga-se a uma `identity`
  por aresta `resolves_to`; nunca por fusão destrutiva de linhas;
- mesclar identidades funde nós `identity` repontando arestas, de forma auditada;
- toda associação/reversão de identidade gera registro no `audit_log`;
- índices por `entities(case_id, kind, value)` e `entity_links(case_id, src_id)`
  e `entity_links(case_id, dst_id)`.

---

## 5. Contratos de API

Todos os endpoints públicos devem exigir autenticação, exceto `/health`.

### 5.1 Health

```http
GET /health
```

Resposta:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "services": {
    "postgres": "ok",
    "lmstudio": "ok",
    "embed": "ok"
  }
}
```

### 5.2 Casos

```http
POST /cases
GET /cases
GET /cases/{case_id}
```

`POST /cases`:

```json
{
  "name": "Operacao X",
  "legal_ref": "Mandado 0000000-00.2026.0.00.0000",
  "retention_policy": "default"
}
```

### 5.3 Ingestão

Arquivos do PC do usuário não devem ser passados para a API como caminhos locais
arbitrários. O navegador não dá acesso confiável a paths reais do host, e
containers não enxergam paths do host que não estejam montados.

Na v1 não haverá upload web. O fluxo de ingestão é por pasta local montada:

```http
GET /ingest/inbox
POST /ingest
```

Nesse modo, o setup configura uma pasta do host em `SOKOL_HOST_INGEST_DIR` e o
compose monta essa pasta em `SOKOL_CONTAINER_INGEST_DIR`, preferencialmente
read-only. A UI lista arquivos disponíveis e cria ingestão por `inbox_ref`.

```http
POST /ingest
```

Payload:

```json
{
  "case_id": "uuid",
  "source": {
    "type": "inbox",
    "inbox_ref": "evidencia.ufdr"
  },
  "source_type": "ufdr",
  "options": {
    "enrich_media": true
  }
}
```

Resposta:

```json
{
  "job_id": "uuid",
  "document_id": "uuid",
  "status": "pending"
}
```

Regras:

- `inbox_ref` deve ser relativo à pasta montada; nunca aceitar `../` ou path
  absoluto;
- o backend deve copiar ou hardlinkar para staging controlado antes de processar;
- toda ingestão registra hash SHA-256 antes do primeiro parser;
- a UI deve permitir escolher arquivos da pasta montada e iniciar ingestão;
- a UI deve mostrar progresso de cópia/importação para staging e depois progresso
  de parsing/enriquecimento/indexação.

### 5.4 Jobs e progresso

```http
GET /jobs/{job_id}
GET /events/jobs/{job_id}
```

`GET /events/jobs/{job_id}` deve usar SSE.

Eventos mínimos:

```json
{
  "job_id": "uuid",
  "stage": "ufdr_inventory",
  "status": "running",
  "progress": 0.42,
  "message": "Inventariando membros do UFDR",
  "updated_at": "2026-07-08T00:00:00Z"
}
```

Não usar polling de arquivo.

### 5.5 Busca

```http
POST /search/scan
POST /search/exact
```

`POST /search/scan`:

```json
{
  "case_id": "uuid",
  "query": "lavagem de dinheiro por empresas de fachada",
  "mode": "hybrid",
  "top_k": 30,
  "filters": {
    "date_from": "2026-03-01",
    "date_to": "2026-03-31",
    "artifact_kinds": ["document", "message"]
  }
}
```

Modos:

- `semantic`;
- `lexical`;
- `hybrid`;
- `exact-normalized`.

Busca híbrida deve combinar `pgvector` e `tsvector` por RRF, seguida de rerank.

### 5.6 Timeline e mensagens

```http
GET /timeline?case_id=&device_id=&date_from=&date_to=&kinds=
GET /messages?case_id=&chat_id=&sender=&date_from=&date_to=&contains=
GET /calls?case_id=&direction=&date_from=&date_to=&min_duration=
GET /media?case_id=&kind=&label=&date_from=&date_to=
GET /geo/events?case_id=&near=&radius_m=&date_from=&date_to=
```

Esses endpoints são ferramentas estruturadas do sistema e também devem ser
usados pelo agente.

### 5.7 Chat investigativo

```http
POST /chat/agent
```

Payload:

```json
{
  "case_id": "uuid",
  "session_id": "uuid",
  "question": "O que o usuário fez no dia 12/03?",
  "scope": {
    "device_id": "device-1"
  },
  "stream": true,
  "answer_style": "normal"
}
```

Resposta final:

```json
{
  "answer": "No dia 12/03, foram encontrados 214 eventos...",
  "sources": [
    {
      "origin_ref_table": "media",
      "origin_ref_id": "sha256:...",
      "event_id": "uuid",
      "label": "Foto com GPS - 12/03 08:30 (-03:00)"
    }
  ],
  "tool_calls": [
    {
      "name": "query_timeline",
      "arguments": {
        "date_from": "2026-03-12T00:00:00-03:00",
        "date_to": "2026-03-12T23:59:59-03:00"
      },
      "rows_returned": 214
    }
  ],
  "validation": {
    "status": "passed",
    "warnings": []
  }
}
```

Regras:

- o LLM escolhe ferramentas e parâmetros;
- o LLM nunca escreve SQL livre;
- ferramentas usam SQL parametrizado sobre views read-only;
- fatos numéricos devem vir de ferramentas;
- sem fonte, a resposta deve dizer que não há registro;
- todas as citações devem apontar para o registro de origem existente
  (message/media/documento+página), não para o event (ADR-0003);
- resultado automático não confirmado é indício, nunca afirmado como fato
  (ADR-0004);
- streaming deve ser via SSE.

### 5.8 Relatórios

```http
POST /reports/ipj
POST /reports/laudo
```

Relatórios são artefatos de saída, não formato intermediário.

Payload mínimo:

```json
{
  "case_id": "uuid",
  "format": "docx",
  "filters": {
    "date_from": "2026-03-01",
    "date_to": "2026-03-31",
    "chat_ids": ["chat-1"]
  },
  "bookmark_ids": []
}
```

Cada relatório deve incluir:

- fontes citadas;
- hashes SHA-256;
- origem da evidência;
- data de geração;
- usuário que gerou;
- manifest auditável.

### 5.9 Watchlists

```http
POST /watchlists
GET /watchlists
GET /watchlists/hits
```

```json
{
  "case_id": "uuid",
  "kind": "phone",
  "value": "+5541999999999",
  "active": true
}
```

Watchlists devem rodar durante ingestão e enriquecimento.

---

## 6. Pipeline de ingestão

### 6.0 Entrada de arquivos locais

A fronteira correta é:

```text
PC do usuário -> pasta local montada -> /ingest/inbox -> staging Docker -> worker
```

O worker nunca deve tentar abrir um path arbitrário do PC do usuário. Ele só
processa arquivos que já estejam em volumes controlados pela stack:

- `/data/staging`: arquivos enviados pela UI e validados;
- `/ingest/inbox`: pasta opcional do host montada no container;
- `/data/final`: artefatos preservados após ingestão.

Pasta de entrada montada é o fluxo padrão da v1:

1. operador configura ou escolhe uma pasta local no setup;
2. operador coloca arquivos nessa pasta;
3. API lista a pasta via endpoint autenticado;
4. usuário seleciona o arquivo na UI;
5. API copia ou hardlinka para staging controlado;
6. API calcula SHA-256 e cria job de ingestão;
7. worker processa sem depender do path original do usuário.

Importação, ingestão e enriquecimento têm progressos separados (ADR-0001 e
CONTEXT.md). Importação mede cópia/hash/snapshot; ingestão mede parsing, dedupe e
indexação textual (`tsv`/busca exata) — é o marco em que o caso vira consultável;
enriquecimento (OCR/ASR/visão/face/placa e embedding vetorial que habilita busca
semântica/híbrida) roda depois, com o caso já usável.

### 6.1 UFDR

O UFDR deve ser processado sem extração massiva e sem geração de DOCX.

Fluxo:

1. inventariar o ZIP pelo central directory;
2. classificar membros como SQLite, XML, mídia, documentos e outros;
3. calcular SHA-256 dos membros relevantes;
4. gravar `documents` e `artifacts`;
5. fazer parse streaming de `report.xml`;
6. extrair SQLites necessários para staging controlado;
7. popular `messages`, `events`, `media`;
8. enfileirar enriquecimentos por artefato;
9. gerar chunks de conversa com referências a `message_ids`;
10. embedar chunks em batch com o embedding ativo, default
    `Qwen/Qwen3-Embedding-0.6B`;
11. liberar consulta parcial assim que mensagens/eventos estiverem gravados.

Aceite mínimo:

- UFDR grande deve ficar consultável estruturalmente em minutos, antes do fim de
  OCR/ASR/faces/placas;
- crash de worker deve retomar pelo checkpoint;
- reingestão do mesmo UFDR deve deduplicar mídia e pular trabalho já concluído.

### 6.2 Conversas

Mensagens devem ser armazenadas como linhas estruturadas.

Chunks para RAG devem ser janelas de conversa:

- por chat;
- com período;
- com participantes;
- com `message_ids`;
- com texto suficiente para contexto sem perder rastreabilidade.

### 6.3 Documentos avulsos

PDF/DOCX/imagens devem passar por `sokol-doc`.

Regras:

- se PDF já tem camada de texto, não OCRizar página inteira;
- tabelas e layout devem ser preservados quando possível;
- bboxes devem ser armazenados quando disponíveis;
- OCR deve rodar como serviço persistente, nunca como subprocess por imagem.

### 6.4 Áudio e vídeo

Áudio:

- `sokol-asr`;
- faster-whisper;
- VAD;
- timestamps por segmento;
- batch.

Vídeo:

- extrair áudio para ASR;
- extrair keyframes;
- processar keyframes por OCR/visão/faces/placas.

### 6.5 Placas

Pipeline obrigatório:

1. YOLO detecta região de placa;
2. crop é normalizado;
3. OCR roda no crop;
4. regex valida Mercosul e placa antiga;
5. resultados de baixa confiança viram pendência humana.

OCR na imagem inteira só pode ser fallback.

### 6.6 Faces

Faces detectadas devem criar pendências humanas quando não houver identidade
validada.

Contrato:

- embeddings faciais ficam associados a pessoa/identidade;
- matches automáticos têm score e limiar;
- decisões humanas são auditadas;
- fusões arriscadas exigem confirmação.

---

## 7. Busca, RAG e agente

### 7.1 Busca híbrida

O modo híbrido combina:

- busca vetorial em `chunks.embedding`;
- busca lexical em `chunks.tsv`;
- fusão por RRF;
- rerank;
- retorno com fontes estruturadas.

Busca exata normalizada deve usar SQL, removendo acentos, espaços duplicados e
diferenças simples de pontuação.

### 7.2 Embedding

Embedding textual:

- modelo default: `Qwen/Qwen3-Embedding-0.6B`;
- modelos alternativos permitidos: qualquer modelo registrado e validado, como
  `BAAI/bge-m3`;
- serving default: LM Studio/OpenAI-compatible;
- dimensão default: 1024;
- dimensão configurável conforme o perfil do modelo;
- contexto conforme o perfil do modelo;
- armazenamento inicial: `vector(1024)`;
- cada chunk grava `embedding_model_id` e `embedding_dim`.

Troca de embedding exige uma das duas estratégias:

- reindexar os chunks existentes com o novo modelo; ou
- criar índice paralelo e restringir busca ao `embedding_model_id` ativo.

Qualquer mudança de dimensão exige migration/reindexação planejada antes da
ativação do modelo.

### 7.3 Seleção de modelos em runtime

> Nota (ADR-0006): vale para **LLM** e **reranker**. O **embedding** é fixo pós-eval
> e não é trocável em runtime; ignore aqui as partes de troca de embedding ativo,
> validação de dimensão em produção e reindexação como feature.

O SOKOL deve permitir alterar modelos sem mudar código:

- LLM ativo: usado imediatamente em novas respostas;
- embedding ativo: usado em novas indexações e buscas apenas contra chunks do
  mesmo modelo;
- reranker ativo: usado imediatamente em novas buscas.

Mudanças de modelo devem ser auditadas:

```json
{
  "action": "model.changed",
  "model_type": "embedding",
  "previous_model": "Qwen/Qwen3-Embedding-0.6B",
  "new_model": "BAAI/bge-m3",
  "requires_reindex": true,
  "changed_by": "user_id"
}
```

Antes de ativar um embedding novo, o backend deve rodar validação:

- endpoint responde;
- dimensão retornada bate com o perfil;
- embedding de query e documento é estável;
- índice compatível existe ou job de reindexação foi criado;
- evals mínimos passam ou a UI mostra aviso de modelo não validado.

### 7.4 Chat investigativo

O chat deve ser tool-first, não RAG-first.

Ferramentas mínimas:

- `query_timeline`;
- `query_messages`;
- `query_calls`;
- `query_media`;
- `query_geo`;
- `query_graph`;
- `semantic_search`.

Fluxo v1:

1. LLM recebe pergunta;
2. LLM chama uma ou mais ferramentas;
3. backend executa ferramentas com SQL parametrizado;
4. LLM sintetiza resposta;
5. validador determinístico verifica fontes, datas e contagens;
6. se falhar, há no máximo um retry;
7. se continuar falhando, entrega com avisos explícitos.

### 7.5 Playbooks

Playbooks são workflows versionados, mais determinísticos que o chat livre.

Playbooks v1:

- `triagem-ufdr`;
- `relatorio-do-dia`;
- `perfil-do-alvo`;
- `vinculos`;
- `padrao-de-vida`.

Devem ser definidos em YAML ou tabela versionada, com plano fixo e síntese LLM
apenas no final.

---

## 8. Frontend

Frontend deve ser implementado em Node, com uma interface moderna, futurista,
minimalista e elegante. Deve priorizar uso investigativo, não landing page.

Stack fechada para v1:

- Node LTS;
- React;
- Vite;
- TypeScript;
- Tailwind CSS;
- shadcn/ui ou componentes equivalentes com Radix primitives;
- TanStack Query para estado remoto;
- SSE nativo para progresso e streaming;
- Playwright para testes end-to-end.

Direção visual:

- visual futurista, limpo e sofisticado;
- fundo escuro técnico, com contraste alto e poucos acentos luminosos;
- evitar paleta monocromática exagerada;
- layouts densos, claros e operacionais;
- cards apenas para itens repetidos, modais e ferramentas enquadradas;
- nada de hero/landing page;
- tipografia discreta, sem texto gigante fora de contexto;
- microinterações sutis, sem animações que atrapalhem análise;
- foco em legibilidade de evidências, fontes, datas, status e alertas.

Componentes esperados:

- sidebar compacta de casos e módulos;
- topbar com status de serviços, caso ativo e usuário;
- painéis de filtros persistentes;
- seletor de pasta de entrada montada para operadores/admins;
- navegador de arquivos da pasta montada;
- progresso de importação para staging com validação de hash;
- tabelas densas para eventos, jobs e evidências;
- timeline visual com filtros por tipo, pessoa, app e período;
- chat com fontes clicáveis e validação visível;
- badges de confiança para OCR, face, placa e labels automáticos;
- viewers de conversa, documento, mídia e relatório.

### 8.1 Mapa de interface

Shell global:

- sidebar esquerda: casos, ingestão, timeline, busca, chat, mídia, pendências,
  relatórios e operação;
- topbar: caso ativo, seletor de caso, status dos serviços, fila ativa,
  notificações, usuário e menu de configurações;
- área principal: tela do módulo atual;
- painel lateral direito opcional: filtros, fontes selecionadas, detalhes de
  evidência ou contexto do chat;
- rodapé discreto de status: versão, conexão SSE e último evento recebido.

Controles globais:

- botão `Novo caso`;
- botão `Selecionar caso`;
- botão `Importar evidência`;
- botão `Abrir chat`;
- botão `Gerar relatório`;
- botão `Exportar`;
- botão `Atualizar`;
- menu `Configurações`;
- indicador de saúde: API, Postgres, LM Studio, embed, worker e GPU.

### 8.2 Áreas e ações por módulo

Login:

- campos usuário e senha;
- botão `Entrar`;
- estado de erro claro para credencial inválida;
- sem branding promocional ou texto explicativo longo.

Casos:

- tabela/lista de casos com nome, referência legal, status, membros e última
  atividade;
- botões `Novo caso`, `Abrir`, `Arquivar`, `Exportar caso`;
- filtros por status e texto;
- criação de caso em modal enxuto.

Ingestão:

- navegador da pasta montada `/ingest/inbox`;
- tabela com nome, tamanho, tipo provável, data, hash quando disponível e status;
- botões `Recarregar pasta`, `Importar selecionados`, `Calcular hash`,
  `Remover da seleção`;
- barra de progresso de importação para staging;
- barra separada para ingestão/parsing/enriquecimento/indexação;
- painel de detalhes do arquivo selecionado;
- aviso quando a pasta montada não estiver acessível pelo container.

Jobs:

- tabela densa com job, caso, tipo, estágio, progresso, tentativas, worker,
  heartbeat e erro;
- botões `Cancelar`, `Reexecutar`, `Ver logs`, `Abrir evidências geradas`;
- filtros por status, tipo, caso e período;
- estados visuais para `pending`, `running`, `failed`, `done` e `cancelled`.

Timeline:

- visualização cronológica por hora/dia;
- filtros por período, dispositivo, app, tipo de evento, pessoa, telefone,
  placa, mídia e confiança;
- botões `Abrir fonte`, `Adicionar bookmark`, `Enviar para chat`,
  `Exportar seleção`;
- alternância lista/timeline compacta;
- cada evento deve mostrar fonte, timestamp, resumo e badges.

Busca:

- campo de busca principal;
- seletor de modo `híbrida`, `exata`, `semântica`, `lexical`;
- filtros por caso, período, tipo de artefato, pessoa, placa e mídia;
- botões `Buscar`, `Limpar`, `Criar conjunto`, `Enviar resultados ao chat`;
- resultados com score, tipo, preview, fonte e ações `Abrir`, `Bookmark`,
  `Copiar referência`.

Chat investigativo:

- lista de sessões;
- caixa de pergunta com botão `Enviar`;
- botão `Parar geração`;
- seletor de escopo: caso inteiro, evidências selecionadas, período ou entidade;
- indicação das ferramentas chamadas;
- painel de fontes por parágrafo;
- status de validação: aprovado, aviso ou falhou;
- ações `Abrir fonte`, `Adicionar ao laudo`, `Criar bookmark`, `Copiar resposta`.

Viewer de conversa:

- layout de mensagens por participante, semelhante a chat forense;
- filtros por remetente, período, mídia, termo e direção;
- botões `Abrir mídia`, `Ver evento`, `Bookmark`, `Enviar trecho ao chat`;
- preservação de timestamp, app, dispositivo e origem.

Viewer de documento:

- painel de páginas;
- highlight por bbox quando disponível;
- busca interna;
- lista de citações relacionadas;
- botões `Abrir original`, `Bookmark`, `Adicionar ao relatório`,
  `Copiar citação`.

Mídia:

- galeria densa com imagens, vídeos e áudios;
- filtros por label, face, placa, período, GPS e confiança;
- blur por padrão para categorias sensíveis;
- botões `Revelar`, `Abrir`, `Bookmark`, `Enviar ao chat`, `Resolver pendência`;
- player de áudio/vídeo com transcrição sincronizada quando existir.

Pendências:

- abas `Faces`, `Placas`, `Identidades`;
- fila de revisão com imagem/crop, score, origem e sugestões;
- botões `Confirmar`, `Corrigir`, `Descartar`, `Mesclar identidade`,
  `Pedir revisão`;
- toda decisão deve exigir confirmação e gerar auditoria.

Mapa:

- mapa com eventos georreferenciados;
- filtros por período, dispositivo, pessoa e tipo de evento;
- botões `Traçar rota`, `Ver eventos próximos`, `Enviar seleção ao chat`;
- suporte a modo offline/tiles locais quando definido.

Grafo:

- visualização de entidades e vínculos;
- filtros por tipo de entidade e força do vínculo;
- botões `Expandir 1-hop`, `Caminho entre entidades`, `Abrir evidências`,
  `Enviar subgrafo ao chat`;
- layout deve ser legível, sem animações excessivas.

Relatórios:

- lista de bookmarks e evidências selecionadas;
- builder por seções;
- botões `Adicionar seção`, `Gerar rascunho`, `Validar fontes`,
  `Exportar DOCX`, `Exportar PDF`;
- prévia com fontes, hashes e manifest.

Operação:

- status de serviços;
- uso de GPU, fila, disco e últimos erros;
- botões `Recarregar health`, `Ver logs`, `Reprocessar falhas`,
  `Rodar backup`, `Testar restore`;
- acesso restrito a administradores.

### 8.3 Estados de UI obrigatórios

Cada tela operacional deve tratar:

- vazio: sem dados ainda, com próxima ação clara;
- carregando: skeleton/loading compacto;
- erro: mensagem objetiva, causa provável e ação disponível;
- sem permissão: explicar qual permissão falta;
- processo em andamento: progresso e cancelamento quando suportado;
- concluído: resumo do que mudou e link para próxima ação.

Telas em ordem de implementação:

1. login e seleção de caso;
2. seleção de arquivo da pasta montada e ingestão com progressos separados;
3. painel de jobs;
4. timeline com filtros;
5. chat investigativo com streaming e fontes clicáveis;
6. busca textual/exata/híbrida;
7. viewer de conversas;
8. viewer de documentos com highlight;
9. galeria de mídia com labels e blur por padrão para categorias sensíveis;
10. pendências humanas de faces e placas;
11. mapa geoespacial;
12. grafo de vínculos;
13. bookmarks;
14. builder de laudo.

Sem texto promocional dentro da aplicação. A primeira tela após login deve ser
operacional.

---

## 9. Segurança e cadeia de custódia

Requisitos desde a v1:

- autenticação local;
- senha com Argon2;
- sessão segura;
- RBAC por caso;
- segredos gerados no setup, fora do repositório;
- `.env` real ignorado;
- audit log hash-chain;
- SHA-256 de todo artefato ingerido;
- export de caso com manifest;
- logs de ferramenta do agente;
- bloqueio de cross-case sem permissão e justificativa.

---

## 10. Docker Compose novo

O compose novo deve ser criado depois deste plano.

Regras:

- escrever `deploy/docker-compose.yml` do zero;
- incluir perfis `gpu` e, se viável, `cpu`;
- usar nomes `sokol-*`;
- não referenciar imagens antigas;
- não usar Weaviate;
- não usar Ollama;
- não codificar GPUs fixas;
- não exigir que o usuário informe quantidade ou índice de GPUs;
- consumir variáveis de GPU resolvidas pelo setup, preservando override manual;
- cada serviço deve ter healthcheck;
- volumes devem ser nomeados;
- dados devem ficar sob `./data`;
- staging, final e media-cache devem ser volumes/pastas explícitos;
- pasta de entrada do host deve ser opcional e montada em `/ingest/inbox`;
- containers não devem receber paths arbitrários do PC do usuário;
- modelos/cache devem ficar em volumes explícitos;
- secrets reais devem vir de `.env`, nunca do compose.

Serviços mínimos no compose v1:

```yaml
services:
  postgres:
  embed:
  api:
  web:
  worker-ingest:
  rerank:
  doc:
  asr:
  vision:
  face:
  plate:
```

O `deploy/env.example` novo deve refletir apenas variáveis SOKOL.

---

## 11. Evals e testes

### 11.1 Dados sintéticos

Criar gerador de corpus sintético:

- UFDR falso;
- `report.xml`;
- SQLite de chats;
- chamadas;
- contatos;
- localizações;
- histórico web;
- fotos com EXIF;
- áudios curtos;
- gabarito JSON.

Não desenvolver contra evidência real.

### 11.2 Golden set

Criar 30 a 80 perguntas por corpus:

- busca por CPF;
- busca por telefone;
- busca por placa;
- pergunta por data;
- pergunta por rotina;
- vínculo entre pessoas;
- busca sem resposta;
- pergunta que exige RAG textual;
- pergunta que exige SQL estruturado.

Métricas:

- recall@k;
- MRR;
- citações válidas;
- groundedness;
- latência p50/p95;
- falhas de ferramenta;
- regressão de respostas PT-BR.
- regressão por troca de LLM, embedding e reranker.

### 11.3 Testes mínimos

- migrations sobem do zero;
- ingestão de UFDR sintético;
- worker retoma após kill;
- dedupe por SHA-256;
- embeddings gravados com dimensão correta;
- `embedding_model_id` gravado em todo chunk;
- troca de LLM sem reindexação;
- troca de embedding bloqueada até validar dimensão e criar plano de
  reindexação ou índice paralelo;
- busca híbrida retorna fontes;
- chat chama ferramenta correta para perguntas temporais;
- validador rejeita citação inexistente;
- relatório inclui hashes;
- RBAC bloqueia acesso a caso alheio.

---

## 12. Roadmap

### Fase 0 - Fundação

- monorepo;
- Docker Compose novo;
- Postgres + pgvector + postgis;
- migrations;
- auth local;
- audit log;
- jobs;
- LM Studio/llmster no host acessível pelos containers para LLM;
- `sokol-embed` Docker funcionando via `/v1/embeddings`;
- registro de modelos com perfis para `Qwen/Qwen3-Embedding-0.6B` e
  `BAAI/bge-m3`;
- corpus sintético mínimo;
- harness de evals.

### Fase 1 - Ingestão estruturada

- UFDR inventory;
- parse `report.xml`;
- parse WhatsApp/SMS/chamadas/localizações/contatos;
- `messages` e `events`;
- jobs retomáveis;
- dedupe de mídia;
- chunks de conversa;
- busca estrutural inicial.

### Fase 2 - Busca e RAG

- embedding em batch;
- seleção de embedding ativo;
- proteção contra mistura de embeddings incompatíveis;
- pgvector + tsvector;
- busca híbrida;
- rerank;
- citações estruturadas;
- viewer básico.

### Fase 3 - Mídia e enriquecimento

- OCR/docs;
- ASR;
- visão;
- faces;
- placas com YOLO;
- pendências humanas.

### Fase 4 - Chat investigativo

- tool-calling;
- ferramentas SQL read-only;
- validador determinístico;
- streaming;
- playbooks.

### Fase 5 - Relatórios e operação

- bookmarks;
- IPJ sob demanda;
- laudo builder;
- export de caso;
- backup/restore;
- observabilidade;
- instalador.

---

## 13. Critérios de aceite da v1

O SOKOL v1 estará pronto quando:

- roda por Docker Compose novo;
- não depende do compose antigo;
- detecta GPUs automaticamente no setup;
- sobe sem o usuário informar quantidade ou índice de GPUs;
- permite override manual de GPU por `.env`;
- LM Studio/llmster no host serve LLM via OpenAI-compatible;
- containers alcançam `SOKOL_LMSTUDIO_BASE_URL`;
- `sokol-embed` serve embeddings via OpenAI-compatible dentro do Docker;
- existe modelo padrão para LLM, embedding e reranker;
- usuário administrador consegue alterar LLM ativo sem editar código;
- usuário administrador consegue selecionar outro embedding registrado, como
  BGE-M3, com validação e reindexação/índice paralelo quando necessário;
- embedding ativo gera vetores gravados no Postgres com `embedding_model_id`;
- UFDR sintético é ingerido sem DOCX intermediário;
- mensagens e eventos ficam consultáveis antes do fim do enriquecimento;
- busca híbrida retorna fontes estruturadas;
- chat responde perguntas temporais usando ferramentas SQL;
- relatório DOCX/PDF é gerado sob demanda com hashes;
- audit log hash-chain registra ingestão, busca, chat e relatório;
- RBAC por caso funciona;
- evals rodam e comparam baseline.

---

## 14. Observações de implementação

- Priorizar contratos estáveis antes de otimizações.
- Manter cada serviço ML com `/health` e endpoint batch.
- Evitar abstrações genéricas antes do primeiro corpus sintético rodar.
- Não aceitar resposta LLM sem fonte em contexto factual.
- Tratar modelos como configuração. `Qwen/Qwen3-Embedding-0.6B` é o default
  recomendado de v1, não o único embedding permitido.
- Não permitir troca silenciosa de embedding em base já indexada; exigir
  validação, auditoria e estratégia de reindexação ou índice paralelo.
- Registrar `pipeline_version` em todo enriquecimento para permitir backfill
  seletivo.
- Toda decisão humana sobre face, placa, identidade ou evidência deve ser
  auditada.

---

## 15. TODOs de planificação

Esta lista transforma o roadmap em tarefas planejáveis. A ordem abaixo é a
ordem recomendada para reduzir risco: primeiro contratos e ambiente mínimo,
depois ingestão estruturada, depois busca, agente, mídia e operação.

### TODO-00 - Fechar escopo da v1

Objetivo: impedir que a v1 vire um clone completo de tudo ao mesmo tempo.

Etapas:

1. Definir corpus alvo da v1: UFDR sintético + PDF/DOCX avulso + algumas
   imagens com placa/rosto.
2. Definir funcionalidades obrigatórias da v1: caso, ingestão, eventos,
   mensagens, busca híbrida, chat com ferramentas, relatório simples e auditoria.
3. Definir funcionalidades fora da v1: grafo visual avançado, speaker-id,
   migração completa do sistema antigo, alta disponibilidade e integrações
   externas.
4. Transformar os critérios de aceite da seção 13 em checklist de release.

Entregável: seção curta `Escopo v1` no plano ou em issue/PRD separado.

Pronto quando: qualquer implementador sabe o que entra e o que não entra na
primeira entrega.

### TODO-01 - Criar layout do repositório

Objetivo: estabelecer a estrutura física antes de escrever serviços.

Etapas:

1. Criar diretórios `api/`, `web/`, `worker/`, `services/`, `db/`, `deploy/`,
   `ops/`, `evals/`, `synth/` e `docs/`.
2. Escolher gerenciador Python (`uv` recomendado) e versão única de Python.
3. Criar `README.md` com comandos mínimos de desenvolvimento.
4. Criar `.gitignore` cobrindo `.env`, dados, caches, modelos e artefatos.
5. Criar `deploy/env.example` novo, apenas com variáveis `SOKOL_*`.

Entregável: esqueleto do monorepo com documentação mínima de boot.

Pronto quando: um desenvolvedor consegue clonar, instalar dependências e ver
quais serviços existirão, mesmo que ainda estejam vazios.

### TODO-02 - Especificar Docker Compose do zero

Objetivo: criar a base operacional sem herdar o compose antigo.

Etapas:

1. Criar `deploy/docker-compose.yml` novo com nomes `sokol-*`.
2. Incluir serviços mínimos: postgres, embed, api, web, worker-ingest, rerank,
   doc, asr, vision, face e plate.
3. Adicionar healthchecks em todos os serviços.
4. Definir volumes de dados, staging, final, media-cache, cache de modelos e
   Postgres.
5. Usar perfis `gpu` e, se viável, `cpu`.
6. Adicionar mount opcional de `SOKOL_HOST_INGEST_DIR` em
   `SOKOL_CONTAINER_INGEST_DIR`.
7. Consumir variáveis resolvidas pelo setup para GPU, sem hardcode de índices.

Entregável: compose novo que sobe Postgres e serviços stub/health.

Pronto quando: `docker compose --env-file deploy/.env up` sobe a stack mínima
sem referenciar arquivos ou imagens do Cerebro.

### TODO-03 - Criar setup com autodetecção de GPU

Objetivo: permitir instalação sem o usuário saber quantas GPUs existem.

Etapas:

1. Criar script `ops/setup` para gerar `.env` a partir de `env.example`.
2. Detectar GPUs com `nvidia-smi --query-gpu=index,name,memory.total`.
3. Resolver `SOKOL_GPU_MODE=auto` para variáveis concretas.
4. Recomendar GPU de maior VRAM para LM Studio/llmster no host quando houver 2
   ou mais GPUs.
5. Configurar serviços auxiliares Docker na outra GPU, quando disponível.
6. Usar a única GPU com concorrência reduzida quando houver 1 GPU.
7. Validar overrides manuais quando `SOKOL_GPU_MODE=manual`.
8. Perguntar ou detectar pasta local opcional para ingestão de arquivos enormes.
9. Validar se Docker Desktop pode montar a pasta escolhida.
10. Falhar cedo com mensagem clara quando GPU for exigida e não existir.

Entregável: script de setup idempotente.

Pronto quando: o mesmo setup gera `.env` correto em máquina com 0, 1 ou 2+
GPUs, sem edição manual obrigatória.

### TODO-04 - Subir Postgres com extensões e migrations

Objetivo: criar a fonte de verdade do sistema.

Etapas:

1. Configurar Postgres 16 no compose.
2. Habilitar `pgvector`, `postgis`, `unaccent` e extensões necessárias para UUID.
3. Criar Alembic no diretório `db/`.
4. Implementar migrations iniciais para `cases`, `case_members`, `documents`,
   `artifacts`, `media`, `messages`, `events`, `chunks`, `jobs` e `audit_log`.
5. Criar índices mínimos de `case_id`, datas, `tsvector`, vetor e geografia.
6. Criar seed opcional de usuário admin local.

Entregável: banco sobe do zero por migration.

Pronto quando: `alembic upgrade head` cria o schema completo em banco limpo.

### TODO-05 - Implementar auditoria hash-chain

Objetivo: garantir rastreabilidade forense desde o início.

Etapas:

1. Definir formato canônico do payload JSON auditado.
2. Criar função de inserção que calcula `prev_hash` e `hash`.
3. Revogar `UPDATE` e `DELETE` da role da aplicação sobre `audit_log`.
4. Criar helper no backend para registrar ações.
5. Criar verificador da cadeia inteira.
6. Registrar eventos mínimos: login, criação de caso, ingestão, troca de modelo,
   busca, chat, relatório e decisão humana.

Entregável: módulo de auditoria usado pela API.

Pronto quando: qualquer alteração relevante gera registro append-only e o
verificador detecta adulteração manual.

### TODO-06 - Criar registro e seleção de modelos

Objetivo: dar modelos padrão, mas permitir troca segura.

Etapas:

1. Criar arquivo `models.yaml` inicial ou tabela administrativa equivalente.
2. Registrar LLM default, `Qwen/Qwen3-Embedding-0.6B`, `BAAI/bge-m3` e reranker
   default.
3. Criar validação de endpoint: modelo responde, dimensão bate, contexto é
   compatível.
4. Criar API administrativa para listar modelos e escolher modelo ativo.
5. Auditar toda troca de modelo.
6. Bloquear troca de embedding quando não houver índice compatível ou job de
   reindexação planejado.

Entregável: configuração central de modelos.

Pronto quando: administrador troca LLM sem reindexar e tenta trocar embedding
com validação explícita de impacto.

### TODO-07 - Integrar LM Studio/headless no host

Objetivo: padronizar LLM pelo contrato OpenAI-compatible.

Etapas:

1. Instalar/configurar LM Studio ou `llmster` no host.
2. Expor API OpenAI-compatible em `SOKOL_LMSTUDIO_BASE_URL`.
3. Garantir que containers alcançam essa URL.
3. Criar client interno compatível com OpenAI para chat.
4. Implementar healthcheck de modelos carregados/disponíveis.
5. Testar `POST /v1/chat/completions`.

Entregável: wrapper de LLM usado pela API e pelo agente.

Pronto quando: API dentro do Docker consegue gerar resposta usando somente
`SOKOL_LMSTUDIO_BASE_URL`.

### TODO-07A - Implementar sokol-embed Docker

Objetivo: servir embeddings textuais em Docker com throughput e batch
previsíveis.

Etapas:

1. Criar serviço `sokol-embed` com `/health`.
2. Expor `POST /v1/embeddings` compatível com OpenAI.
3. Carregar `Qwen/Qwen3-Embedding-0.6B` como default.
4. Permitir perfil alternativo `BAAI/bge-m3`.
5. Aceitar batch de textos.
6. Retornar dimensão validável por modelo.
7. Testar throughput com corpus sintético.

Entregável: serviço Docker de embeddings.

Pronto quando: worker gera embeddings em batch via `SOKOL_EMBED_BASE_URL` sem
depender do LM Studio.

### TODO-08 - Criar API base e autenticação

Objetivo: ter superfície pública mínima e segura.

Etapas:

1. Criar FastAPI em `api/`.
2. Implementar `/health`.
3. Implementar usuários locais com senha Argon2.
4. Implementar sessão ou token local.
5. Implementar RBAC por caso.
6. Implementar endpoints de casos: `POST /cases`, `GET /cases`,
   `GET /cases/{case_id}`.
7. Registrar auditoria para autenticação e criação de casos.

Entregável: API autenticada com casos.

Pronto quando: usuário autenticado cria caso e usuário sem permissão não acessa
caso alheio.

### TODO-09 - Implementar fila de jobs

Objetivo: tornar ingestão e enriquecimento retomáveis.

Etapas:

1. Criar repositório de jobs com `FOR UPDATE SKIP LOCKED`.
2. Implementar estados: `pending`, `running`, `done`, `failed`, `cancelled`.
3. Implementar `attempts`, `max_attempts`, backoff e heartbeat.
4. Implementar retomada de jobs órfãos.
5. Criar endpoints `GET /jobs/{job_id}` e `GET /events/jobs/{job_id}`.
6. Emitir progresso por SSE.

Entregável: worker genérico e protocolo de progresso.

Pronto quando: matar o worker no meio de um job faz outro worker retomar sem
duplicar resultado.

### TODO-10 - Criar corpus sintético e golden set

Objetivo: desenvolver sem evidência real e medir regressões.

Etapas:

1. Gerar UFDR sintético com `report.xml`.
2. Gerar SQLite de conversas com mensagens em português.
3. Gerar chamadas, contatos, localizações e histórico web.
4. Gerar imagens com EXIF e alguns casos de placa/rosto.
5. Gerar áudios curtos ou stubs com transcrição esperada.
6. Criar gabarito JSON com fatos verdadeiros.
7. Criar 30 a 80 perguntas de golden set.

Entregável: pacote sintético reprodutível.

Pronto quando: o mesmo seed gera o mesmo corpus e o mesmo gabarito.

### TODO-11 - Implementar ingestão UFDR fase 1

Objetivo: tornar UFDR consultável estruturalmente sem DOCX.

Etapas:

1. Implementar listagem segura da pasta montada `/ingest/inbox`.
2. Criar `POST /ingest` aceitando `inbox_ref`.
3. Implementar importação para `/data/staging` com cópia/hardlink quando seguro.
4. Implementar inventário do ZIP sem extração massiva.
5. Classificar membros por tipo.
6. Calcular SHA-256 dos membros relevantes.
7. Criar `documents` e `artifacts`.
8. Parsear `report.xml` por streaming.
9. Extrair SQLites necessários para staging controlado.
10. Popular `messages`, `events` e `media`.
11. Criar jobs de enriquecimento para mídia.
12. Emitir progresso via SSE.

Entregável: ingestão estrutural de UFDR.

Pronto quando: após ingestão parcial, timeline e mensagens já aparecem antes de
OCR/ASR/faces terminarem.

### TODO-12 - Implementar parsers estruturados

Objetivo: cobrir os tipos de evidência que geram eventos.

Etapas:

1. Criar contrato comum de parser: entrada, artefatos gerados, eventos gerados e
   erros recuperáveis.
2. Implementar parser WhatsApp.
3. Implementar parser SMS.
4. Implementar parser chamadas.
5. Implementar parser contatos.
6. Implementar parser localizações.
7. Implementar parser histórico web.
8. Planejar parsers SkyECC e Cellebrite XLS como entradas equivalentes a
   `messages` e `events`.

Entregável: pacote de parsers com testes por fixture.

Pronto quando: cada parser popula tabelas estruturadas e cria eventos com
`ref_table/ref_id`.

### TODO-13 - Implementar chunking e embedding

Objetivo: criar a camada textual pesquisável sem perder rastreabilidade.

Etapas:

1. Definir chunking de conversa por chat, período e número de mensagens.
2. Gerar texto com cabeçalho contextual.
3. Guardar `message_ids` em cada chunk.
4. Criar batch embedding pelo modelo ativo.
5. Gravar `embedding`, `embedding_model_id` e `embedding_dim`.
6. Gerar `tsvector`.
7. Impedir indexação se dimensão retornada divergir do perfil ativo.

Entregável: chunks pesquisáveis por vetor e texto.

Pronto quando: o corpus sintético gera chunks com fontes resolvíveis até a
mensagem original.

### TODO-14 - Implementar busca híbrida

Objetivo: permitir busca semântica, lexical e exata com fontes.

Etapas:

1. Implementar busca vetorial por `pgvector`.
2. Implementar busca lexical por `tsvector`.
3. Implementar busca exata normalizada com `unaccent` e normalização de espaços.
4. Combinar resultados por RRF no modo híbrido.
5. Aplicar rerank quando serviço estiver saudável.
6. Retornar fontes estruturadas e previews.
7. Restringir busca ao `embedding_model_id` ativo.

Entregável: `POST /search/scan` e `POST /search/exact`.

Pronto quando: golden set mede recall@k e citações válidas.

### TODO-15 - Implementar ferramentas estruturadas do agente

Objetivo: responder perguntas que são SQL, não RAG.

Etapas:

1. Criar views read-only para timeline, mensagens, chamadas, mídia, geo e grafo.
2. Criar schemas Pydantic de parâmetros.
3. Implementar `query_timeline`.
4. Implementar `query_messages`.
5. Implementar `query_calls`.
6. Implementar `query_media`.
7. Implementar `query_geo`.
8. Implementar `semantic_search`.
9. Garantir SQL parametrizado, sem SQL livre vindo do LLM.

Entregável: biblioteca de ferramentas do agente.

Pronto quando: cada ferramenta tem teste com corpus sintético e retorna fontes
auditáveis.

### TODO-16 - Implementar chat investigativo v1

Objetivo: responder perguntas combinando ferramentas e síntese LLM.

Etapas:

1. Criar `POST /chat/agent`.
2. Definir prompt de sistema com regras de aterramento.
3. Permitir tool-calling para ferramentas estruturadas.
4. Executar ferramentas no backend.
5. Sintetizar resposta com fontes.
6. Fazer streaming por SSE.
7. Registrar plano, chamadas, parâmetros e fontes no audit log.

Entregável: chat investigativo funcional.

Pronto quando: pergunta como "o que ocorreu em 12/03?" chama timeline, não
busca vetorial pura.

### TODO-17 - Implementar validador determinístico

Objetivo: impedir resposta factual sem sustentação.

Etapas:

1. Validar que toda citação aponta para registro existente.
2. Validar que datas citadas pertencem ao intervalo solicitado.
3. Validar contagens e durações contra retorno das ferramentas.
4. Validar que fontes pertencem ao mesmo `case_id`.
5. Retornar avisos explícitos quando a validação falhar.
6. Permitir no máximo um retry de síntese com feedback do validador.

Entregável: camada de validação usada em todo chat.

Pronto quando: resposta com fonte inexistente é rejeitada ou entregue com aviso
explícito, nunca silenciosamente aceita.

### TODO-18 - Implementar serviços de mídia como contratos Docker

Objetivo: preparar enriquecimento sem acoplar modelos ao worker.

Etapas:

1. Criar `sokol-doc` com `/health` e `/parse`.
2. Criar `sokol-asr` com `/health` e `/transcribe`.
3. Criar `sokol-vision` com `/health`, `/embed_image` e `/classify`.
4. Criar `sokol-face` com `/health`, `/detect`, `/embed` e `/compare`.
5. Criar `sokol-plate` com `/health` e `/detect`.
6. Garantir batch nos serviços que processam muitos itens.
7. Registrar `pipeline_version` nos resultados.

Entregável: serviços ML substituíveis por contrato HTTP.

Pronto quando: worker consegue chamar cada serviço por HTTP e persistir resultado
com status e versão.

### TODO-19 - Implementar pendências humanas

Objetivo: separar automação de decisão pericial.

Etapas:

1. Criar pendências para faces desconhecidas.
2. Criar pendências para placas de baixa confiança.
3. Criar tela/API para resolver pendências.
4. Auditar decisão humana.
5. Associar decisão a pessoa, veículo ou identidade.
6. Permitir correção posterior preservando histórico.

Entregável: fluxo de revisão humana.

Pronto quando: resultado incerto não entra como fato validado sem ação humana.

### TODO-20 - Implementar frontend operacional mínimo

Objetivo: tornar o backend utilizável por analistas.

Etapas:

1. Criar app Node com React, Vite, TypeScript e Tailwind.
2. Definir tema visual futurista, minimalista e elegante.
3. Montar shell operacional: sidebar, topbar, status de serviços e caso ativo.
4. Implementar estados globais: vazio, carregando, erro, sem permissão,
   andamento e concluído.
5. Tela de login.
6. Lista e criação de casos.
7. Navegador da pasta montada com seleção de arquivos.
8. Importação para staging com progresso próprio.
9. Ingestão com progresso SSE separado da importação.
10. Painel de jobs com ações cancelar/reexecutar/ver logs.
11. Timeline com filtros e ações por evento.
12. Busca híbrida/exata com resultados e fontes.
13. Chat com streaming, fontes clicáveis, ferramentas chamadas e status de
    validação.
14. Viewer simples de conversa e documento.
15. Primeira versão de bookmarks e envio de evidências ao chat.
16. Testar telas principais com Playwright.

Entregável: UI v1 Node/React sem landing page.

Pronto quando: um usuário consegue criar caso, ingerir corpus sintético, buscar,
abrir fonte e perguntar ao chat.

### TODO-21 - Implementar relatórios sob demanda

Objetivo: trazer DOCX/PDF de volta como saída auditável.

Etapas:

1. Criar bookmarks de evidências.
2. Gerar relatório IPJ simples por filtro.
3. Gerar laudo a partir de bookmarks.
4. Incluir hashes, origem e fontes.
5. Registrar relatório no audit log.
6. Salvar manifest do relatório.

Entregável: `POST /reports/ipj` e `POST /reports/laudo`.

Pronto quando: relatório gerado permite rastrear cada afirmação até evidência e
hash de origem.

### TODO-22 - Implementar observabilidade e operação

Objetivo: operar o sistema sem depender do desenvolvedor.

Etapas:

1. Criar página `/ops`.
2. Mostrar saúde dos serviços.
3. Mostrar fila por estágio.
4. Mostrar jobs falhos e últimos erros.
5. Mostrar uso de GPU quando disponível.
6. Mostrar latência p50/p95 de busca e chat.
7. Criar alerta simples para fila parada e disco baixo.

Entregável: painel operacional mínimo.

Pronto quando: operador identifica serviço parado, fila travada ou falha de
modelo sem ler logs manualmente.

### TODO-23 - Implementar backup, restore e export de caso

Objetivo: proteger dados e cadeia de custódia.

Etapas:

1. Criar backup diário de Postgres.
2. Criar rotina de restore em banco temporário.
3. Criar export de caso com manifest SHA-256.
4. Incluir audit log do caso no export.
5. Incluir referências a mídias e artefatos de origem.
6. Testar restore mensal automaticamente.

Entregável: scripts em `ops/`.

Pronto quando: backup restaurado passa queries de sanidade e export de caso tem
manifest verificável.

### TODO-24 - Criar matriz de dependências

Objetivo: orientar execução paralela por múltiplos devs/agentes.

Etapas:

1. Marcar cada TODO com dependências.
2. Separar trilhas paralelas: infraestrutura, ingestão, frontend, ML services e
   evals.
3. Identificar bloqueadores de v1.
4. Marcar tarefas que podem virar issues independentes.
5. Definir marcos semanais.

Entregável: tabela de dependências no tracker ou no plano.

Pronto quando: é possível distribuir tarefas sem dois implementadores decidirem
contratos diferentes.

### Ordem sugerida de execução

1. TODO-00 a TODO-05: fundação e segurança.
2. TODO-06 a TODO-10: modelos, LM Studio, embedding Docker, API base, jobs e
   evals.
3. TODO-11 a TODO-14: ingestão, parsers, chunks e busca.
4. TODO-15 a TODO-17: ferramentas, chat e validação.
5. TODO-18 a TODO-21: mídia, pendências, frontend e relatórios.
6. TODO-22 a TODO-24: operação, backup e organização para escala.

### Matriz compacta de dependências

| TODO | Prioridade | Bloqueia | Observação |
| --- | --- | --- | --- |
| TODO-00 | P0 | todos | fecha escopo e evita expansão prematura |
| TODO-01 | P0 | TODO-02, TODO-04, TODO-08 | cria layout comum |
| TODO-02 | P0 | TODO-03, TODO-07, TODO-18 | base operacional Docker |
| TODO-03 | P0 | TODO-07, TODO-18 | resolve GPU sem intervenção do usuário |
| TODO-04 | P0 | TODO-05, TODO-09, TODO-11, TODO-13 | schema e extensões |
| TODO-05 | P0 | TODO-06, TODO-08, TODO-16, TODO-21 | auditoria desde o início |
| TODO-06 | P0 | TODO-07, TODO-07A, TODO-13, TODO-14 | modelos e embeddings seguros |
| TODO-07 | P0 | TODO-16 | LM Studio operacional para LLM |
| TODO-07A | P0 | TODO-13, TODO-14 | embedding Docker operacional |
| TODO-08 | P0 | TODO-11, TODO-16, TODO-20 | API segura e casos |
| TODO-09 | P0 | TODO-11, TODO-18 | jobs retomáveis |
| TODO-10 | P0 | TODO-11, TODO-14, TODO-16 | corpus e regressão |
| TODO-11 | P1 | TODO-13, TODO-15, TODO-20 | ingestão estrutural |
| TODO-12 | P1 | TODO-11, TODO-15 | parsers por tipo |
| TODO-13 | P1 | TODO-14, TODO-16 | chunks e vetores |
| TODO-14 | P1 | TODO-16, TODO-20 | busca com fontes |
| TODO-15 | P1 | TODO-16, TODO-17 | ferramentas do agente |
| TODO-16 | P1 | TODO-17, TODO-20, TODO-21 | chat investigativo |
| TODO-17 | P1 | TODO-21 | validação factual |
| TODO-18 | P2 | TODO-19 | mídia pesada |
| TODO-19 | P2 | TODO-20, TODO-21 | revisão humana |
| TODO-20 | P2 | release v1 | experiência mínima |
| TODO-21 | P2 | release v1 | relatório auditável |
| TODO-22 | P3 | operação | diagnóstico |
| TODO-23 | P3 | operação | backup/export |
| TODO-24 | P3 | execução paralela | governança do backlog |

### Trilhas paralelas sugeridas

- Infraestrutura: TODO-01, TODO-02, TODO-03, TODO-04, TODO-09.
- Segurança e auditoria: TODO-05, TODO-08, TODO-23.
- Modelos e evals: TODO-06, TODO-07, TODO-07A, TODO-10, TODO-13, TODO-14.
- Ingestão: TODO-11, TODO-12, TODO-18, TODO-19.
- Agente: TODO-15, TODO-16, TODO-17.
- Produto: TODO-20, TODO-21, TODO-22.
