# 33 — /ops: observabilidade e operação

Status: done
Tipo: AFK
Prioridade: P3

## Parent

`PLANO_NOVO.md` TODO-22; seção 8.2 (Operação).

## What to build

Página `/ops` restrita a Admin: saúde de todos os serviços (API, Postgres, LM Studio, embed, workers), fila por estágio, jobs falhos com últimos erros, uso de GPU quando disponível, latência p50/p95 de busca e Agent, ações "Reprocessar falhas"/"Ver logs", e alerta simples para fila parada e disco baixo.

## Acceptance criteria

- [ ] Operador identifica serviço parado sem ler logs manualmente
- [ ] Fila travada e disco baixo disparam alerta visível
- [ ] Latências p50/p95 de busca e Agent exibidas
- [ ] Leitor/Analista não acessam `/ops` (403)

## Blocked by

- 06-fila-de-jobs-sse
- 20-frontend-shell
