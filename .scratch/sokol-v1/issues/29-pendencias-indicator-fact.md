# 29 — Pendências humanas: Indicator → Fact

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-19; seção 8.2 (Pendências); ADR-0004, ADR-0008.

## What to build

O portão **Indicator → Fact** do glossário, ponta a ponta: API + tela de Pendências (abas Faces, Placas, Identidades) com fila de revisão (crop, score, origem, sugestões) e ações Confirmar/Corrigir/Descartar/Mesclar identidade. Confirmação cria/move arestas `resolves_to` de forma **não-destrutiva** (ADR-0008); mesclagem de Identities funde nós repontando arestas; correção posterior preserva histórico. Toda decisão exige confirmação e é auditada. Qualquer **Analista** pode resolver (decisão registrada no CONTEXT.md).

## Acceptance criteria

- [ ] Confirmar face associa via `resolves_to` sem apagar a observação
- [ ] Confirmação transforma Indicator em Fact (visível ao Agent/relatório)
- [ ] Mesclar Identities reponta arestas e é reversível com histórico
- [ ] Toda decisão gera registro de auditoria com o usuário decisor
- [ ] Leitor não consegue resolver Pendência

## Blocked by

- 20-frontend-shell
- 27-sokol-face-indicators
- 28-sokol-plate-indicators
