# 04 — Auth local + casos + RBAC (3 papéis)

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-08; seções 5.2 e 9; `CONTEXT.md` (Case, Admin, Analista, Leitor).

## What to build

Autenticação local (senha Argon2, sessão/token seguro) e endpoints de Casos (`POST /cases`, `GET /cases`, `GET /cases/{id}`), com RBAC por caso nos três papéis do glossário: **Admin** (tudo + membros + cross-case), **Analista** (opera, resolve Pendência, gera laudo), **Leitor** (somente leitura). Todos os endpoints exigem auth exceto `/health`. Sem gate de Perito — decisão deliberada registrada no `CONTEXT.md`.

## Acceptance criteria

- [ ] Usuário autenticado cria caso; não autenticado recebe 401
- [ ] Leitor não consegue ingerir nem alterar dados do caso
- [ ] Usuário fora de `case_members` não acessa caso alheio (teste de RBAC)
- [ ] Busca cross-case bloqueada por padrão (fundação para exceção auditada)
- [ ] Testes cobrindo os três papéis

## Blocked by

- 03-migrations-schema-completo
