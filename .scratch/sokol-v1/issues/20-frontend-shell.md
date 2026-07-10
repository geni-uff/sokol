# 20 — Frontend shell: login, casos e tema visual

Status: ready-for-human
Tipo: HITL
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-20 (etapas 1–6); seções 8, 8.1, 8.2, 8.3.

## What to build

App `web/` com React+Vite+TypeScript+Tailwind+shadcn/ui+TanStack Query. Shell operacional: sidebar compacta, topbar (caso ativo, status de serviços, usuário), rodapé de status com conexão SSE. Tema futurista/minimalista da seção 8 (fundo escuro técnico, sem hero/landing). Telas: login (sem branding promocional) e lista/criação de casos. Estados globais obrigatórios da 8.3 (vazio, carregando, erro, sem permissão, andamento, concluído).

**HITL**: a direção visual definida aqui propaga para todas as telas — apresentar o tema ao usuário para aprovação antes de prosseguir para a issue 21.

## Acceptance criteria

- [ ] Login funcional contra a API; erro claro para credencial inválida
- [ ] Criar/listar/abrir caso funcionando ponta a ponta
- [ ] Indicador de saúde consome `/health` real
- [ ] Estados da seção 8.3 implementados como componentes reutilizáveis
- [ ] **Aprovação do usuário na direção visual**
- [ ] Teste Playwright de login + criação de caso

## Blocked by

- 04-auth-casos-rbac
