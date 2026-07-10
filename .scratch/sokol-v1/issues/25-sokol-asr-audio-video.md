# 25 — sokol-asr: transcrição de áudio e vídeo

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-18 (parcial); seção 6.4.

## What to build

Serviço `sokol-asr` (faster-whisper + VAD) com `/health` e `/transcribe`, batch, timestamps por segmento. Para vídeo: worker extrai áudio para ASR e keyframes para os serviços visuais (issue 26). Transcrições viram Chunks pesquisáveis rastreáveis ao Artifact de origem; Events de mídia enriquecidos com resumo. `pipeline_version` registrado.

## Acceptance criteria

- [ ] Áudio sintético transcrito com timestamps por segmento
- [ ] Vídeo gera áudio extraído + keyframes enfileirados
- [ ] Transcrição pesquisável via busca lexical com Source até o Artifact
- [ ] Batch e healthcheck funcionando

## Blocked by

- 06-fila-de-jobs-sse
- 13-ingestion-estrutural-ufdr
