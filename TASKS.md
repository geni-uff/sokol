# SOKOL TASKS — Roadmap de Implementação

**Status:** 2026-07-11  
**Último update:** Media leakage security fixes aplicadas  
**Total tasks:** 12 (4 P0 + 4 P1 + 4 P2)

---

## 🔴 P0 — CRÍTICO (Esta semana)

### TASK-001: Debug — Validar caso vazio/membership
**Prioridade:** 🔴 P0 (Blocker)  
**Esforço:** 15 min  
**Status:** ⏳ Pendente  
**Descrição:** Executar queries para validar por que apenas 411 mídias aparecem

**Checklist:**
- [ ] `SELECT COUNT(*) FROM cases;` — confirmar se há cases no DB
- [ ] `SELECT COUNT(*) FROM case_members WHERE user_id = 'YOUR_UUID';` — verificar membership
- [ ] Se vazio, rodar seeder de test cases
- [ ] Reportar resultado em `#sokol-debug`

**Outputs:**
- Resultado das queries
- Se cases vazio: rodar seeder

---

### TASK-002: Debug — Validar geolocalizações
**Prioridade:** 🔴 P0 (Blocker)  
**Esforço:** 10 min  
**Status:** ⏳ Pendente  
**Descrição:** Verificar se há dados de localização no DB

**Checklist:**
- [ ] `SELECT kind, COUNT(*) FROM events GROUP BY kind LIMIT 20;`
- [ ] `SELECT COUNT(*) FROM events WHERE kind='location' AND geo IS NOT NULL;`
- [ ] Se retorna 0: confirma que mapa vazio é por falta de dados, não bug
- [ ] Se > 0 e mapa ainda vazio: debug MapTab rendering

**Outputs:**
- Resultado das queries
- Confirmação: mapa funciona, só falta dados

---

### TASK-003: Test — Media endpoints com case_id validation
**Prioridade:** 🔴 P0 (Security)  
**Esforço:** 20 min  
**Status:** ⏳ Pendente  
**Descrição:** Verificar que endpoints /media/file, /media/thumbnail, /media/info agora requerem case_id

**Checklist:**
- [ ] Call `/media/file/{hash}` SEM case_id → deve retornar 400/401
- [ ] Call `/media/file/{hash}?case_id=WRONG_UUID` → deve retornar 404
- [ ] Call `/media/file/{hash}?case_id=CORRECT_UUID` → deve retornar arquivo
- [ ] Mesmo para `/media/thumbnail/{hash}` e `/media/info/{hash}`
- [ ] Testar no frontend: MediaTab em CaseDetail.tsx deve renderizar

**Outputs:**
- Screenshot de erro 404 tentando acessar media errada
- Screenshot de sucesso acessando media correta

---

### TASK-004: Fix — Remover query duplicada em timeline.py
**Prioridade:** 🔴 P0 (Performance)  
**Esforço:** 5 min  
**Status:** ⏳ Pendente  
**Descrição:** Linhas 166-182 em api/src/sokol/timeline.py fazem queries repetidas

**Checklist:**
- [ ] Abrir api/src/sokol/timeline.py
- [ ] Deletar linhas 166-182 (queries de messages, chunks, entities, media duplicadas)
- [ ] Testar endpoint `/events/stats` retorna valores corretos
- [ ] Commit: "fix: remove duplicate queries in get_case_stats"

**Files:**
- `api/src/sokol/timeline.py:166-182`

---

## 🟠 P1 — ALTA (Próximas 2 semanas)

### TASK-005: Feature — Endpoint `/ingest/batch` para múltiplos UFDRs
**Prioridade:** 🟠 P1  
**Esforço:** 4h  
**Status:** ⏳ Pendente  
**Descrição:** Aceitar lista de inbox_refs e processar em paralelo

**Checklist:**
- [ ] Criar modelo `BatchIngestRequest` com `inbox_refs: list[str]`
- [ ] Implementar endpoint POST `/ingest/batch`
- [ ] Validar todos os inbox_refs antes de criar jobs
- [ ] Criar múltiplos documents + jobs em paralelo
- [ ] Retornar `list[IngestResponse]`
- [ ] Emit SSE progress para cada arquivo
- [ ] Testes: ingerir 3 UFDRs via batch, verificar que retorna 3 responses
- [ ] Commit: "feat: add /ingest/batch endpoint for parallel UFDR ingestion"

