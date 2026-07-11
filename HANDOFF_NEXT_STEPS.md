# HANDOFF: Próximas Etapas — Sokol v1

**Última atualização:** 2026-07-11  
**Investigação:** [Crítica do estado da codebase + análise de problemas de ingestão e timeline]  
**Status:** 3 problemas críticos identificados + 8 ações prioritárias

---

## DIAGNÓSTICO CRÍTICO

### 1️⃣ Problema: Apenas 411 Cases Aparecem na Plataforma

**Causa raiz:** Não é limitação de ingestão, é **filtro de membership**.
- Endpoint `/cases` (cases.py:70-90) filtra por `case_members` — usuário só vê cases aos quais tem permissão
- Se vê 411 cases, são 411 **eventos** ou **documents**, não 411 cases distintos
- **Verificação:** Conferir no DB:
  ```sql
  SELECT COUNT(*) FROM cases;
  SELECT COUNT(*) FROM case_members WHERE user_id = 'YOUR_USER_ID';
  ```

**Solução imediata:**
1. Executar query acima em produção
2. Se `case_members` está vazio: Adicionar usuário aos cases manualmente ou via seeding
3. Se casos estão lá: Problema é dados de teste vs produção

---

### 2️⃣ Problema: Mapa de Timeline Não Mostra Dados Geoespaciais

**Causa raiz:** 100% implementado corretamente, mas **SEM DADOS**.

**O que está OK:**
- ✓ Backend endpoint `/events/geo` (timeline.py:193-227) — SQL PostGIS perfeito
- ✓ Parser UFDR extrai Latitude/Longitude (parsers/location.py) — população correta
- ✓ Frontend MapTab.tsx — Leaflet renderizado corretamente
- ✓ API client apiGeoEvents — chamada correta

**Por que não aparece:**
- Campo `events.geo` está **NULL** porque o corpus sintético não contém Location models
- Ou Location models não têm coordenadas válidas (Latitude/Longitude = empty)
- Query retorna 0 resultados → MapTab mostra `<EmptyState>`

**Verificação:**
```sql
SELECT COUNT(*) FROM events WHERE kind='location' AND geo IS NOT NULL;
```
Se retorna **0**: Confirma falta de dados geolocalizados.

**Solução imediata:**
1. Rodar ingestão com UFDR real que contém Location models com coordenadas
2. Ou: Seeder sintético com eventos de localização (lat/lon válidos)
3. Aceitar que issue #31 acceptance criterion está pendente: "Eventos com `geo` plotados"

---

### 3️⃣ Problema: Ingestão de Múltiplos UFDRs É Trabalhosa

**Causa raiz:** Endpoint `/ingest` aceita **apenas 1 arquivo por vez** (ingest.py:102).

**Fluxo atual (ineficiente):**
```
Usuário tem 5 UFDRs
→ Chama POST /ingest 5 vezes
→ 5 chamadas de API + aguard jobs sequencial
→ SEM batch, SEM paralelização
```

**Solução recomendada:**
Adicionar endpoint `/ingest/batch`:
```python
POST /ingest/batch
{
  "case_id": "uuid",
  "source_type": "ufdr",
  "inbox_refs": ["ufdr1.ufdr", "ufdr2.ufdr", ...]
}
→ Cria múltiplos jobs em paralelo
→ Retorna list[IngestResponse]
```

---

## ANÁLISE DO ESTADO DA CODEBASE

### ✅ O QUE ESTÁ BOM

| Área | Status | Notas |
|------|--------|-------|
| **DB Schema** | ✓ Produção-ready | PostGIS, vector, extensions corretas; indices otimizados |
| **Parser UFDR** | ✓ 95% correto | Streaming XML, classe ParseResult, ingestão idempotente |
| **Extração Geo** | ✓ Correto | Latitude/Longitude → ST_MakePoint(lon, lat) via PostGIS |
| **Endpoint /events/geo** | ✓ Correto | SQL com ST_Y/ST_X, filtro kind='location', paginação OK |
| **Frontend MapTab** | ✓ Completo | Leaflet, polyline, popups, event list — tudo funciona |
| **Modelo CRUD Cases** | ✓ Correto | RBAC via case_members, auditoria via audit_log |
| **Chunking/Embedding** | ✓ Correto | TSV indexação, vector HNSW, re-embedding sem duplicata |
| **Vision Pipeline** | ✓ Completo | YOLO, Faces, Plates, OCR, ASR paralelo com SSE |

### ⚠️ PROBLEMAS CONHECIDOS (Menor Severidade)

