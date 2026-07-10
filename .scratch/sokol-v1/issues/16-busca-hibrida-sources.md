# 16 — Busca híbrida com Sources de origem

Status: done
Tipo: AFK
Prioridade: P1

## Parent

`PLANO_NOVO.md` TODO-14; seções 5.5 e 7.1; ADR-0003.

## What to build

`POST /search/scan` (modos `semantic`, `lexical`, `hybrid`, `exact-normalized`) e `POST /search/exact`: vetorial em `chunks.embedding`, lexical em `chunks.tsv`, exata normalizada com `unaccent`, fusão por RRF no híbrido, rerank quando o serviço `sokol-rerank` estiver saudável (degrada sem ele). Resultados retornam **Sources apontando ao registro de origem** (Message/Media/Document+página — ADR-0003) com previews. Filtros por caso, período e tipo de Artifact. Busca auditada.

## Acceptance criteria

- [ ] Golden set roda com recall@k e MRR medidos
- [ ] Toda resposta traz Sources com `origin_ref_table`/`origin_ref_id` resolvíveis
- [ ] Rerank indisponível degrada para RRF puro sem erro
- [ ] Modo `exact-normalized` ignora acentos e espaços duplicados

## Blocked by

- 15-chunking-embedding-tsv
