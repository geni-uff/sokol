# 03 — Entity Resolution (mesma pessoa, não-destrutiva)

Status: ready-for-agent
Tipo: AFK
Prioridade: P0

## Parent

`.scratch/sokol-v2/PRD.md` — Fase A2. **Obrigatório**: ADR-0008 (resolução não-destrutiva) e `CONTEXT.md` (Contact vs Identity, `resolves_to`).

## What to build

Backend `api/src/sokol/entity_resolution.py` (novo router, registrar em `main.py`):

- `POST /entities/resolve` — body: `{case_id: uuid}`. Gera **sugestões** de resolução dentro do caso:
  - mesmo telefone/e-mail em Contacts diferentes → sugerir mesma Identity;
  - nomes com distância de Levenshtein ≤ 2 (normalizados: lowercase, sem acento via `unaccent`) E pelo menos 1 seletor em comum → sugerir;
  - cada sugestão: `{entity_a, entity_b, reason, confidence}` — é **Indicator**, nada é aplicado automaticamente.
- `POST /entities/{id}/resolve-to` — body: `{identity_id: uuid, confirmed_by_user: true}`. Cria aresta `resolves_to` em `entity_links` (a observação continua existindo — NUNCA delete/sobrescreva a entidade). Auditar em `audit_log`.
- `PATCH /identities/{id}/merge` — body: `{other_identity_id}`. Mesclar duas Identities = repontar as arestas da segunda para a primeira e marcar a segunda como mesclada (campo/flag, não DELETE). Auditar.
- Cross-case (sugestões entre casos) só com papel admin + justificativa + auditoria, como na issue 02.

Frontend: seção "Resolução de Entidades" (dentro da aba de grafo/entidades existente ou nova aba): lista de sugestões com botões Confirmar/Rejeitar; rejeição também é persistida (para não re-sugerir).

## Before you start

- `\d entities` e `\d entity_links` — confirme colunas (tipos de aresta, força). O tipo de aresta a usar é `resolves_to`.
- Verifique se existe view/endpoint de grafo em `api/src/sokol/graph.py` para reaproveitar na UI.

## Acceptance criteria

- [ ] `POST /entities/resolve` retorna sugestões com reason e confidence; nada é gravado sem confirmação
- [ ] Confirmar sugestão cria aresta `resolves_to`; as duas entidades originais continuam consultáveis
- [ ] Merge de Identities reponta arestas; nenhuma linha é deletada; `audit_log` registra a operação
- [ ] Sugestão rejeitada não reaparece na próxima chamada
- [ ] Teste de RBAC: usuário leitor não confirma/mescla (403)

## Blocked by

- 01-infra-indices-cache
- 02-cross-case-analysis (recomendado, para reusar o padrão de autorização cross-case)
