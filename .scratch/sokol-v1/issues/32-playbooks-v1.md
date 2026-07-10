# 32 — Playbooks v1

Status: done
Tipo: AFK
Prioridade: P3

## Parent

`PLANO_NOVO.md` seção 7.5; `CONTEXT.md` (Playbook).

## What to build

Motor de **Playbooks**: workflows versionados em YAML (ou tabela versionada) com plano fixo de Structured tools e síntese LLM **apenas no final**. Implementar os cinco da v1: `triagem-ufdr`, `relatorio-do-dia`, `perfil-do-alvo` (usa Identity/`resolves_to`), `vinculos`, `padrao-de-vida`. Saída com Sources, validada pelo Validator, auditada como o Agent.

## Acceptance criteria

- [ ] `relatorio-do-dia` roda o plano fixo e sintetiza só ao final
- [ ] `perfil-do-alvo` percorre a Identity e suas observações resolvidas
- [ ] Saída passa pelo Validator igual a resposta de Agent
- [ ] Playbook versionado: mudar o YAML gera nova versão auditável

## Blocked by

- 19-validator-deterministico
