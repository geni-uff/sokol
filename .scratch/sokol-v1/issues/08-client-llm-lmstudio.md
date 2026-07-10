# 08 — Client LLM OpenAI-compatible (LM Studio no host)

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-07; seções 1.4 e 2.3.

## What to build

Client interno OpenAI-compatible para chat completions consumindo `SOKOL_LMSTUDIO_BASE_URL` (default `http://host.docker.internal:1234/v1`), com healthcheck de modelos carregados exposto no `GET /health` da API (`lmstudio: ok|down`). Trocar host/porta/provedor não pode exigir mudança de código. Suporte a streaming (necessário para o Agent depois).

## Acceptance criteria

- [ ] API dentro do Docker gera resposta usando somente `SOKOL_LMSTUDIO_BASE_URL`
- [ ] `/health` reporta o estado do LM Studio mesmo sendo serviço externo ao compose
- [ ] Timeout e erro de conexão produzem falha explícita, não travamento
- [ ] Teste com mock de servidor OpenAI-compatible (não exige LM Studio no CI)

## Blocked by

- 01-monorepo-compose-minimo
