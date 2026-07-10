# 27 — sokol-face: detecção facial gerando Indicators

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-18 (parcial); seção 6.6; ADR-0002, ADR-0004, ADR-0008.

## What to build

Serviço `sokol-face` (InsightFace `buffalo_l`) com `/health`, `/detect`, `/embed`, `/compare`, batch. Worker: faces detectadas viram `entities` kind=`face` (clusters por embedding); matches automáticos têm score e limiar e são **Indicators** (ADR-0004) — face sem Identity validada cria **Pendência** (consumida na issue 29). Nenhuma associação automática face→Identity vira Fact sem humano. `pipeline_version` registrado.

## Acceptance criteria

- [ ] Rostos do corpus sintético geram entities `face` com embeddings
- [ ] Match automático carrega score e estado de Indicator
- [ ] Face desconhecida cria Pendência pendente de revisão
- [ ] Nenhuma aresta `resolves_to` criada automaticamente sem confirmação humana

## Blocked by

- 06-fila-de-jobs-sse
- 13-ingestion-estrutural-ufdr
