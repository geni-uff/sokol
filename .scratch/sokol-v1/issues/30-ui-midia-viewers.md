# 30 — UI de mídia: galeria, viewer de documento, player

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-20 (etapas restantes); seção 8.2 (Mídia, Viewer de documento).

## What to build

Galeria densa de Media (imagens/vídeos/áudios) com filtros por label/face/placa/período/GPS/confiança, **blur por padrão** para categorias sensíveis com ação Revelar (auditada), badges de confiança distinguindo Indicator de Fact (ADR-0004). Viewer de documento com highlight por bbox, busca interna e citações relacionadas. Player de áudio/vídeo com transcrição sincronizada quando existir.

## Acceptance criteria

- [ ] Categoria sensível abre borrada; Revelar é auditado
- [ ] Badge diferencia Indicator (não confirmado) de Fact
- [ ] Viewer de documento destaca bbox da Source clicada
- [ ] Transcrição sincronizada com o player quando disponível

## Blocked by

- 21-ui-operacional-nucleo
- 24-sokol-doc-ocr
- 25-sokol-asr-audio-video
- 26-sokol-vision-keyframes
