# INSTRUCOES — SOKOL

Manual do operador. Versão do produto: **0.8.2**.

Autor: **Matheus C. Pestana** (GENI/UFF), em parceria com a **Polícia Federal**.

---

## 0. Como este texto está escrito

Este manual aplica as **regras de redação ASD-STE100** (Issue 9) em português.

- Uma frase, uma ideia.
- Procedimento: voz de comando. Uma ação por passo. Frase curta (cerca de 20 palavras).
- Descrição: voz ativa. Frase curta (cerca de 25 palavras).
- Um termo para cada conceito. Sem sinônimo.
- Presente simples. Sem metáfora.

Termos técnicos do SOKOL estão na seção 1. Use só esses termos.

**AVISO:** Dados de Caso não saem da máquina. Não envie UFDR, mídia ou texto de Caso para serviço externo.

---

## 1. Termos

Use a palavra da coluna **Termo**. Não use a coluna **Não use**.

| Termo | Significado | Não use |
|---|---|---|
| **Caso** | Recipiente da investigação. Todo dado tem `case_id`. | projeto, operação |
| **Document** | Unidade importada (um arquivo `.ufdr`, um PDF). | evidência (como tabela) |
| **Artifact** | Unidade extraída de um Document (conversa, foto, sqlite). | item, anexo |
| **Media** | Binário com SHA-256. Vários Artifacts podem apontar para a mesma Media. | blob |
| **Event** | Linha da Timeline com data e hora. | ocorrência |
| **Message** | Linha de comunicação (WhatsApp, SMS, …). | chat (como linha) |
| **Conversation** | Thread de Messages com o mesmo `chat_id`. | chat (como thread) |
| **Agent** | Pergunta e resposta com IA. Aba da UI: **Chat**. | chat, bot, assistente |
| **Source** | Citação a Message, Media (SHA-256) ou Document+página. | fonte genérica |
| **Chunk** | Janela de texto para busca. | trecho |
| **Ingestion** | Parse do Document. Depois disto o Caso é consultável. | upload |
| **Enrichment** | Jobs após a Ingestion: detecção ML e vetores. | ingestão |
| **Job** | Unidade na fila (`pending` → `running` → `done` ou `failed`). | tarefa |
| **Indicator** | Detecção automática. Não é fato. | fato |
| **Fact** | Afirmação confirmada (Pendência humana ou dado determinístico). | indício |
| **Pendência** | Fila humana. Passo Indicator → Fact. | alerta |
| **Watchlist** | Seletores (telefone, placa, …) sobre o Caso. | lista |
| **Bookmark** | Item marcado para o relatório. | favorito |
| **Identity** | Pessoa real resolvida. | contact (confusão) |
| **Contact** | Entrada de agenda observada no aparelho. | pessoa |
| **resolves_to** | Aresta que liga observação a Identity. Não apaga nós. | merge |
| **Inbox** | Pasta no host com arquivos a ingerir (`SOKOL_INGEST_DIR`). | upload do browser |

Vocabulário completo: [`CONTEXT.md`](CONTEXT.md).

---

## 2. O que o SOKOL faz

O SOKOL corre na máquina local com Docker Compose.

O operador:

1. Cria um Caso.
2. Copia um ou mais UFDRs para o Inbox.
3. Enfileira a Ingestion na aba **Operação**.
4. Consulta Timeline, Conversas, Dados e Mídia.
5. Corre o Enrichment (pipeline, texto, vetores).
6. Pergunta ao Agent.
7. Resolve Pendências.
8. Gera relatório.

O LLM do Agent corre no **LM Studio** no host. Os outros serviços correm em containers.

---

## 3. Peças da plataforma

| Nome | Porta no host | Função |
|---|---|---|
| UI operacional | 3000 | Interface. Use esta porta no dia a dia. |
| UI de desenvolvimento | 5173 | Código vivo (`npm run dev`). Não é produção. |
| API | 8000 | Gateway FastAPI. Documentação: `/docs`. |
| Postgres | 5433 | Banco com pgvector e PostGIS. |
| Redis | 6379 | Fila. |
| Worker | — | Ingestion e Indexar vetores. Um Job de cada vez. |
| sokol-embed | 8001 | Vetores de texto (1024 dimensões). |
| sokol-vision | 8007 | Objectos em imagem (YOLO). |
| sokol-ocr | 8008 | Texto em imagem. |
| sokol-asr | 8009 | Transcrição de áudio. |
| sokol-plate | 8010 | Placas. |
| sokol-face | 8011 | Rostos. |
| LM Studio | 1234 | LLM. Fora do Docker. |

