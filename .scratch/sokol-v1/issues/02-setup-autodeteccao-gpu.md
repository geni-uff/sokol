# 02 — Setup com autodetecção de GPU

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-03; seção 3.

## What to build

Script `ops/setup` idempotente que gera `.env` a partir de `deploy/env.example`: detecta GPUs via `nvidia-smi`, resolve `SOKOL_GPU_MODE=auto` para variáveis concretas (`SOKOL_RESOLVED_GPU_*`), recomenda a GPU de maior VRAM para o LM Studio no host quando houver 2+, usa GPU única com concorrência reduzida quando houver 1, e falha com mensagem clara quando GPU é exigida e não existe. Valida overrides quando `SOKOL_GPU_MODE=manual`. Pergunta/detecta a pasta local de ingestão (`SOKOL_HOST_INGEST_DIR`) e valida que o Docker consegue montá-la.

## Acceptance criteria

- [ ] Mesmo setup gera `.env` correto em máquina com 0, 1 e 2+ GPUs (simulável em teste)
- [ ] `SOKOL_GPU_MODE=manual` com índice inválido falha antes de subir containers
- [ ] Segredos gerados no setup, fora do repositório
- [ ] Rodar duas vezes não corrompe o `.env` (idempotente)

## Blocked by

- 01-monorepo-compose-minimo
