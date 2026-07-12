# Relatório de Teste End-to-End — SOKOL M4+M5

**Data:** 2026-07-08  
**Autor:** Agente SOKOL  
**Versão:** 0.1.0  

---

## 1. Resumo Executivo

Teste end-to-end dos milestone M4 (Busca v1) e M5 (Chat v1) do SOKOL, incluindo:
- Sintético (seed=42): **SUCESSO** — pipeline completo funcionando
- Real (Google Warrant Return 3.1GB): **PARCIAL** — parser precisa de ajustes para formato Google

---

## 2. Dados Utilizados

### 2.1 UFDR Sintético
| Campo | Valor |
|-------|-------|
| Arquivo | `synthetic_42.ufdr` (21KB) |
| Seed | 42 |
| Modelos | 113 |
| Mensagens | 53 |
| Eventos | 103 |
| Artefatos | 17 |

### 2.2 UFDR Real (Google Warrant Return)
| Campo | Valor |
|-------|-------|
| Arquivo | `google_2025-11-03_Relatório.ufdr` (3.1GB) |
| Dispositivo | Google Warrant Return |
| Usuário | julianamarinho586@gmail.com |
| Modelos XML | 40.199 |
| Artefatos ZIP | 438 |
| Fotos Google | ~350+ |
| Location History | JSON (6MB) + CSV (3MB) |

---

## 3. Bugs Corrigidos

### 3.1 Bugs de SQL
| Arquivo | Bug | Correção |
|---------|-----|----------|
| `api/src/sokol/tools.py:360` | `text()` não definido em `query_geo` | `sql_text()` (lazy import) |
| `api/src/sokol/tools.py:400,498` | `db: Session` sem import | `db` sem type hint |
| `worker/search.py:117,151` | `to_tsportuguese()` não existe | `plainto_tsquery('portuguese', :query)` |
| `worker/chunker.py:153` | `to_tsportuguese()` não existe | `to_tsvector('portuguese', :text)` |
| `worker/chunker.py:153` | `message_ids` UUID[] vs text[] | `[UUID(mid) for mid in msg_ids]` |

### 3.2 Bugs de Tipagem
| Arquivo | Bug | Correção |
|---------|-----|----------|
| `api/src/sokol/search_core.py` | `json.loads(r[2])` em JSONB já parseado | `r[2] if isinstance(r[2], dict) else json.loads(r[2])` |
| `api/src/sokol/search_core.py` | `message_ids` UUID objects | `[str(mid) for mid in (r[3] or [])]` |

### 3.3 Bugs de Sintaxe
| Arquivo | Bug | Correção |
|---------|-----|----------|
| `api/src/sokol/chat.py:34` | `""".` (ponto extra) | `"""` |

### 3.4 Bugs de Infraestrutura
| Arquivo | Bug | Correção |
|---------|-----|----------|
| `api/src/sokol/search.py:50` | `from ..worker.search` (wrong path) | Copiado para `search_core.py` |
| `.env` | `host.docker.internal` (não funciona Linux) | `localhost` |
| `.env` | `change_me` como modelo LLM | `qwen/qwen3.5-9b` |
| `deploy/docker-compose.yml` | API não alcança LM Studio | `network_mode: host` |

---

## 4. Testes Realizados

### 4.1 UFDR Sintético — Pipeline Completo

```
┌─────────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│  Sintético   │───▶│ Ingest   │───▶│ Chunker  │───▶│ Search   │
│   21KB       │    │  1s      │    │  19 chks │    │  ✓       │
└─────────────┘    └──────────┘    └──────────┘    └──────────┘
                                              │
                                              ▼
                                        ┌──────────┐
                                        │   Chat   │
                                        │  ✓       │
                                        └──────────┘
```

#### Ingestão
- **Status:** ✓ SUCESSO
- **Tempo:** ~1s
- **Resultado:** 53 mensagens, 103 eventos, 17 artefatos

#### Chunking
- **Status:** ✓ SUCESSO
- **Chunks criados:** 19
- **Dimensão embedding:** 1024 (Qwen3-Embedding-0.6B)
- **Tsvector:** `to_tsvector('portuguese', ...)`

#### Busca Lexical (`/search/scan`)
- **Status:** ✓ SUCESSO
- **Query:** "WhatsApp"
- **Resultados:** 3 chunks com score 0.061
- **Fontes citadas:** ✓

#### Busca Exata (`/search/exact`)
- **Status:** ✓ SUCESSO
- **Query:** "pix"
- **Resultados:** 1 chunk com menção a "pix"

#### Chat Agent (`/chat/agent`)
- **Status:** ✓ SUCESSO
- **Modelo:** qwen/qwen3.5-9b
- **Tool calls:** 1 (`query_messages`)
- **Resposta:** Tabelas formatadas com 20 fontes citadas
- **Warnings de validação:** 0

---

### 4.2 UFDR Real (Google 3.1GB) — Teste Parcial

```
┌─────────────┐    ┌──────────┐    ┌──────────┐
│  Google 3GB │───▶│ Ingest   │───▶│ Parser   │
│             │    │  10s     │    │  ⚠️      │
└─────────────┘    └──────────┘    └──────────┘
                                         │
                                         ▼
                                   ┌──────────┐
                                   │ Erros:   │
                                   │ 40.199   │
                                   └──────────┘
```

