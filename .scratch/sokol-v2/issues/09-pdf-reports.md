# 09 — Relatórios PDF reais com gráficos e cadeia de custódia

Status: ready-for-agent
Tipo: AFK
Prioridade: P2

## Parent

`.scratch/sokol-v2/PRD.md` — Fase C2. Estado atual: `api/src/sokol/reports.py` gera **HTML** (o PDF foi adiado no FEAT-002, commit `fda3b49`).

## What to build

1. **Conversão HTML→PDF** no backend: usar WeasyPrint (adicionar a `api/pyproject.toml`; requer libs de sistema no `api/Dockerfile` — `libpango`, `libcairo`; verifique a doc do WeasyPrint para a imagem base usada no Dockerfile). Endpoint existente de download passa a aceitar `?format=pdf|html` (default `html`, para não quebrar chamadas atuais).
2. **Conteúdo do laudo** (estender o template HTML existente):
   - capa com número do caso, `legal_ref`, período coberto, data de geração e usuário gerador;
   - sumário executivo;
   - seção de cadeia de custódia: por Document — nome, SHA-256, data de ingestão, jobs executados;
   - gráficos estáticos: heatmap de atividade e top contatos (reusar os endpoints da issue 05; renderizar server-side como SVG embutido no HTML — sem JS no PDF);
   - **apenas Facts e Bookmarks** entram como asserção; Indicators só se explicitamente rotulados como "indício não confirmado" (ADR-0004).
3. Registrar geração de laudo no `audit_log`.

**Fora de escopo**: assinatura digital RSA (decisão pendente — ver PRD, "Fora de escopo").

## Before you start

- Leia `api/src/sokol/reports.py` e o template atual; gere um relatório HTML de um caso sintético antes de mudar qualquer coisa.
- WeasyPrint em container costuma falhar por falta de libs de sistema: teste `docker compose build sokol-api` cedo.

## Acceptance criteria

- [ ] `?format=pdf` baixa um PDF renderizado; `?format=html` continua funcionando igual a hoje
- [ ] PDF contém capa, custódia (com SHA-256 por Document) e ao menos 1 gráfico SVG
- [ ] Nenhum Indicator aparece como afirmação
- [ ] Geração registrada no `audit_log`
- [ ] Build do container da API passa com a nova dependência

## Blocked by

- 05-heatmaps-analytics (para os gráficos; se 05 não estiver pronta, entregar PDF sem gráficos e deixar este AC pendente)
