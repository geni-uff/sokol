# 06 — Detecção de anomalias na timeline

Status: ready-for-agent
Tipo: AFK
Prioridade: P1

## Parent

`.scratch/sokol-v2/PRD.md` — Fase B2. Toda anomalia é **Indicator** (ADR-0004): score + explicação, nunca afirmada como fato.

## What to build

Backend `api/src/sokol/anomalies.py` (novo router em `main.py`) + análise sob demanda (POST dispara, GET lê resultados persistidos):

- `POST /anomalies/{case_id}/analyze` — roda as regras determinísticas abaixo e persiste em tabela nova `anomalies` (migração Alembic: `id, case_id, kind, severity, score, explanation, ref_event_ids uuid[], created_at, dismissed boolean default false`):
  1. **Salto impossível**: pares consecutivos de eventos `kind='location'` cuja velocidade implícita > 150 km/h (usar `ST_Distance` em metros / Δt). Já existe lógica parecida no route analytics do MapTab/timeline (commit `a41711b`) — procure e reutilize.
  2. **Horário atípico**: eventos entre 02h–05h no fuso do caso quando > 3× a média do caso nessa janela.
  3. **Contato-relâmpago**: contraparte nova com > 20 mensagens nas primeiras 24 h de contato.
  4. **Silêncio anômalo**: gap > 48 h num caso com média de atividade diária.
- `GET /anomalies/{case_id}` — lista com filtro `?dismissed=false`.
- `PATCH /anomalies/{id}/dismiss` — analista descarta (auditar).

Frontend: seção "Anomalias" (na aba Timeline ou Analytics — escolher a que exigir menos código novo): lista ordenada por severidade, cada item com explicação em PT e link para os eventos de origem; botão "Descartar".

## Before you start

- Confirme como o route analytics existente calcula velocidade entre pontos (grep por `speed`/`velocidade`/`ST_Distance` em `api/src/sokol/timeline.py` e `web/src/components/case/MapTab.tsx`).
- `\d events` para os campos de timestamp e geo.

## Acceptance criteria

- [ ] Migração cria a tabela `anomalies` (upgrade + downgrade limpos)
- [ ] Corpus sintético com salto de 500 km em 10 min gera anomalia kind `impossible_jump`
- [ ] Regras de horário usam o fuso do caso (ADR-0007)
- [ ] Dismiss persiste e some da lista default; fica no `audit_log`
- [ ] Nenhuma anomalia é exposta como fato — resposta sempre carrega `score` e `explanation`

## Blocked by

None — can start immediately (melhor depois de 01 para índices)