#### Ingestão
- **Status:** ⚠️ PARCIAL
- **Tempo:** ~10s (ZIP + XML parsing)
- **Modelos XML:** 40.199 (100% Location)
- **Mensagens:** 0
- **Eventos:** 0
- **Artefatos:** 438 (ZIPs do Google)
- **Erros:** 40.199 (todos Location)

#### Análise dos Erros

**Causa raiz:** O Google Warrant Return usa formato diferente do Cellebrite UFED:

1. **Estrutura XML diferente:**
   - Namespace: `http://pa.cellebrite.com/report/2.0`
   - Models são todos do tipo `Location`
   - Campos `Latitude`/`Longitude` não existem no formato esperado

2. **Dados reais estão em outros formatos:**
   - `LocationHistory.json` (6MB) — coordenadas GPS
   - `LocationHistory.csv` (3MB) — formato tabular
   - `SemanticLocationHistory.json` (557KB) — locais semânticos
   - `database.db` (84MB) — SQLite do Google

3. **Artefatos ZIP:**
   - Google Photos (~350 fotos, 1.7GB)
   - Drive Mobile Backups (598MB)
   - Calendar, Subscriber Info, etc.

#### O que Precisa ser Feito

| Prioridade | Tarefa | Descrição |
|------------|--------|-----------|
| P0 | Parser Google Location | Extrair lat/lon de `LocationHistory.json` |
| P0 | Parser Google MyActivity | Parse de `MyActivity_*.html` |
| P1 | Parser Google Photos | Indexar metadados de fotos |
| P1 | Parser Google Drive | Listar arquivos do backup |
| P2 | Parser Calendar | Eventos do calendário |
| P2 | Parser Subscriber Info | Dados da conta Google |

---

## 5. Configuração Utilizada

### 5.1 Docker Stack
```yaml
sokol-postgres: pgvector:pg16 + PostGIS
sokol-api: FastAPI + uvicorn (network_mode: host)
sokol-embed: PyTorch (não iniciado neste teste)
```

### 5.2 LLM
- **Modelo:** qwen/qwen3.5-9b
- **Provider:** LM Studio (localhost:1234)
- **Contexto:** 32768 tokens
- **Temperatura:** 0.3

### 5.3 Database
- **PostgreSQL:** 16 + pgvector + PostGIS
- **Porta:** 5433
- **Senhas:** change_me (dev)

---

## 6. Resultados Quantitativos

### 6.1 Sintético
| Métrica | Valor |
|---------|-------|
| Tempo total (ingest+chunk) | ~2s |
| Chunks criados | 19 |
| Buscas testadas | 2 (lexical, exact) |
| Tool calls no chat | 1 |
| Warnings de validação | 0 |
| Fontes citadas | 20 |

### 6.2 Real (Google)
| Métrica | Valor |
|---------|-------|
| Tamanho arquivo | 3.1GB |
| Tempo de cópia | 7.5s |
| Tempo de parsing | ~10s |
| Modelos XML parseados | 40.199 |
| Artefatos criados | 438 |
| Erros de parsing | 40.199 (100%) |
| Mensagens extraídas | 0 |
| Eventos extraídos | 0 |

---

## 7. Conclusões

### 7.1 O que Funcionou
1. ✅ Pipeline de ingestão para UFDRs Cellebrite padrão
2. ✅ Chunking com tsvector em português
3. ✅ Busca lexical e exata
4. ✅ Chat agent com tool calling
5. ✅ Validação de respostas (citações, datas, contagens)
6. ✅ Audit log

### 7.2 O que Precisa de Melhoria
1. ⚠️ Parser para Google Warrant Return
2. ⚠️ Parser para outros formatos (non-Cellebrite)
3. ⚠️ Integração do chunker no pipeline de ingestão
4. ⚠️ Serviço de embeddings (não testado neste ciclo)
5. ⚠️ Rate limiting e timeout para LLM

### 7.3 Próximos Passos
1. **M6:** Frontend web (React/Next.js)
2. **M7:** Operações (backup, restore, monitoramento)
3. **Parser Google:** Prioridade alta para casos reais
4. **Embeddings:** Integrar serviço para busca vetorial

---

## 8. Anexo: Logs Relevantes

### Worker Log (Sintético)
```
2026-07-08 15:19:02,994 [sokol.worker] INFO: Processing job a1e0b431
2026-07-08 15:19:03,008 [sokol.worker] INFO: parse_xml: 30% — Parsed 113 models
2026-07-08 15:19:03,058 [sokol.worker] INFO: insert_messages: 80% — Inserted 53 messages
2026-07-08 15:19:03,175 [sokol.worker] INFO: insert_events: 90% — Inserted 103 events
2026-07-08 15:19:03,209 [sokol.worker] INFO: Job completed
```

### Worker Log (Real)
```
2026-07-08 15:53:15,503 [sokol.worker] INFO: Processing job a09ee097
2026-07-08 15:53:25,144 [sokol.worker] INFO: parse_models: 75% — Parsed 40199/40199
2026-07-08 15:53:25,144 [sokol.worker] INFO: insert_messages: 75% — Inserting 0 messages
2026-07-08 15:53:25,163 [sokol.worker] INFO: Job completed
```

### Chat Response Exemplo
```json
{
  "response": "## Conversas no WhatsApp\n\nEncontrei **38 mensagens**...",
  "tool_calls": [{"name": "query_messages", "arguments": "{\"app\":\"WhatsApp\",\"limit\":100}"}],
  "sources": [{"ref_table": "messages", "ref_id": "...", "summary": "..."}],
  "validation_warnings": []
}
```
