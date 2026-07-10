# 10 — Registro de modelos (troca runtime só LLM/reranker)

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-06 (reduzido); seções 2.5 e 7.3; ADR-0006.

## What to build

Registro de modelos em `models.yaml` versionado: LLM default, embedding **fixo** e reranker default. API administrativa lista modelos e permite trocar **LLM e reranker** em runtime, com validação de endpoint (modelo responde, contexto compatível) e auditoria da troca (`model.changed`). O embedding aparece no registro como somente-leitura em runtime (ADR-0006) — sem fluxo de troca, sem reindexação como feature.

## Acceptance criteria

- [ ] Admin troca LLM ativo sem editar código e sem reindexação; troca auditada
- [ ] Troca de reranker em runtime funciona e é auditada
- [ ] Tentativa de trocar embedding via API é rejeitada com mensagem citando ADR-0006
- [ ] Backend valida que o modelo selecionado responde antes de ativar

## Blocked by

- 05-audit-log-hash-chain
- 08-client-llm-lmstudio
- 09-sokol-embed-docker
