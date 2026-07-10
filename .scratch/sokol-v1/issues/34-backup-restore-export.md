# 34 — Backup, restore e export de caso

Status: done
Tipo: AFK
Prioridade: P3

## Parent

`PLANO_NOVO.md` TODO-23; seção 9.

## What to build

Scripts em `ops/`: backup diário do Postgres; rotina de restore em banco temporário com queries de sanidade; export de Case com manifest SHA-256 incluindo o audit log do caso e referências a Medias/Artifacts de origem; teste de restore automatizável (mensal). Export auditado no hash-chain.

## Acceptance criteria

- [ ] Backup restaurado em banco temporário passa queries de sanidade
- [ ] Export de caso tem manifest SHA-256 verificável
- [ ] Audit log do caso incluído no export e cadeia íntegra após restore
- [ ] Rotina de teste de restore executável sem intervenção manual

## Blocked by

- 05-audit-log-hash-chain
