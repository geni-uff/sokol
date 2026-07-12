# SOKOL TASKS — Roadmap de Implementação (CONCLUÍDO)

> **⛔ ARQUIVO HISTÓRICO — não execute nada daqui.**
> Todas as 12 tasks abaixo foram implementadas e commitadas em 2026-07-11.
> O backlog ativo está em **`.scratch/sokol-v2/`**. Instruções gerais: `CLAUDE.md`.

**Fechado em:** 2026-07-12

## Resumo do que foi entregue

| Task | Descrição | Status | Commit |
|------|-----------|--------|--------|
| TASK-001 | Debug — validar caso vazio/membership | ✅ Completa | `0d54560` |
| TASK-002 | Debug — validar geolocalizações | ✅ Completa | `0d54560` |
| TASK-003 | Test — media endpoints com validação de `case_id` | ✅ Completa | `0d54560` |
| TASK-004 | Fix — query duplicada em `timeline.py` | ✅ Completa | `0d54560` |
| TASK-005 | Feature — endpoint `/ingest/batch` | ✅ Completa | `adb89d3` |
| TASK-006 | Feature — seeder de eventos geolocalizados (`worker/seed_locations.py`) | ✅ Completa | `adb89d3` |
| TASK-007 | Fix — Tailwind v4 custom tokens (inline styles) | ✅ Completa | `adb89d3` |
| TASK-008 | Refactor — media queries com filtro `case_id` | ✅ Completa | `adb89d3` |
| TASK-009 | Feature — filtros de período na timeline/mapa | ✅ Completa | `a41711b` |
| TASK-010 | Feature — filtro por app na timeline | ✅ Completa | `a41711b` |
| TASK-011 | UX — "ver eventos próximos" no mapa | ✅ Completa | `a41711b` |
| TASK-012 | Feature — traçar rota no mapa com análise temporal | ✅ Completa | `a41711b` |

Na sequência (2026-07-11, noite) foram entregues também as FEAT-001 a FEAT-008
(worker Docker, relatórios HTML, reranking, E2E Playwright, observabilidade,
export ZIP, backup stub, UX de detecções) — commits `06fe369`..`94dedcc`.

O detalhamento original de cada task foi removido por estar obsoleto; se
precisar, consulte o histórico git deste arquivo (`git log -p TASKS.md`).