**Files:**
- `api/src/sokol/ingest.py` (add endpoint)
- Tests: `api/tests/test_ingest.py`

**Acceptance criteria:**
- [ ] POST `/ingest/batch` com 5 UDRs retorna 5 IngestResponse
- [ ] Todos os 5 jobs são criados em paralelo
- [ ] SSE mostra progresso de cada arquivo

---

### TASK-006: Feature — Seeder de eventos geolocalizados
**Prioridade:** 🟠 P1  
**Esforço:** 3h  
**Status:** ⏳ Pendente  
**Descrição:** Injetar Location events com coordenadas válidas para testar mapa

**Checklist:**
- [ ] Criar `worker/seed_locations.py`
- [ ] Para cada case: gerar 5-10 Location events (São Paulo area)
- [ ] Usar `ST_MakePoint(lon, lat)` para geo
- [ ] Incluir address em meta para popups no Leaflet
- [ ] Comando: `python -m worker.seed_locations --case-id <UUID>`
- [ ] Após seed: `SELECT COUNT(*) FROM events WHERE kind='location' AND geo IS NOT NULL;` retorna > 0
- [ ] Frontend MapTab mostra pontos e polyline
- [ ] Commit: "feat: add location event seeder for map testing"

**Files:**
- `worker/seed_locations.py` (novo)

**Acceptance criteria:**
- [ ] Comando cria 10 location events com geo válido
- [ ] MapTab renderiza mapa com 10 pontos
- [ ] Popups mostram endereço e coordenadas

---

### TASK-007: Fix — Tailwind v4 custom tokens (inline styles)
**Prioridade:** 🟠 P1  
**Esforço:** 1h  
**Status:** ⏳ Pendente  
**Descrição:** Resolver custom token classes que não resolvem em dev (bg-surface-elevated, etc.)

**Checklist:**
- [ ] Identificar todos custom token classes em MapTab.tsx
- [ ] Converter para inline styles ou hardcoded values
- [ ] Alternativa: restaurar @theme em src/index.css (veja histórico S105-S108)
- [ ] Testar que MapTab renderiza sem erros de Tailwind
- [ ] Commit: "fix: replace Tailwind custom tokens with inline styles (Tailwind v4 compat)"

**Files:**
- `web/src/components/case/MapTab.tsx` (linhas 12-14, 21, etc.)

**Acceptance criteria:**
- [ ] MapTab renderiza sem warnings de Tailwind
- [ ] Cores corretas (glass morphism, border, surface)

---

### TASK-008: Refactor — Media queries com filtro case_id
**Prioridade:** 🟠 P1  
**Esforço:** 2h  
**Status:** ⏳ Pendente  
**Descrição:** Função `_get_case_images()` e `_get_case_audios()` em pipeline.py consultam media sem filtro case

**Checklist:**
- [ ] Abrir `api/src/sokol/pipeline.py:63-79` e `82-98`
- [ ] Adicionar `AND m.hash IN (...)` que filtra por case_id
- [ ] Ou: use LEFT JOIN com messages/artifacts e WHERE case_id
- [ ] Testar que `/detect/vision` só processa imagens do case correto
- [ ] Commit: "fix: filter media queries by case_id in pipeline"

**Files:**
- `api/src/sokol/pipeline.py:63-98`

**Acceptance criteria:**
- [ ] Query retorna 0 imagens se nenhuma linkada ao case
- [ ] Query retorna N imagens se N linkadas

---

## 🟡 P2 — MÉDIO (Este mês)

### TASK-009: Feature — Filtros de período na timeline/mapa
**Prioridade:** 🟡 P2  
**Esforço:** 3h  
**Status:** ⏳ Pendente  
**Descrição:** Adicionar date-picker para filtrar eventos por período

**Checklist:**
- [ ] Adicionar `start_date` e `end_date` params a `/events/timeline`
- [ ] Adicionar `start_date` e `end_date` params a `/events/geo`
- [ ] Frontend MapTab: adicionar 2 date pickers acima do mapa
- [ ] Enviar params na query: `apiTimeline(caseId, limit, offset, kind, undefined, startDate, endDate)`
- [ ] Testes: filtrar por período específico
- [ ] Commit: "feat: add date range filters to timeline and geo endpoints"

