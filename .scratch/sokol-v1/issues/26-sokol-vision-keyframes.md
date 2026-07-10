# 26 — sokol-vision: triagem visual + keyframes

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-18 (parcial); seções 2.2 e 6.4.

## What to build

Serviço `sokol-vision` (SigLIP/Qwen-VL embedding ou equivalente local) com `/health`, `/embed_image` e `/classify`, batch. Worker de Enrichment processa imagens e keyframes: labels de triagem visual gravados como **Indicators** com score (ADR-0004), embeddings visuais persistidos para busca futura. Labels sensíveis marcam a Media para blur por padrão na galeria. `pipeline_version` registrado.

## Acceptance criteria

- [ ] Imagens do corpus sintético recebem labels com score, marcados como Indicators
- [ ] Categorias sensíveis marcadas para blur por padrão
- [ ] Keyframes de vídeo processados igual a imagens
- [ ] Batch e healthcheck funcionando

## Blocked by

- 06-fila-de-jobs-sse
- 13-ingestion-estrutural-ufdr
