# PRD — SOKOL v2: Inteligência Investigativa

**Criado:** 2026-07-12
**Contexto:** O v1 (`.scratch/sokol-v1/`, issues 01–34) está concluído: ingestão UFDR, busca híbrida, timeline/mapa, pipeline ML, playbooks básicos, watchlists, relatórios HTML. O v2 transforma dados por caso em inteligência entre casos e análises derivadas.

## Objetivo

Dar ao analista respostas que hoje exigem trabalho manual: "estes dois casos se conectam?", "quem é essa pessoa em todos os casos?", "qual o padrão de vida do alvo?", "o que é anômalo nesta timeline?".

## Regras que valem para TODAS as issues deste PRD

1. **RBAC**: tudo escopado por `case_id`; features cross-case (issues 02, 03) exigem papel Admin, justificativa obrigatória no request e registro no `audit_log`. Ver `CLAUDE.md` (invariantes) e ADR-0004/0008.
2. **Indicator ≠ Fact**: qualquer match automático (similaridade, anomalia, resolução de entidade) é *Indicator* com score — nunca afirmado como fato nem incluído em laudo sem confirmação humana.
3. **Antes de codar**: verifique o schema real (`docker exec -it sokol-postgres psql -U sokol -d sokol` + `\d tabela`) e o módulo citado — a issue pode ter envelhecido em relação ao código.
4. **Padrões do repo**: router novo = arquivo em `api/src/sokol/` + `app.include_router()` em `main.py`; aba nova no frontend = componente em `web/src/components/case/` + item de navegação em `CaseDetail.tsx` + funções em `web/src/lib/api.ts`.
5. Ao concluir: marcar acceptance criteria, `Status: done`, commit `feat(v2-NN): descrição`.

## Issues (ordem recomendada de execução)

| # | Issue | Fase | Status inicial |
|---|-------|------|----------------|
| 01 | Infra: índices, cache e otimização de busca | pré-req | done |
| 02 | Cross-Case Analysis (dashboard "Análise Cruzada") | A1 | done |
| 03 | Entity Resolution (mesma pessoa entre casos) | A2 | done |
| 04 | Playbook Library (4 templates de produção) | A3 | done |
| 05 | Heatmaps forenses (aba Analytics) | B1 | done |
| 06 | Detecção de anomalias na timeline | B2 | done |
| 07 | Watchlists em tempo real na ingestão | B3 | done |
| 08 | Comentários e anotações em casos | C1 | ready-for-agent |
| 09 | Relatórios PDF reais com gráficos | C2 | done |
| 10 | Export em massa (CSV/VCard/KML) | C3 | ready-for-agent |
| 11 | Backup/restore real via API (substituir stub) | débito | ready-for-agent |

Dependências: 02, 03 e 05 dependem de 01. 03 recomenda-se após 02. Demais são independentes.

## Métricas de sucesso

- Matching cross-case com precisão verificável (toda sugestão carrega evidência: número/e-mail/local exato compartilhado).
- Execução de playbook < 5 s por step no corpus de teste.
- Zero vazamento entre casos (testar acesso negado sem membership permanece obrigatório em toda issue).

## Fora de escopo do v2

- Assinatura digital de laudos (RSA) — precisa de decisão de produto/jurídica.
- Clustering ML de entidades — v2 usa matching determinístico (valor exato, Levenshtein para nomes); ML só se o determinístico se provar insuficiente.
