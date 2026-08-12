# 11 — Backup/restore real via API (substituir stub)

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`.scratch/sokol-v2/PRD.md` — débito técnico. Estado atual: `api/src/sokol/case_backup.py` (FEAT-007, commit `0d6871c`) só agenda/lista — **não executa backup nenhum**. Scripts shell de backup existem em `ops/` — verificar o que fazem antes de duplicar lógica.

## What to build

1. **Execução real**: job de backup que roda `pg_dump` do Postgres (via `docker exec` não funciona de dentro do container da API — usar `pg_dump` instalado na imagem da API apontando para o host `sokol-postgres`, credenciais das mesmas envs `DATABASE_URL`) + tar dos diretórios de mídia/staging do caso ou globais. Saída em diretório configurável `SOKOL_BACKUP_DIR` (adicionar a `deploy/env.example`), com nome `sokol_backup_YYYYMMDD_HHMMSS.tar.gz` e SHA-256 gravado ao lado.
2. **Agendamento**: o schedule já persistido pelo stub passa a ser respeitado — loop no worker (`worker/loop.py`) checa a cada N minutos se há backup devido e executa.
3. **Restore**: endpoint admin-only `POST /backup/restore` com body `{backup_file: str, confirm: true}` — valida SHA-256 antes; documentar claramente que restore sobrescreve o banco (exigir `confirm: true`).
4. Listagem passa a mostrar backups reais do diretório (nome, tamanho, SHA-256, data), não registros fictícios.
5. Todos os endpoints: admin-only + `audit_log`.

## Before you start

- Leia `case_backup.py` e os scripts em `ops/` — se `ops/backup` já faz o dump corretamente, a API pode orquestrá-lo em vez de reimplementar.
- Verifique se `pg_dump` existe na imagem da API (`docker exec sokol-api which pg_dump`); se não, adicionar `postgresql-client` ao `api/Dockerfile`.

## Acceptance criteria

- [x] `POST /backup` gera um `.tar.gz` real com dump SQL restaurável + SHA-256
- [x] Restore em banco limpo reproduz os casos (testar com caso sintético)
- [x] Backup agendado dispara sozinho via worker no horário devido
- [x] Restore sem `confirm: true` retorna 400; não-admin recebe 403
- [x] Operações registradas no `audit_log`

## Blocked by

None — can start immediately
