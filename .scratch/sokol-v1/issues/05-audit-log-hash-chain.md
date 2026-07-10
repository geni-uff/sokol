# 05 — Audit log hash-chain append-only

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-05; seção 4.6.

## What to build

Módulo de auditoria: formato canônico de payload JSON, inserção que calcula `hash = sha256(prev_hash || canonical_json(payload))`, role da aplicação sem `UPDATE`/`DELETE` em `audit_log`, helper de registro usado pela API, e verificador da cadeia inteira (executável como job). Eventos mínimos registrados: login, criação de caso, ingestão, troca de modelo, busca, resposta do Agent, relatório, decisão humana.

## Acceptance criteria

- [ ] Registros são append-only; UPDATE/DELETE negados à role da aplicação (teste no banco)
- [ ] Verificador percorre a cadeia e detecta adulteração manual de um registro
- [ ] Login e criação de caso já geram registros de auditoria
- [ ] Payload canônico estável (mesma entrada → mesmo hash)

## Blocked by

- 03-migrations-schema-completo
