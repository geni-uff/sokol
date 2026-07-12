# 04 — Playbook Library: 4 templates de produção

Status: ready-for-agent
Tipo: AFK
Prioridade: P1

## Parent

`.scratch/sokol-v2/PRD.md` — Fase A3. Engine existente: `api/src/sokol/playbooks.py` (steps com DAG via `depends_on`; ações `search`/`filter`/`analyze`/`export`/`notify` e ações nomeadas tipo `extract_contacts`).

## What to build

Templates **seedados e versionados** (não criados à mão pela UI). Criar `api/src/sokol/playbook_templates.py` com os 4 templates como dicts Python e uma função `seed_templates()` idempotente (upsert por nome+versão), chamada no startup da API (`main.py` lifespan) ou por comando.

1. **"Padrão de Comunicação"** — quem falou com quem: top contatos por volume, horários típicos, apps usados, gaps de silêncio.
2. **"Rastreamento de Localização"** — sequência de localizações por dia, distância percorrida, lugares recorrentes (cluster por raio de 200 m), mapa exportável.
3. **"Análise de Contatos"** — agenda completa: contatos com/sem conversa, contatos em watchlist, contatos compartilhados com outras entidades do caso.
4. **"Análise Temporal"** — atividade por hora do dia × dia da semana (no fuso do caso — ADR-0007), picos, períodos mortos, primeira/última atividade.

Cada template termina com um step de síntese LLM (padrão já existente no engine) e grava execução em `playbook_executions`/`playbook_results`.

Frontend (aba Playbooks existente): seção "Biblioteca" com os 4 templates, botão "Executar", histórico de execuções com timestamp e link para resultado.

## Before you start

- Leia `api/src/sokol/playbooks.py` inteiro (~614 linhas) — use as ações que já existem; só crie ação nova se nenhuma servir, e registre-a no mesmo padrão.
- Rode um playbook existente de ponta a ponta antes de escrever os templates, para conhecer o formato de resultado.

## Acceptance criteria

- [ ] `seed_templates()` roda 2x sem duplicar templates
- [ ] Os 4 templates executam sem erro num caso com dados sintéticos e gravam resultados
- [ ] "Análise Temporal" usa `reference_timezone` do caso, não UTC
- [ ] Cada step executa em < 5 s no corpus sintético
- [ ] UI lista os 4 templates com histórico de execução

## Blocked by

None — can start immediately