`sokol-api`, `sokol-worker` e `sokol-web` usam a rede do host.

---

## 4. Papéis

Há dois eixos.

**No Caso**

| Papel | O operador faz |
|---|---|
| Admin do Caso | Membros, Ingestion, Agent, Pendência, relatório, cross-case |
| Analista | Ingestion, Agent, Bookmark, Pendência, relatório |
| Leitor | Lê. Não ingere. Não resolve Pendência. Não gera laudo |

**Na plataforma**

O usuário com `is_platform_admin` abre `/admin`. Aí faz backup, troca de LLM e verificação de auditoria. O seed de desenvolvimento é o usuário `admin`.

Para ingerir, o operador deve ser **membro** do Caso (Admin ou Analista). Senão a API responde: `Not a member of this case`.

---

## 5. Requisitos

Antes do deploy, confirme:

1. Linux com Docker Compose v2.
2. Git.
3. LM Studio instalado no host.
4. Espaço em disco para modelos ML (dezenas de GB).
5. Cerca de 32 GB de RAM.
6. GPU NVIDIA com Container Toolkit, se for usar visão, ASR ou faces.

Sem GPU, visão, ASR e faces ficam lentos ou inviáveis. A Ingestion de texto continua.

---

## 6. Deploy

Faça os passos na ordem. Um passo, uma ação.

### 6.1 Código e ambiente

1. Abra um terminal.
2. Clone o repositório.

```bash
git clone https://github.com/geni-uff/sokol.git
```

3. Entre na pasta do repositório.

```bash
cd sokol
```

4. Copie o exemplo de ambiente.

```bash
cp deploy/env.example .env
```

5. Edite `.env`.
6. Defina `POSTGRES_PASSWORD`.
7. Se mudar a senha, alinhe `DATABASE_URL` com a mesma senha.

**AVISO:** Não grave `.env` no Git. Não grave UFDR real no Git.

### 6.2 Pastas de dados

1. Crie as pastas.

```bash
mkdir -p data/media-cache data/staging data/backups
```

### 6.3 LM Studio

O SOKOL não baixa o GGUF do LLM.

1. Abra o LM Studio.
2. Carregue o modelo com **Context Length 32768**.
3. Se a VRAM não chegar, use 16384. Não use 8192 em Caso real.
4. Ligue o servidor local na porta **1234**.
5. Confirme a lista de modelos.

```bash
curl -s http://localhost:1234/v1/models
```

O id do modelo no LM Studio deve coincidir com `config/models.yaml` e com a linha ativa em **Administração → Modelos**.

### 6.4 Subida da stack

**Windows:** dê dois cliques em `SOKOL.bat` na raiz do repositório. O script sobe os containers, aplica as migrações e abre o navegador.

**Linux / terminal:**

1. Entre na pasta `deploy`.

```bash
cd deploy
```

2. Suba os containers.

```bash
docker compose --env-file ../.env up --build -d
```

3. Aplique as migrações.

```bash
docker exec sokol-api alembic upgrade head
```

4. Verifique a API.

```bash
curl http://localhost:8000/health
```

A resposta deve mostrar a API saudável. O campo `lmstudio` deve ser `ok` se o LM Studio responde.

5. Abra o browser em `http://localhost:3000`.

A primeira subida baixa modelos ML. Espere.

### 6.5 Parar e voltar a subir

Para parar e **manter** o banco:

```bash
cd deploy
docker compose --env-file ../.env down
```

Para subir de novo:

```bash
cd deploy
docker compose --env-file ../.env up -d
```

**AVISO:** Não apague o volume `sokol-pgdata` salvo se quiser apagar o banco.

### 6.6 UI na porta 3000

A porta **3000** serve o bundle do container `sokol-web`.

