# 23 — Watchlists + hits durante Ingestion/Enrichment

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` seção 5.9; `CONTEXT.md` (Watchlist, Hit).

## What to build

`POST /watchlists`, `GET /watchlists`, `GET /watchlists/hits`: seletores por caso (telefone, placa, CPF) com `active`. Matching roda durante **Ingestion** (Messages/Events/entities recém-gravados) e **Enrichment** (placas/OCR ao chegarem). Um **Hit** referencia o seletor e o registro casado; hits de Indicators carregam o estado não-confirmado (ADR-0004). Criação/ativação auditada.

## Acceptance criteria

- [ ] Telefone em watchlist gera Hit ao ingerir o corpus sintético que o contém
- [ ] Hit aponta para o registro de origem casado
- [ ] Hit sobre placa de baixa confiança aparece marcado como Indicator
- [ ] Watchlist inativa não gera hits

## Blocked by

- 13-ingestion-estrutural-ufdr
