<p align="center">
  <img src="logo_sokol.png" alt="SOKOL" width="480" />
</p>

<h3 align="center">Plataforma de Análise e Investigação Forense</h3>

<p align="center">
  Sistema Operacional de Conhecimento e Organização Local — ingestão, enriquecimento,
  busca, Agent investigativo e geração de laudos a partir de evidências digitais.
  Tudo roda na máquina, via Docker Compose, sem serviços externos.
</p>

<p align="center"><strong>v0.8.2</strong> · 1.0.0 só quando o produto estiver completo</p>

---

## O que é

O SOKOL transforma evidências brutas (UFDR Cellebrite, documentos, mídia) em dados
estruturados, pesquisáveis e auditáveis, sempre escopados por **caso** (`case_id`).

| Capacidade | O que faz |
|-----------|-----------|
| **Ingestão** | UFDR (XML Cellebrite + walker FileSystem/iCloud), mensagens, chamadas, contatos, GPS, web, e-mail, mídia |
| **Busca híbrida** | Lexical (`tsvector`) + semântica (`pgvector`) com reranking |
| **Agent** | Pergunta-e-resposta com ferramentas SQL; respostas com **Sources** |
| **Pipeline de detecção** | YOLO, rostos, placas, OCR, transcrição — em amostra ou em tudo (aba Mídia) |
| **Índice textual / vetorial** | Busca: Indexar texto (`tsv`); Indexar vetores (`pgvector`) para o Agent |
| **Timeline e mapa** | Eventos no fuso do caso; geo via PostGIS |
| **Playbooks e laudos** | Fluxos determinísticos e relatórios HTML com cadeia de custódia |
| **Watchlists e pendências** | Seletores globais; fila humana Indicator → Fact |
| **Cross-case e identidades** | Comparação auditada (Admin); resolução não-destrutiva (`resolves_to`) |
| **Auditoria** | `audit_log` append-only com hash-chain |

Vocabulário: [`CONTEXT.md`](CONTEXT.md). ADRs: [`docs/adr/`](docs/adr/). Agentes: [`CLAUDE.md`](CLAUDE.md). Versão: [`docs/VERSIONING.md`](docs/VERSIONING.md).

**Login de desenvolvimento:** `admin` / `admin123` (admin de plataforma: `/admin`, backup, troca de modelos).

---

## Início rápido