Depois de mudar código em `web/src/`:

1. Reconstrua o container.

```bash
cd deploy
docker compose --env-file ../.env up -d --build sokol-web
```

A porta **5173** é só para desenvolvimento (`cd web && npm run dev`).

---

## 7. Primeiro acesso

1. Abra `http://localhost:3000`.
2. Digite o usuário `admin`.
3. Digite a senha `admin123`.
4. Clique para entrar.

Isto é o login de desenvolvimento. Troque a senha em ambiente real.

O admin de plataforma abre `/admin`.

---

## 8. Ciclo de um Caso

Faça os passos na ordem.

### 8.1 Criar o Caso

1. Abra `/cases`.
2. Crie um Caso.
3. Preencha o nome.
4. Preencha a referência legal, se existir.
5. Use o fuso `America/Sao_Paulo`, salvo outra ordem.

O operador que cria o Caso entra como Admin desse Caso.

### 8.2 Copiar o UFDR para o Inbox

O Inbox é a pasta do host em `SOKOL_INGEST_DIR`. O valor padrão é `UFDRsTest/` (relativo a `deploy/`).

1. Copie o arquivo `.ufdr` para essa pasta.
2. Pode usar subpasta (exemplo: `apple/pa7.ufdr`).
3. Não pare o Docker para copiar.
4. Só recrie o Compose se **mudar** o valor de `SOKOL_INGEST_DIR`.

O browser **não** envia o arquivo. A Ingestion lê o Inbox.

**NOTA:** Um UFDR ainda em cópia é um ZIP incompleto. A UI mostra *Copiando*. A API recusa até o arquivo fechar.

### 8.3 Enfileirar a Ingestion

1. Abra o Caso.
2. Abra a aba **Operação**.
3. Marque um ou mais arquivos.
4. Clique em **Ingerir**.
5. Para uma pasta inteira, marque o cabeçalho da pasta. Clique em **Ingerir pasta**.

O worker processa **um** Job de cada vez. O estado vai de `pending` para `running` e depois `done` ou `failed`.

Vários UFDRs no mesmo Caso são válidos. Cada arquivo vira um Document. O teto do lote é 200 arquivos.

**CUIDADO:** Dois extracts do **mesmo** aparelho tendem a duplicar Messages e Events. Extracts de aparelhos **diferentes** é o uso correto.

Pode somar um UFDR a um Caso que já tem dados. Use de novo a aba **Operação**. Não crie um segundo Caso para “anexar”.

### 8.4 Consultar

Depois de `done`, o Caso já é consultável.

Abra Timeline, Conversas, Dados e Mídia.

A Ingestion tenta gerar vetores. Se o endpoint de embedding falhar, o Caso continua sem vetores. Por isso existe o passo 8.5.

### 8.5 Enrichment

Três Jobs distintos. Um não substitui o outro.

| Job | Onde | O que grava |
|---|---|---|
| Pipeline de detecção | Aba **Mídia** | Indicators: visão, rostos, placas, OCR, ASR |
| Indexar texto | Aba **Busca** | Chunks e índice lexical (`tsv`). Vetor fica vazio |
| Indexar vetores | Aba **Busca** (e Chat vazio) | Vetores em Chunks e Events |

**Pipeline**

1. Abra a aba **Mídia**.
2. Clique em **Amostra** para triagem (80 imagens e 40 áudios).
3. Clique em **Tudo** só se a amostra chegar e houver tempo e GPU.

Rostos, Placas, Voz e OCR vazios após a Ingestion são o estado esperado. Corra o pipeline.

O resultado é **Indicator**. O Agent não afirma Indicator como Fact. O laudo não usa Indicator como asserção. Para Fact, resolva a **Pendência**.

**Indexar texto**

1. Abra a aba **Busca**.
2. Clique em **Indexar texto** (canto superior direito).

Isto serve a busca por palavra. Isto **não** serve a busca semântica do Agent.

**Indexar vetores**

1. Abra a aba **Busca**.
2. Clique em **Indexar vetores** (ao lado de Indexar texto).

Na aba **Chat**, o mesmo botão aparece só **antes** da primeira pergunta. Depois some.