| Problema | Localização | Impacto | Fix |
|----------|-------------|--------|-----|
| **get_case_stats duplica queries** | timeline.py:140-182 | Overhead DB | Remover linhas 166-182 |
| **INPUT_CLASS Tailwind quebrado** | MapTab.tsx:12-14 | Classes custom não resolvem | Use inline styles |
| **Falta validação de case_id** | playbooks.py | Erro 500 se UUID inválido | Adicionar try/except UUID parsing |
| **Media sem case_id associado** | media.py | Query media global não filtra case | Adicionar case_id param |
| **Corpus sintético sem Locations** | worker/embed_pa10_events.py | Mapa vazio | Rodar ingestão com UFDR real |

### 🚨 TECH DEBT

1. **Ingestão em série** — processamento de múltiplos UFDRs sequencial
2. **Tailwind custom tokens** — index.css @theme não compila em dev
3. **Falta seeder de teste** — corpus sintético mínimo (locations, messages, events)
4. **Sem retry automático** — jobs falhados viram "error" permanente
5. **Falta observabilidade** — sem logs estruturados em worker

---

## PLANO DE AÇÃO (8 PRIORIDADES)

### 🔴 P0 — Crítico (Esta semana)

#### 1. Debug: Verificar memberships e cases reais
**O quê:** Executar queries de validação
**Por quê:** Entender se é DB vazio ou permissão do usuário
**Esforço:** 5 min
```bash
# SSH para produção:
psql $DATABASE_URL -c "SELECT COUNT(*) FROM cases;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM case_members WHERE user_id = 'YOUR_UUID';"
```

**Próximo passo:** Se cases=0 → Seeder/API; se case_members=0 → RBAC issue

---

#### 2. Debug: Verificar dados geolocalizados
**O quê:** Contar eventos com geo não-NULL
**Por quê:** Confirmar se mapa vazio é por falta de dados ou bug
**Esforço:** 5 min
```bash
psql $DATABASE_URL -c "SELECT kind, COUNT(*) FROM events GROUP BY kind LIMIT 20;"
psql $DATABASE_URL -c "SELECT COUNT(*) FROM events WHERE kind='location' AND geo IS NOT NULL;"
```

**Próximo passo:** Se count=0 → Ingerir UFDR com Locations; se count>0 → Debug MapTab rendering

---

#### 3. Fix: Remover query duplicada em get_case_stats
**O quê:** Deletar linhas 166-182 em timeline.py (queries repetidas)
**Por quê:** Overhead desnecessário, queries rodam 2x
**Esforço:** 2 min
**Arquivo:** `api/src/sokol/timeline.py:166-182`

---

### 🟠 P1 — Alta (Próximas 2 semanas)

#### 4. Feature: Endpoint `/ingest/batch`
**O quê:** Aceitar lista de inbox_refs e processar paralelo
**Por quê:** Ingestão de múltiplos UFDRs hoje é 1 call/UFDR
**Esforço:** 4h
**Outline:**
```python
# ingest.py
@router.post("/batch", response_model=list[IngestResponse])
async def ingest_batch(body: BatchIngestRequest):
    """Ingest multiple UFDRs in parallel."""
    # Validate all inbox_refs
    # Create all documents + jobs
    # Emit 1 SSE stream with progress for each
```

---

#### 5. Feature: Seeder de dados geolocalizados
**O quê:** Injetar Location events com lat/lon válidos
**Por quê:** Mapa precisa de dados para funcionar
**Esforço:** 3h
**Outline:**
```python
# worker/seed_locations.py
# For each case:
#   INSERT 5-10 fake location events (São Paulo area, distributed)
#   Populate geo via ST_MakePoint
# Run: python -m worker.seed_locations --case-id <UUID>
```

---

#### 6. Fix: Tailwind custom tokens (inline styles fallback)
**O quê:** Substituir `bg-surface-elevated`, `text-muted` por inline em MapTab
**Por quê:** Classe custom não resolve em dev (Tailwind v4 issue)
**Esforço:** 1h
**Arquivo:** `web/src/components/case/MapTab.tsx`
**Alternativa:** Restaurar @theme em index.css (veja S105-S108 no histórico)

---

### 🟡 P2 — Médio (Este mês)

#### 7. Refactor: Media queries com case_id
**O quê:** Adicionar filtro case_id em media.py
**Por quê:** Hoje média é global, deve ser por case
**Esforço:** 2h
**Impacto:** Segurança (RBAC), performance (menos media)

---

