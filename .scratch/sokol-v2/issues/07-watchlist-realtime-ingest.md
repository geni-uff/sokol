# 07 — Watchlists em tempo real durante a ingestão

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`.scratch/sokol-v2/PRD.md` — Fase B3. Módulo existente: `api/src/sokol/watchlists.py` (scan manual sob demanda). `CONTEXT.md`: Watchlist roda "durante Ingestion e Enrichment".

## What to build

1. **Hook de scan na ingestão**: ao final do parse de cada Document no worker (`worker/ingest_worker.py` / `worker/ufdr_parser.py`), rodar os seletores das watchlists ativas contra os dados recém-inseridos daquele `document_id` (não re-escanear o caso inteiro). Gravar hits na tabela de hits existente (verifique o nome com `\dt *hit*` / leitura de `watchlists.py`).
2. **Regras de match melhores** no motor de scan:
   - normalização de telefone (remover `+55`, espaços, hífens) antes de comparar;
   - match exato para CPF/CNPJ/placa/e-mail; fuzzy (Levenshtein ≤ 1) apenas para nomes;
   - campo `match_type` no hit (`exact` | `fuzzy` | `regex`).
3. **Notificação**: evento SSE no canal de progresso da ingestão já existente (`/ingest/progress`) quando houver hit, e badge de contagem de hits na UI de watchlists.
4. Watchlists com escopo: adicionar campo `case_id nullable` — NULL = global (comportamento atual), preenchido = só naquele caso. Migração Alembic.

## Before you start

- Leia `api/src/sokol/watchlists.py` inteiro e identifique a função de scan reutilizável; extraia-a para ser chamável pelo worker sem HTTP se necessário (worker e API compartilham o Postgres).
- Confirme como o worker emite progresso hoje (grep `progress` em `worker/ingest_worker.py`).

## Acceptance criteria

- [x] Hook pós-inserção no ufdr_parser roda scan incremental (IDs recém-inseridos); engine verificado carregando dentro do container do worker
- [x] Telefone `+55 21 99715-0213` casou 214 linhas gravadas como `5521997150213` (match_type=exact)
- [x] Watchlist escopada ao caso Apple: scan no caso Google = 0 watchlists, 0 hits
- [x] Hit emitido no canal de progresso da ingestão (stage `watchlist`); badge de hits na WatchlistsTab (polling 30 s)
- [x] Re-scan criou 0 duplicatas (dedup por watchlist+pattern+row)

## Blocked by

None — can start immediately