Enquanto o Job corre, o rótulo mostra o progresso (`Indexando chunks N/M`). Quando Chunks e Events estão cobertos, o rótulo é **Vetores prontos**.

O worker preenche só linhas com vetor vazio. Se o LM Studio não carregar o modelo de embedding, o worker usa `sokol-embed` na porta 8001. No CPU o Job é lento. Não relance o Job a cada minuto.

Depois de um UFDR novo no mesmo Caso, corra de novo Indexar texto, Indexar vetores e o pipeline.

### 8.6 Fechar o ciclo humano

1. Resolva Pendências (Indicator → Fact).
2. Marque Bookmarks.
3. Gere o relatório na aba **Relatórios**.

---

## 9. Abas do Caso

As abas não têm endereço próprio. A troca é estado local.

| Aba na UI | Significado |
|---|---|
| **Timeline** | Events no fuso do Caso. Mapa de localizações. |
| **Busca** | Busca no Caso. Botões Indexar texto e Indexar vetores. |
| **Chat** | Interface do **Agent**. |
| **Conversas** | Messages agrupadas em Conversation. |
| **Dados** | Tabelas estruturadas (contatos, chamadas, …). |
| **Bookmarks** | Itens marcados para o relatório. |
| **Watchlists** | Seletores e Hits. |
| **Pendências** | Fila Indicator → Fact. |
| **Mídia** | Galeria. Pipeline de detecção. |
| **Rostos** | Faces (Indicators até Pendência). |
| **Placas** | Placas detectadas. |
| **Voz** | Transcrições ASR. |
| **OCR** | Texto extraído de imagem. |
| **Analytics** | Agregados. |
| **Grafo** | Entidades e arestas. |
| **Playbooks** | Fluxos determinísticos com síntese no fim. |
| **Relatórios** | HTML com cadeia de custódia. |
| **Análise Cruzada** | Vários Casos. Só Admin. Auditoria obrigatória. |
| **Identidades** | Resolução com `resolves_to`. Não apaga nós. |
| **Operação** | Inbox, Ingestion, Jobs, diagnóstico XML/FileSystem. |

---

## 10. Agent (aba Chat)

O Agent chama tools SQL. Contagem e fato vêm dessas tools. A busca semântica **não** conta (ADR-0005).

Cada afirmação deve ter **Source**: Message, Media (SHA-256) ou Document+página.

O teto de cada tool é **50 linhas**. Este teto está no código. Não há botão para mudar. O LLM pode pedir 500. A API devolve 50.

Sem vetores, o Agent só vê o retorno SQL. Com vetores, o Agent também busca em Events e Chunks.

1. Abra a aba **Chat**.
2. Se os vetores ainda não existem, clique em **Indexar vetores** (tela vazia).
3. Faça uma pergunta recortada (data, app ou contato).
4. Não peça “mostra toda a Timeline”.

A UI não envia o histórico da conversa no pedido. Cada pergunta é um ciclo novo.

Para mudar o LLM:

1. Carregue o modelo no LM Studio com contexto 32768.
2. Confirme o id em `GET http://localhost:1234/v1/models`.
3. Entre em `/admin` como admin de plataforma.
4. Abra **Modelos**.
5. Clique em **Ativar** no LLM desejado.

**NOTA:** Trocar o LLM não refaz placas, rostos nem transcrições. Não troque o modelo de embedding pela UI (ADR-0006).

---

## 11. Tipos de UFDR

| Extract Cellebrite | O que o worker faz |
|---|---|
| XML rico (Physical / Advanced Logical) | Lê `report.xml`: chats, e-mails, arquivos |
| FileSystem / warrant iCloud | XML fino. Percorre `files/` em fluxo. Não carrega o ZIP inteiro na RAM |

Se o XML não tem Chat ou Email, poucos bookmarks **não** significam falha. Veja o diagnóstico FileSystem na aba **Operação**.

Domínio ausente na imagem (sem `.eml`, sem GPS) fica em zero. O Job continua `done`.

---

## 12. Administração e backup

1. Entre como `is_platform_admin`.
2. Abra `/admin`.

Nesta página o operador:

- ativa o LLM
- cria backup
- define agendamento
- restaura backup
- verifica a cadeia de `audit_log`

