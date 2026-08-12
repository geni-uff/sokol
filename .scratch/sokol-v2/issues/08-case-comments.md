# 08 — Comentários e anotações em casos

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`.scratch/sokol-v2/PRD.md` — Fase C1. Escopo decidido em triagem 2026-07-12 (ver `## Comments`).

## What to build

Anotações internas de trabalho, planas (sem threading), sem @menções, fora do laudo.

**Migração Alembic** — tabela `case_comments`:

```
id uuid pk, case_id uuid not null (fk cases),
author_user_id uuid not null (fk users),
target_kind text not null check in ('case','event','media'),
target_id uuid null,          -- null quando target_kind='case'
body text not null,
created_at timestamptz default now(),
edited_at timestamptz null,
deleted boolean not null default false
```

Índice: `(case_id, target_kind, target_id)`.

**Backend** `api/src/sokol/comments.py` (novo router, registrar em `main.py`):

- `POST /comments/{case_id}` — body `{target_kind, target_id?, body}`. Papéis **Admin e Analista** apenas (Leitor recebe 403).
- `GET /comments/{case_id}?target_kind=&target_id=` — lista cronológica, exclui `deleted=true`. Qualquer membro do caso (incluindo Leitor) pode ler.
- `PATCH /comments/{id}` — editar `body` (só o autor); seta `edited_at`.
- `DELETE /comments/{id}` — soft-delete (`deleted=true`); autor ou Admin do caso.
- Criar/editar/deletar registram no `audit_log` (padrão de `api/src/sokol/audit.py`).
- Validar que `target_id`, quando presente, pertence ao mesmo `case_id` (evitar referência cross-case).

**Frontend**:

- Painel "Notas do caso" (comentários com `target_kind='case'`) — onde couber melhor na `CaseDetail.tsx` (ex.: aba Dados ou seção lateral).
- Ícone/contador de comentários em cada evento da timeline; clique abre lista + campo de novo comentário.
- Comentário mostra autor, data relativa e marcador "(editado)" quando `edited_at` não-nulo.
- Esconder campo de escrita para Leitor.

## Regras fechadas na triagem (NÃO reabrir)

1. **Sem threading** — lista plana. (Se um dia precisar, adicionar `parent_id` — o schema acima aceita a evolução.)
2. **Sem @menções e sem sistema de notificação** no v2.
3. **Comentário NUNCA entra em laudo/relatório** — é material interno de trabalho, sem custódia. Se o conteúdo importa para o laudo, o analista cria um Bookmark. Garantir que `reports.py` não consuma `case_comments`.
4. **Leitor lê, mas não escreve** — consistente com `CONTEXT.md`.

## Acceptance criteria

- [x] Migração cria `case_comments` (upgrade + downgrade limpos)
- [x] Analista comenta em evento; comentário aparece na timeline com autor e data
- [x] Comentário de caso aparece no painel de notas
- [x] Leitor vê comentários mas recebe 403 ao tentar criar/editar/deletar
- [x] Não-membro do caso recebe 403 até para leitura
- [x] Soft-delete: some da UI, permanece no banco; operação no `audit_log`
- [x] Editar seta `edited_at` e mostra "(editado)" na UI
- [x] `target_id` de outro caso é rejeitado (422/404)
- [x] Relatório gerado não contém nenhum comentário

## Blocked by

None — can start immediately

## Comments

**2026-07-12 (triagem com o mantenedor):** decididas as 4 questões abertas —
(1) sem threading, lista plana; (2) sem @menções nem notificações no v2;
(3) comentários nunca entram no laudo (usar Bookmark para isso);
(4) Leitor pode ler, não pode escrever. Status promovido de `needs-triage`
para `ready-for-agent`.

**2026-08-12 (implementação):** migração `016`, router `comments.py`, painel na aba Dados
e toggle de notas na timeline (`MapTab`). Smoke-test API: create/list/edit/soft-delete,
403 leitor, 404 target cross-case, audit_log.
