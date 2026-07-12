# 05 — Heatmaps forenses (aba "Analytics")

Status: ready-for-agent
Tipo: AFK
Prioridade: P1

## Parent

`.scratch/sokol-v2/PRD.md` — Fase B1.

## What to build

Backend `api/src/sokol/analytics.py` (novo router, registrar em `main.py`), tudo escopado por `case_id` + `require_case_member`:

- `GET /analytics/{case_id}/activity-heatmap` — matriz 7×24 (dia da semana × hora, **no fuso do caso**, ADR-0007): `SELECT extract(dow ...), extract(hour ...), count(*) FROM events WHERE case_id=... GROUP BY 1,2`. Param opcional `kind` para filtrar tipo de evento.
- `GET /analytics/{case_id}/location-heatmap` — agregação de eventos `kind='location'` em grid (arredondar lat/lon a 3 casas decimais ≈ 110 m): `[{lat, lon, count}]` para heat layer no Leaflet.
- `GET /analytics/{case_id}/contact-frequency` — top N contrapartes por volume de mensagens/chamadas, com série mensal.
- Cachear os 3 endpoints (issue 01, TTL 300 s, invalidar pós-ingestão).

Frontend: aba "Analytics" — `web/src/components/case/AnalyticsTab.tsx` + nav em `CaseDetail.tsx` + client em `api.ts`:
- heatmap de atividade como grid CSS colorido (sem lib nova de gráfico se possível; se precisar, use a que já estiver em `web/package.json` — verifique antes de adicionar dependência);
- heatmap de localização com `leaflet.heat` sobre o mapa já usado no MapTab;
- barras de frequência de contato.

Lembrete Tailwind v4: tokens custom não resolvem em dev — inline styles ou classes padrão.

## Acceptance criteria

- [ ] Heatmap de atividade respeita o `reference_timezone` do caso
- [ ] Endpoints retornam 403 para não-membro do caso
- [ ] Caso sem eventos retorna estruturas vazias (não 500)
- [ ] Aba renderiza os 3 painéis com dados sintéticos
- [ ] Nenhuma dependência frontend nova sem verificar as existentes primeiro

## Blocked by

- 01-infra-indices-cache
