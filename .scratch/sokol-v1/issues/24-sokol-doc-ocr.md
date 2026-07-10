# 24 — sokol-doc: OCR/documentos como serviço

Status: done
Tipo: AFK
Prioridade: P2

## Parent

`PLANO_NOVO.md` TODO-18 (parcial); seções 2.1 e 6.3.

## What to build

Serviço `sokol-doc` (Docling + fallback OCR) com `/health` e `/parse`, persistente (nunca subprocess por imagem): PDF com camada de texto não é OCRizado página inteira; tabelas/layout preservados quando possível; bboxes armazenados quando disponíveis. Worker de Enrichment consome via HTTP, gera Chunks de documento com `page_start/page_end/bbox` e registra `pipeline_version`.

## Acceptance criteria

- [ ] PDF com texto nativo não passa por OCR completo (teste com fixture)
- [ ] Chunks de documento carregam página e bbox quando disponíveis
- [ ] Resultado persistido com `pipeline_version`
- [ ] Batch suportado; healthcheck no compose

## Blocked by

- 06-fila-de-jobs-sse
- 13-ingestion-estrutural-ufdr
