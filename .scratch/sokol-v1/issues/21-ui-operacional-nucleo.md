# 21 — UI operacional núcleo (ingestão, jobs, timeline, busca, Agent)

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-20 (etapas 7–14); seções 8.2 e 8.3.

## What to build

Sobre o shell aprovado: navegador da pasta montada com Import para staging (progresso próprio) e Ingestion com progresso SSE separado; painel de Jobs denso (cancelar/reexecutar/ver logs); Timeline com filtros (período/dispositivo/app/tipo) e "Abrir fonte"; Busca híbrida/exata com resultados, score e Sources clicáveis; Agent com streaming, ferramentas chamadas visíveis, fontes por parágrafo e status do Validator; viewer simples de Conversation. Datas exibidas com `tz_original`+offset (ADR-0007).

## Acceptance criteria

- [ ] Fluxo completo demoável: criar caso → importar UFDR sintético → ver jobs → timeline → buscar → perguntar ao Agent → abrir fonte
- [ ] Import e Ingestion têm barras de progresso separadas via SSE
- [ ] Toda Source clicável abre o registro de origem
- [ ] Status de validação do Agent visível (aprovado/aviso/falhou)
- [ ] Playwright cobrindo o fluxo principal

## Blocked by

- 12-import-inbox-staging
- 16-busca-hibrida-sources
- 19-validator-deterministico
- 20-frontend-shell