1. Copiar `deploy/env.example` → `.env` e definir `POSTGRES_PASSWORD`.
2. `mkdir -p data/media-cache data/staging data/backups`
3. Abrir o **LM Studio** no host, carregar o LLM com contexto **32768** (ver [Modelos](#modelos-llm-embedding-e-reranker)), servidor na porta **1234**.
4. Subir a stack:

```bash
cd deploy && docker compose --env-file ../.env up --build -d
docker exec sokol-api alembic upgrade head
curl http://localhost:8000/health
```

5. UI operacional: **http://localhost:3000** (não a 5173, salvo desenvolvimento da interface).

A primeira subida baixa modelos ML (dezenas de GB). Sem GPU os serviços de visão/ASR/face ficam lentos ou inviáveis.

---

## Duas portas: 3000 vs 5173

São a **mesma aplicação**, servidas de formas diferentes.

| | `http://localhost:3000` | `http://localhost:5173` |
|---|---|---|
| Quem serve | Contentor `sokol-web` (nginx + bundle) | Vite (`cd web && npm run dev`) |
| Código | Último `docker compose … --build sokol-web` | Fonte atual em `web/src/` (HMR) |
| Quando usar | Operação / “como em produção” | Desenvolvimento da UI |

Depois de mudar o frontend, reconstrua o container ou o **3000 fica velho**:

```bash
cd deploy && docker compose --env-file ../.env up -d --build sokol-web
```

A API está sempre em **`http://localhost:8000`** (docs: `/docs`). O nginx em `:3000` faz proxy de `/api/` para ela.

---

## Modelos (LLM, embedding e reranker)

Há **três papéis**. Só o **LLM** se troca no dia-a-dia. Embedding e reranker são outra história.

| Papel | Onde corre | Para que serve | Trocar em runtime? |
|-------|------------|----------------|--------------------|
| **LLM** | LM Studio no **host** (`:1234`) | Agent (aba Chat), síntese de playbooks | Sim — Admin `/admin` |
| **Embedding** | `sokol-embed` (`:8001`); fallback se o LM Studio não carregar o GGUF | Busca semântica / vetores (`Indexar vetores`) | **Não** (ADR-0006) |
| **Reranker** | serviço de rerank | Ordenar hits da busca híbrida | Sim, com cuidado |

A fonte de verdade do LLM ativo é `config/models.yaml` (montado no container da API). A UI **Administração → Modelos** mostra *Chat usa \<id\> · n_ctx N* — esse id é o que o Agent envia ao LM Studio. O `.env` (`SOKOL_DEFAULT_LLM_MODEL`) só entra se o registry não tiver um modelo `active`.

### Quando mudar o LLM

Mude quando o modelo atual **falha no trabalho investigativo**, não por hábito:

- Respostas fracas em português, recusa de tools, ou alucinação persistente.
- Precisa de **mais contexto** (casos grandes) e a VRAM aguenta `n_ctx` 16k–32k.
- O modelo carregado **não é o que o Admin mostra** (erro típico: env com `gpt-oss-20b` e UI com Gemma).
- Troca de hardware / VRAM: descer para um modelo mais pequeno em vez de ficar em `n_ctx=8192`.

**Não mude** a meio de um laudo sem anotar no caso: o tom e os erros do Agent mudam. Detecções ML (YOLO, faces, ASR) **não** usam o LLM — trocar o chat não refaz placas nem transcrições.

**Não mude o embedding** pela UI (está bloqueado). Vetores já gravados ficariam incompatíveis; isso exige reindexação offline e edição de `models.yaml` de propósito. Reranker pode-se ativar no Admin se o endpoint responder; o impacto é só a ordem da busca, não os embeddings.

O `.env` pode apontar `SOKOL_EMBED_BASE_URL` para o LM Studio (`:1234`). Na prática o GGUF de embedding **muitas vezes não carrega** enquanto o LLM ocupa a VRAM — o worker tenta o LM Studio e cai em `http://localhost:8001/v1` (`sokol-embed`). Desligue o fallback com `SOKOL_EMBED_FALLBACK_URL=` vazio.

### Como mudar o LLM (checklist)

O Sokol **não baixa** o GGUF por si. Os dois lados precisam coincidir: processo no LM Studio **e** id no registry.

**1. Carregar no LM Studio com contexto alinhado**

Alvo: **32768** tokens. Se a VRAM não chegar, **16384** — não deixar em 8192 (o Agent rebenta em casos reais).

```bash
# Ver o que está em disco / em memória
lms ls
lms ps

# Carregar o id exacto que o Admin vai usar
lms load google/gemma-4-12b-qat -c 32768 -y
```

Na UI do LM Studio: *My Models* → Load → **Context Length 32768**, servidor local ligado na porta **1234**. Confirme:

```bash
curl -s http://localhost:1234/v1/models
curl -s http://localhost:8000/health   # "lmstudio": "ok"
```

**2. O id tem de existir no registry**

`config/models.yaml` lista os LLM permitidos. Para um modelo **novo**:

1. Adicione uma entrada em `llm_models` (`id`, `provider: lmstudio`, `model:` igual ao id do LM Studio, `context_length`, `enabled: true`).
2. Não precisa rebuild se o volume `../config:/app/config` estiver montado (já está no compose).
3. Recarregar a página Admin.

**3. Ativar no Admin**

1. Entre como `is_platform_admin` (`admin` no seed).
2. **Administração → Modelos**. A linha *Chat usa …* é o id efetivo.
3. Clique **Ativar** no LLM desejado. A API valida se o LM Studio **responde com esse id**; senão devolve 502.
4. Faça uma pergunta curta no Agent («quantas mensagens neste caso?»). Se aparecer `tokens > n_ctx 8192`, o modelo carregado está curto — volte ao passo 1.

**4. Variáveis de ambiente (opcional)**

Em `.env` / `deploy/env.example`:

```bash
SOKOL_LMSTUDIO_BASE_URL=http://localhost:1234/v1
SOKOL_LLM_N_CTX=32768
# Só usados se nenhum LLM estiver active no yaml:
SOKOL_DEFAULT_LLM_MODEL=google/gemma-4-12b-qat
SOKOL_ACTIVE_LLM_MODEL=google/gemma-4-12b-qat
```

Depois de mudar `.env` da API: `docker compose --env-file ../.env up -d sokol-api`.

### Contexto (`n_ctx`) vs teto das tools

Mesmo com 32k, o Agent **não** mete 40 mil localizações no prompt. As tools têm teto (`limit`/`k` ≤ 50) e os resultados são compactados. Os dois lados juntos: modelo com contexto alto **e** payload pequeno. Se o prompt ainda passar do `n_ctx`, o Agent recusa com mensagem clara em vez de falhar no LM Studio.

---

## Operação do dia-a-dia

### Ciclo de um caso

1. **Criar caso** em `/cases` (nome, referência legal, fuso `America/Sao_Paulo`).
2. Ser **membro** do caso (senão a API responde *Not a member of this case*).
3. Copiar o UFDR para a pasta do host em `SOKOL_INGEST_DIR` (default `UFDRsTest/`, relativa a `deploy/`). Subpastas ok. **Não precisa parar o Docker** para copiar arquivos para a pasta já montada. Só precisa de `compose up -d` se **mudar** o valor de `SOKOL_INGEST_DIR`.
4. Caso → aba **Operação** → marcar arquivo ou **Ingerir pasta**. Um UFDR ainda sendo copiado (ZIP incompleto) aparece como *Copiando* e a API recusa ingestão até o arquivo fechar. O worker drena o job sozinho (`pending` → `running` → `done`).
5. Investigar: Timeline, Dados, Mídia, Conversas, Busca, Agent.
6. **Enriquecer** (não vem de graça na ingestão — ver [Enriquecimento](#enriquecimento-pipeline-texto-e-vetores)):
   - **Mídia → Amostra** (detecções ML). **Tudo** só quando a amostra bastar e houver tempo/GPU.
   - **Busca → Indexar texto** (índice lexical). **Indexar vetores** (Agent / busca semântica).
7. Pendências (Indicator → Fact), Bookmarks, Relatório.

Pela API:

```bash
TOKEN=$(curl -s http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .token)

curl -X POST http://localhost:8000/ingest/batch \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"case_id":"<uuid>","source_type":"ufdr","inbox_refs":["apple/pa7.ufdr"]}'
```

Progresso: `GET /ingest/jobs?case_id=` e a lista na aba Operação. Mídia grande **não** é toda extraída na ingestão — `GET /media/file/{hash}?case_id=` extrai on-demand para `data/media-cache/`.

A ingestão **tenta** gerar embeddings; se o endpoint falhar, o erro é engolido e o caso fica usável **sem vetores**. Por isso o passo 6 existe.

### Dois tipos de UFDR

| Extract Cellebrite | O que o Sokol faz |
|--------------------|-------------------|
| XML rico (Physical / Advanced Logical, UFED 7.x e 8.x) | Parse de `report.xml`: chats, e-mails, arquivos (`name` ou fallback pelo *Local Path*) |
| **FileSystem / warrant iCloud** | XML costuma ser fino (Note, LogEntry, WebBookmark). O worker **percorre `files/` em stream** (notas, `.eml`, sqlite, XLSX, mídia) **sem** carregar o ZIP inteiro na RAM. A aba Operação mostra tipos XML ignorados **e** o probe FileSystem. |

Se o XML não tiver Chat/Email, 4 bookmarks não são “ingest falhou”: olhe o diagnóstico FileSystem. Domínios ausentes na imagem (sem `.eml`, sem GPS) ficam em 0 hits — o job continua `done`.

### Enriquecimento: pipeline, texto e vetores

Três jobs distintos. Não se substituem.

| O quê | Onde na UI | Endpoint | O que grava | Quem executa |
|-------|------------|----------|-------------|--------------|
| **Pipeline de detecção** | Caso → **Mídia** (não Operação) | `POST /detect/pipeline/{case_id}?mode=sample\|all` | Indicadores: visão, rostos, placas, OCR, ASR | Threads na **API** |
| **Indexar texto** | Caso → **Busca** (canto superior direito) | `POST /detect/chunk/{case_id}` | `chunks` + `tsv` (lexical). `embedding` fica `NULL` | API (síncrono) |
| **Indexar vetores** | Caso → **Busca** (ao lado de Indexar texto); também no **Chat** vazio | `POST /detect/embed/{case_id}` | `chunks.embedding` e `events.embedding` (1024-d) | **Worker** (`kind=embed`) |

Rostos, Placas, Voz e OCR vazios depois da ingestão é o esperado até rodar o pipeline em **Mídia**.

#### Pipeline de detecção (Mídia)

- **Amostra** (padrão): 80 imagens e 40 áudios — triagem.
- **Tudo**: percorre a mídia extraível do caso; lento e pesado de GPU.
- Resultado = **Indicator** (ADR-0004), não Fact. O Agent não afirma isso como fato e não entra no laudo como asserção. Vira Fact só via **Pendência** humana.
- Jobs listados na própria aba Mídia são **deste caso**; ignore “Done” de outro UFDR.

```bash
curl -X POST "http://localhost:8000/detect/pipeline/{case_id}?mode=sample" \
  -H "Authorization: Bearer $TOKEN"
# Caso inteiro:
curl -X POST "http://localhost:8000/detect/pipeline/{case_id}?mode=all" \
  -H "Authorization: Bearer $TOKEN"
```

#### Indexar texto (Busca)

Gera/atualiza o índice **lexical** (`chunks.tsv`). Necessário para a busca por palavra na aba Busca. **Não** preenche vetores — o Agent ainda não faz busca semântica só com isto.

#### Indexar vetores (Busca / Chat)

Habilita `semantic_search` / `semantic_search_events` no Agent. O botão:

- Na **Busca**: sempre visível no cabeçalho, ao lado de Indexar texto.
- No **Chat**: só **antes da primeira pergunta** (some quando já há histórico).
- Enquanto o job corre, o rótulo vira `Indexando chunks N/M` (depois `events`).
- Quando chunks e events estão cobertos: **Vetores prontos** (desativado).

O worker preenche só linhas com `embedding IS NULL`. Se o LM Studio não carregar o GGUF de embedding (VRAM ocupada pelo LLM), cai automaticamente no `sokol-embed` (`:8001`, mesmo modelo 1024-d, ADR-0006). No CPU isso é lento — deixe o job no worker; não relance a cada minuto.

```bash
curl -X POST "http://localhost:8000/detect/embed/{case_id}" \
  -H "Authorization: Bearer $TOKEN"
curl "http://localhost:8000/detect/embed/{case_id}" \
  -H "Authorization: Bearer $TOKEN"
```

`GET` devolve `chunks_embedded` / `chunks_total` e `events_embedded` / `events_total`.

### Agent (aba Chat)

`POST /chat/agent` (sem histórico na UI). Contagens e fatos vêm de **tools SQL**, nunca da busca semântica (ADR-0005). Teto das tools: 50 linhas, sem `COUNT(*)`. Cada afirmação deve ter Source (Message, Media SHA-256, ou Document+página).

Sem vetores, o Agent só vê o que o SQL devolver. Com vetores, usa busca semântica em **events** e **chunks**. Perguntas largas demais (“mostra toda a timeline”) devem ser recortadas por data, app ou contato.

### Backup

Só admin de plataforma. Staging entra no tar em modo `auto` se ≤ `SOKOL_BACKUP_STAGING_MAX_MB` (default 2048); force com `SOKOL_BACKUP_INCLUDE_STAGING=1`.

---

## Arquitetura

```
Navegador
  :5173  Vite (dev)  ──proxy /api──┐
  :3000  nginx (prod) ─proxy /api──┤
                                   ▼
                         sokol-api :8000  (FastAPI, host network)
                                   │
          ┌──────────────┬─────────┼──────────┬──────────────┐
          ▼              ▼         ▼          ▼              ▼
   Postgres :5433     Redis     Worker    ML services    LM Studio
   pgvector+postgis   :6379     (fila)    :8001–8011     :1234 (host)
```

| Serviço | Porta | Função |
|---------|-------|--------|
| `sokol-web` | **3000** | SPA React (nginx) |
| Vite (fora do Compose) | **5173** | SPA React (dev) |
| `sokol-api` | **8000** | API gateway |
| `sokol-postgres` | **5433** | Postgres 16 + pgvector + PostGIS |
| `sokol-redis` | **6379** | Fila de jobs |
| `sokol-worker` | — | Ingestão **e** job `embed` (Indexar vetores) |
| `sokol-embed` | **8001** | Embeddings (Qwen3-Embedding-0.6B) |
| `sokol-vision` | **8007** | YOLO |
| `sokol-ocr` | **8008** | PaddleOCR |
| `sokol-asr` | **8009** | faster-whisper |
| `sokol-plate` | **8010** | Placas |
| `sokol-face` | **8011** | InsightFace |
| LM Studio | **1234** | LLM do Agent — **no host**, fora do Docker |

`sokol-api`, `sokol-worker` e `sokol-web` usam `network_mode: host`.

---

## Instalação (detalhe)

Pré-requisitos: Linux, Docker Compose v2+, NVIDIA Container Toolkit se GPU, LM Studio, Git, disco para os modelos ML, ~32 GB RAM confortável.

```bash
git clone https://github.com/geni-uff/sokol.git
cd sokol
cp deploy/env.example .env    # ou: python ops/setup
# editar POSTGRES_PASSWORD; alinhar DATABASE_URL se mudar a senha
mkdir -p data/media-cache data/staging data/backups
```

Não commite `.env` nem evidências reais (`UFDRsTest/`, `ingest/`, `data/`).

```bash
cd deploy
docker compose --env-file ../.env up --build -d
docker exec sokol-api alembic upgrade head
curl http://localhost:8000/health
curl http://localhost:3000/api/health
```

Papéis: **por caso** Admin / Analista / Leitor; **plataforma** `users.is_platform_admin` para `/admin` e `/backup/*`.

---

## Frontend e API

Rotas: `/login`, `/cases`, `/cases/:caseId` (abas em estado local, sem deep-link), `/admin`.

Abas do caso: Timeline, Busca (Indexar texto / Indexar vetores), Chat, Conversas, Dados, Bookmarks, Watchlists, Pendências, Mídia (pipeline de detecção), Rostos, Placas, Voz, OCR, Analytics, Grafo, Playbooks, Relatórios, Análise Cruzada, Identidades, **Operação** (inbox, jobs, cobertura XML/FS).

Dev UI: `cd web && npm run dev` (5173). Lint: `npm run lint`. E2E: `npm run test:e2e` (stack no ar).

Módulos FastAPI em `api/src/sokol/` (um por domínio, routers em `main.py`). Worker: `worker/ingest_worker.py`, `ufdr_parser.py`, `fs_walk.py`, `parsers/` (incluindo `email.py`). Serviços ML em `services/`. Schema Alembic em `db/migrations/versions/`.

---

## Variáveis de ambiente (resumo)

Copie `deploy/env.example` → `.env`.

```bash
POSTGRES_DB=sokol
POSTGRES_USER=sokol
POSTGRES_PASSWORD=change_me

SOKOL_API_PORT=8000
SOKOL_WEB_PORT=3000
SOKOL_LMSTUDIO_PORT=1234

SOKOL_LMSTUDIO_BASE_URL=http://localhost:1234/v1
SOKOL_LLM_N_CTX=32768
SOKOL_DEFAULT_LLM_MODEL=google/gemma-4-12b-qat

SOKOL_DEFAULT_EMBED_MODEL=Qwen/Qwen3-Embedding-0.6B
SOKOL_EMBED_DIM=1024

SOKOL_GPU_MODE=auto
SOKOL_MEDIA_CACHE_DIR=/data/media-cache
SOKOL_STAGING_DIR=/data/staging
SOKOL_BACKUP_DIR=/data/backups
# Pasta no host (relativa a deploy/ ou absoluta). Mudar o valor = recreate.
SOKOL_INGEST_DIR=../UFDRsTest
SOKOL_CONTAINER_INGEST_DIR=/ingest/inbox
```

A API em host network liga ao Postgres em `localhost:5433`.

---

## Comandos úteis

```bash
cd deploy && docker compose --env-file ../.env up --build -d
docker compose --env-file ../.env ps
docker logs -f sokol-api
docker logs -f sokol-worker

# Rebuild só a UI
docker compose --env-file ../.env up -d --build sokol-web

docker exec sokol-api alembic upgrade head
docker exec -it sokol-postgres psql -U sokol -d sokol

curl http://localhost:8000/health
cd web && npm run dev      # :5173
cd synth && python -m synth --seed 42 --output ./output
```

Parar: `docker compose --env-file ../.env down` (mantém volumes). Não apague `sokol-pgdata` a menos que queira zerar o banco.

---

## Invariantes (não violar)

1. **Todo dado é escopado por `case_id`.** Mídia exige `?case_id=` e membership.
2. **Cross-case é exceção auditada** (Admin + justificativa + `audit_log`).
3. **Indicator ≠ Fact.** Detecção automática nunca é afirmada pelo Agent nem entra no laudo como fato.
4. **Resolução de identidade é não-destrutiva** — arestas `resolves_to`.
5. **Source** aponta para Message, Media (SHA-256) ou Document+página — não para Event como canônico.
6. **Tempo:** preservar `tz_original`; consultas no fuso do caso.
7. Contagens e fatos vêm de **structured tools (SQL)**, não de busca semântica.

---

## Status

Versão operacional: **0.8.2** (arquivo `VERSION`). SemVer: [`docs/VERSIONING.md`](docs/VERSIONING.md).

O SOKOL está em **0.x**. **1.0.0** só quando tudo funcionar de ponta a ponta. A versão **não sobe sozinha** — só com pedido explícito. PATCH = correção; MINOR = capacidade nova; 1.0.0 = produto completo.

Backlog **sokol-v2** (`.scratch/sokol-v2/`) está concluído. Fora de escopo até decisão jurídica: assinatura digital RSA de laudos.

---

## Licença

Privado — uso interno da GENI/UFF. Não distribuir.
