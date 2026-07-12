# 10 — Export em massa (CSV / VCard / KML)

Status: ready-for-agent
Tipo: AFK
Prioridade: P2

## Parent

`.scratch/sokol-v2/PRD.md` — Fase C3. Já existe export ZIP do caso em `api/src/sokol/case_export.py` (FEAT-006) — estender esse módulo, não criar outro.

## What to build

Novos endpoints em `case_export.py`, todos com `require_case_member` + registro no `audit_log` (export é saída de evidência — sempre auditar):

- `GET /export/{case_id}/timeline.csv` — colunas: `ts_utc, ts_case_tz, kind, app, description, ref_table, ref_id`. Params opcionais `start_date`/`end_date` (mesmo padrão dos filtros da timeline). Streaming response para casos grandes (use `StreamingResponse` do FastAPI, não montar a string inteira em memória).
- `GET /export/{case_id}/contacts.vcf` — vCard 3.0, um VCARD por Contact (nome + telefones + e-mails).
- `GET /export/{case_id}/contacts.csv` — mesma base em CSV.
- `GET /export/{case_id}/locations.kml` — eventos `kind='location'` como Placemarks (nome = timestamp no fuso do caso, coordenadas lon,lat — atenção: KML usa `lon,lat`, PostGIS `ST_X`=lon/`ST_Y`=lat).

Frontend: botões de download na aba de export/relatórios existente (verifique onde o export ZIP aparece hoje e coloque ao lado).

## Before you start

- Leia `case_export.py` para seguir o padrão de autorização e nomeação de rota existente.
- Confirme com `\d events` como `geo` é armazenado e como o endpoint `/events/geo` extrai lat/lon (reuse a mesma expressão SQL).

## Acceptance criteria

- [ ] CSV de timeline com 100k eventos baixa sem estourar memória (streaming)
- [ ] `.vcf` importa sem erro no Google Contacts (validar estrutura VCARD 3.0)
- [ ] `.kml` abre no Google Earth com os pontos nas coordenadas corretas (lon,lat na ordem certa)
- [ ] Cada export gera linha no `audit_log`
- [ ] Não-membro do caso recebe 403 em todos os endpoints

## Blocked by

None — can start immediately
