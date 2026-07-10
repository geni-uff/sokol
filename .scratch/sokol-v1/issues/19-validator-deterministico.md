# 19 — Validator determinístico

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-17; `CONTEXT.md` (Validator); ADR-0003, ADR-0004.

## What to build

O **Validator** do glossário, executado sobre toda resposta do Agent antes da entrega: toda Source aponta para registro de origem existente (ADR-0003) e do mesmo `case_id`; datas citadas pertencem ao intervalo solicitado; contagens/durações batem com o retorno das ferramentas; Indicators não redigidos como afirmação categórica (ADR-0004). Falha → no máximo **um** retry de síntese com feedback; persistindo → entrega com avisos explícitos (`validation.status: warning|failed`), nunca aceitação silenciosa.

## Acceptance criteria

- [ ] Citação inexistente é rejeitada (teste com Source forjada)
- [ ] Source de outro `case_id` é rejeitada
- [ ] Contagem divergente do retorno da ferramenta gera aviso
- [ ] Segundo retry não acontece; resposta sai com aviso explícito

## Blocked by

- 18-agent-v1
