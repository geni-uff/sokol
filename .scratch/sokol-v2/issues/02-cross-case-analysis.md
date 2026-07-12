# 02 — Cross-Case Analysis (aba "Análise Cruzada")

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`.scratch/sokol-v2/PRD.md` — Fase A1. Ver `CONTEXT.md` (Case: "busca cross-case é exceção auditada com justificativa") e ADR-0004.

## What to build

Backend `api/src/sokol/cross_case.py` (novo router, registrar em `main.py`):

- `POST /analysis/cross-case` — body: `{case_ids: [uuid, uuid, ...], justification: str}`.
  - **Autorização**: exigir papel `admin` em TODOS os `case_ids` informados; `justification` não-vazia; gravar a consulta no `audit_log` (siga o padrão de escrita de auditoria em `api/src/sokol/audit.py`).
  - Retornar, entre os casos:
    - `shared_phones`: números que aparecem em `entities`/`messages` de 2+ casos, com contagem por caso;
    - `shared_emails`: idem para e-mails;
    - `shared_locations`: pares de eventos `kind='location'` de casos diferentes a < 500 m (PostGIS `ST_DWithin`), com timestamps;
    - `similarity_score`: 0–1 = interseção/união dos seletores (telefones+e-mails) dos casos.
  - Todo match é **Indicator**: incluir `"confidence"` e nunca rotular como fato.
- Cachear resultado por par de casos (issue 01, TTL 300 s).

Frontend: aba "Análise Cruzada" — componente `web/src/components/case/CrossCaseTab.tsx`, nav em `CaseDetail.tsx`, client em `web/src/lib/api.ts`. UI: seletor de casos (só os que o usuário administra), campo justificativa obrigatório, resultado em 3 seções (telefones, e-mails, locais) com link para o caso de origem.

## Before you start

- `\d entities` e `\d messages` — confirme onde telefones/e-mails vivem (colunas `kind`/`value` em `entities`; `sender` em `messages`).
- Leia `api/src/sokol/cases.py` para o helper de checagem de papel (`require_case_member` ou equivalente admin).

## Acceptance criteria

- [x] Usuário sem papel admin em qualquer dos casos recebe 403
- [x] Request sem `justification` recebe 422
- [x] Cada consulta gera exatamente 1 linha no `audit_log` com os case_ids e a justificativa
- [x] Casos sem interseção retornam listas vazias e `similarity_score: 0`
- [x] Aba renderiza no frontend e exige justificativa antes de consultar
- [ ] Dois casos com um telefone em comum retornam esse telefone em `shared_phones` (pendente: requer dados reais de phone em entities)

## Blocked by

- 01-infra-indices-cache