O staging entra no tar em modo `auto` se o tamanho for ≤ `SOKOL_BACKUP_STAGING_MAX_MB` (padrão: 2048). Force com `SOKOL_BACKUP_INCLUDE_STAGING=1`.

**AVISO:** Restore apaga e recria dados. Confirme o arquivo. A API registra a ação no `audit_log` antes do DROP.

---

## 13. Variáveis de ambiente (mínimo)

Arquivo: `.env` na raiz. Modelo: `deploy/env.example`.

| Variável | Função |
|---|---|
| `POSTGRES_PASSWORD` | Senha do banco |
| `DATABASE_URL` | Ligação da API e do worker (`localhost:5433`) |
| `SOKOL_INGEST_DIR` | Inbox no host |
| `SOKOL_LMSTUDIO_BASE_URL` | `http://localhost:1234/v1` |
| `SOKOL_LLM_N_CTX` | 32768 |
| `SOKOL_EMBED_DIM` | 1024 |
| `SOKOL_BACKUP_DIR` | Pasta de backups no container |

Inbox: copiar arquivos não exige recreate. Mudar `SOKOL_INGEST_DIR` exige recreate.

---

## 14. Comandos de operação

Na pasta `deploy`:

```bash
docker compose --env-file ../.env up --build -d
docker compose --env-file ../.env ps
docker logs -f sokol-api
docker logs -f sokol-worker
docker exec sokol-api alembic upgrade head
curl http://localhost:8000/health
```

Ingestion pela API (exemplo):

```bash
TOKEN=$(curl -s http://localhost:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | jq -r .token)

curl -X POST http://localhost:8000/ingest/batch \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"case_id":"<uuid>","source_type":"ufdr","inbox_refs":["apple/pa7.ufdr"]}'
```

---

## 15. Falhas frequentes

| Sintoma | Causa provável | Acção |
|---|---|---|
| `Not a member of this case` | Operador não é membro | Adicione o usuário ao Caso |
| Inbox vazio na UI | Arquivo fora de `SOKOL_INGEST_DIR` | Copie para a pasta montada. Clique em actualizar |
| Arquivo *Copiando* | ZIP incompleto | Espere o fim da cópia |
| Porta 3000 sem a mudança de UI | Bundle velho | Rebuild de `sokol-web` |
| Agent sem busca semântica | Vetores vazios | Clique em **Indexar vetores** |
| Rostos/placas/OCR vazios | Pipeline não correu | Aba **Mídia** → **Amostra** |
| `lmstudio` não ok no `/health` | Servidor 1234 parado | Ligue o LM Studio. Carregue o LLM |
| Indexar vetores lento | CPU no `sokol-embed` | Deixe o Job no worker |
| Health da API a falhar durante Mídia | Pipeline na API (threads) | Espere o Job. Não lance Tudo em paralelo com uso pesado |
| Timeline vazia e Conversas cheias | Filtro ou mapeamento de Event | Tire o filtro de app. WhatsApp na Timeline lê Events |

---

## 16. Regras que o operador não quebra

1. Todo dado tem `case_id`.
2. Cross-case só com Admin, justificativa e `audit_log`.
3. Indicator não é Fact.
4. Não apague Identity. Use `resolves_to`.
5. Source aponta para Message, Media ou Document+página.
6. Preserve `tz_original`. Consulte no fuso do Caso.
7. Contagem vem de SQL, não de busca semântica.
8. Teste com UFDR sintético (`synth/`). Não commite Caso real.

---

## 17. Documentos vizinhos

| Arquivo | Conteúdo |
|---|---|
| [`README.md`](README.md) | Visão geral, créditos, início rápido |
| [`CONTEXT.md`](CONTEXT.md) | Vocabulário canónico |
| [`docs/adr/`](docs/adr/) | Decisões de arquitectura |
| [`docs/VERSIONING.md`](docs/VERSIONING.md) | Regras de número de versão |
| `deploy/env.example` | Lista de variáveis |

---

## 18. Contacto de autoria

Matheus C. Pestana — GENI/UFF. Parceria: Polícia Federal.

Repositório: https://github.com/geni-uff/sokol