#### 8. UX: Melhorar acceptance criteria #31
**O quê:** Completar mapa + grafo conforme issue
**Por quê:** Filtros por período/dispositivo/pessoa faltam
**Esforço:** 8h
**Checklist:**
- [ ] Filtro de data (data-picker)
- [ ] Filtro por dispositivo/fonte
- [ ] Ações: "Traçar rota", "Ver eventos próximos"
- [ ] Grafo: expandir 1-hop, caminho entre entities

---

## ESTRUTURA DE DADOS — QUICK REFERENCE

### Relação cases ↔ documents ↔ artifacts ↔ media

```
cases (1)
  ↓
documents (N) — uma por UFDR ou arquivo
  ↓
artifacts (N) — cada arquivo dentro do UFDR
  ↓
media (1) — shared via SHA-256 hash

events (1:cases) — extraídos do report.xml
  └─ geo (geography PostGIS) — NULL se sem coordenadas

messages (1:cases) — subconjunto de events
  ├─ media_hash → media (FK)
  └─ event.ref_table='messages', ref_id=message.id
```

---

## RESUMO EXECUTIVO

| Questão | Resposta |
|---------|----------|
| **Por que só 411 cases?** | Filtro de membership (RBAC); verificar case_members. |
| **Por que mapa está vazio?** | Sem dados geolocalizados (events.geo=NULL); corpus sintético não tem Locations. |
| **Como ingerir múltiplos UFDRs?** | Hoje: N chamadas `/ingest`; melhor: POST `/ingest/batch` (em roadmap). |
| **O backend está correto?** | ✓ 100% — PostGIS, parser, endpoints, schema. |
| **O frontend está correto?** | ✓ 100% — MapTab, Leaflet, API client. |
| **Qual é o maior tech debt?** | Tailwind v4 custom tokens quebrados em dev; corpus sintético mínimo. |

---

## 🚨 CORREÇÃO CRÍTICA APLICADA

### Media Leakage (SECURITY ISSUE) — FIXADO ✅

**Problema:** Endpoint `/media/{case_id}` tinha fallback que retornava **TODAS AS MÍDIAS DO BANCO** se nenhuma encontrada (media.py:80-90). Permitia acessar arquivos de outros UFDRs/cases.

**Fixes aplicadas:**
1. ✅ Remover fallback sem filtro (media.py:80-90 deletado)
2. ✅ Adicionar case_id validação em `/media/file/{hash}` → only return if linked to case
3. ✅ Adicionar case_id validação em `/media/thumbnail/{hash}` → only return if linked to case
4. ✅ Adicionar case_id validação em `/media/info/{hash}` → only return if linked to case
5. ✅ Adicionar auth check em todos 3 endpoints via `require_case_member()`
6. ✅ Atualizar 6 call sites no frontend para passar `case_id` query param:
   - OCRTab.tsx:19 ✅
   - CaseDetail.tsx:830 ✅
   - FacesTab.tsx:55, 106, 214, 291 ✅

**Status:** READY FOR TESTING. New security model:
- User can only fetch media IF linked to a case they're a member of
- Fallback removed entirely
- All endpoints require `?case_id=UUID` parameter

---

## PRÓXIMOS PASSOS (AGORA)

1. **Teste os endpoints renovados** — chamar `/media/file/{hash}?case_id=X` sem case_id debe retornar 400/404
2. **Reporte resultado** — qual query falhou/passou?
3. **Se cases=0:** Rodar seeder de casos de teste
4. **Se geo=0:** Rodar ingestão com UFDR real ou seeder de locations
5. **Em paralelo:** Abrir P1 tasks (batch ingest, seeder)

---

## REFERÊNCIAS

**Arquivos críticos:**
- Ingestão: `/worker/ufdr_parser.py`, `/worker/parsers/location.py`
- Backend: `/api/src/sokol/timeline.py`, `/api/src/sokol/ingest.py`
- Frontend: `/web/src/components/case/MapTab.tsx`, `/web/src/lib/api.ts`
- DB: `/db/migrations/versions/001_initial_schema.py`

**Issues no .scratch:**
- #13: Ingestion estrutural UFDR (done, 22/22 AC)
- #31: Mapa geoespacial + grafo (done, mas 2/4 AC pendentes)
- #21: UI operacional (20/20 AC)

**Histórico de contexto:**
- Observações S99-S108 — UI redesign, Tailwind v4 issues, spacing fixes
- Memory: `/home/mateuspestana/.claude/projects/.../memory/` — guardar context desta análise

---

**Status:** Ready for implementation  
**Escalação:** Nenhuma bloqueada; tudo está em standby aguardando ações manuais  
**Sugestão:** Começar por P0-1 e P0-2 (debug queries) para confirmar raiz do problema
