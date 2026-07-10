# 22 — Relatórios: bookmarks + IPJ/laudo com hashes

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-21; seção 5.8; ADR-0003, ADR-0004.

## What to build

**Bookmarks** de evidências; `POST /reports/ipj` (por filtro) e `POST /reports/laudo` (a partir de Bookmarks), gerando DOCX/PDF como **saída** (nunca formato intermediário), com Sources citadas até a origem (ADR-0003), SHA-256, origem da evidência, data, usuário gerador e manifest auditável. **Indicators ficam fora de seções de asserção factual** (ADR-0004). Relatório registrado no audit log.

## Acceptance criteria

- [ ] Cada afirmação do relatório rastreável até evidência e hash de origem
- [ ] Indicator não aparece como afirmação categórica (teste com placa não confirmada)
- [ ] Manifest do relatório verificável
- [ ] Geração auditada no hash-chain

## Blocked by

- 05-audit-log-hash-chain
- 19-validator-deterministico
