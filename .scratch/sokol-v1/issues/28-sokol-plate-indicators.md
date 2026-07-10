# 28 — sokol-plate: pipeline de placas gerando Indicators

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-18 (parcial); seção 6.5; ADR-0004.

## What to build

Serviço `sokol-plate` com `/health` e `/detect`, pipeline obrigatório: YOLO detecta região → crop normalizado → OCR no crop → regex valida Mercosul e formato antigo. OCR na imagem inteira só como fallback. Placas viram `entities` kind=`plate`; leituras de baixa confiança são **Indicators** que criam **Pendência** (ADR-0004). `pipeline_version` registrado.

## Acceptance criteria

- [ ] Imagem sintética com placa passa pelo pipeline crop→OCR→regex
- [ ] Placa de baixa confiança cria Pendência, não Fact
- [ ] Regex valida Mercosul e placa antiga (testes de ambos os formatos)
- [ ] OCR direto na imagem inteira só ocorre como fallback registrado

## Blocked by

- 06-fila-de-jobs-sse
- 13-ingestion-estrutural-ufdr