**Files:**
- `api/src/sokol/timeline.py:54-122` (get_timeline)
- `api/src/sokol/timeline.py:193-227` (get_geo_events)
- `web/src/components/case/MapTab.tsx` (adicionar date pickers)
- `web/src/lib/api.ts` (atualizar assinaturas)

---

### TASK-010: Feature — Filtro por dispositivo/app na timeline
**Prioridade:** 🟡 P2  
**Esforço:** 2h  
**Status:** ⏳ Pendente  
**Descrição:** Adicionar dropdown para filtrar por app/dispositivo

**Checklist:**
- [ ] Query `/events/timeline`: já suporta `app` param
- [ ] Frontend MapTab: adicionar select com app values
- [ ] Enviar na query: `apiTimeline(..., undefined, selectedApp)`
- [ ] Testes: filtrar por "whatsapp", "telegram", etc.
- [ ] Commit: "feat: add app filter to timeline events"

**Files:**
- `web/src/components/case/MapTab.tsx:233-250` (já existe parcial)

---

### TASK-011: UX — "Ver eventos próximos" no mapa
**Prioridade:** 🟡 P2  
**Esforço:** 2h  
**Status:** ⏳ Pendente  
**Descrição:** Click em ponto do mapa → mostra eventos em raio de X metros

**Checklist:**
- [ ] MapTab: adicionar click handler no marker
- [ ] Query DB: `SELECT * FROM events WHERE st_distance(geo, clicked_point) < 1000` (1km)
- [ ] Mostrar em modal ou sidebar: lista de eventos próximos ordenados por distância
- [ ] Testes: click em ponto, verificar eventos próximos
- [ ] Commit: "feat: add 'nearby events' action on map markers"

**Files:**
- `web/src/components/case/MapTab.tsx:16-99` (LeafletMap)
- `api/src/sokol/timeline.py` (novo endpoint `/events/nearby`)

---

### TASK-012: Feature — Traçar rota no mapa
**Prioridade:** 🟡 P2  
**Esforço:** 3h  
**Status:** ⏳ Pendente  
**Descrição:** Visualizar caminho do sujeito conectando pontos geolocalizados

**Checklist:**
- [ ] MapTab já renderiza polyline entre pontos (MapTab.tsx:67-73)
- [ ] Adicionar:
  - [ ] Cores alternadas por período (ex: vermelho noturno, azul diurno)
  - [ ] Velocidade média entre pontos
  - [ ] Tempo total de deslocamento
  - [ ] Saltos suspeitos (> 100 km/h)
- [ ] Botão "Traçar rota" que expande detalhes
- [ ] Testes: visualizar rota com 10 pontos
- [ ] Commit: "feat: enhance map route visualization with time analysis"

**Files:**
- `web/src/components/case/MapTab.tsx:64-78` (enhance polyline)

---

## 📊 DEPENDÊNCIAS E SEQUÊNCIA

```
TASK-001 (Debug casos)
├─→ TASK-002 (Debug geo)
│   └─→ TASK-006 (Seed locations)
│       └─→ TASK-010, TASK-011, TASK-012
├─→ TASK-003 (Test media security)
│   └─→ TASK-008 (Refactor media queries)
└─→ TASK-004 (Fix perf)
    └─→ TASK-005 (Batch ingest)
        └─→ TASK-007 (Fix Tailwind)
            └─→ TASK-009 (Date filters)
```

---

## 📋 CHECKLIST DE IMPLEMENTAÇÃO

- [ ] TASK-001 completa → debug bloqueia
- [ ] TASK-002 completa → confirma mapa é por dados
- [ ] TASK-003 completa → security validada
- [ ] TASK-004 completa → perf melhora
- [ ] TASK-005 completa → ingestão batch
- [ ] TASK-006 completa → mapa tem dados
- [ ] TASK-007 completa → Tailwind fixo
- [ ] TASK-008 completa → RBAC media correto
- [ ] TASK-009-012 completas → UX mapa completa

---

## COMO USAR ESTE ARQUIVO

1. **Para começar:** Faça TASK-001 (15 min debug)
2. **Para rastreamento:** Atualize status de `⏳ Pendente` → `🔄 Em andamento` → `✅ Completa`
3. **Para dependências:** Respeite a sequência acima
4. **Para reportar:** Inclua task ID no commit: `fix: TASK-004 remove duplicate queries`

---

**Próximo:** Comece por TASK-001 (debug cases) para validar estado atual
