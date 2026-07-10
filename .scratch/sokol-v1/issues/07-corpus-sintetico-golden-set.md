# 07 — Corpus sintético UFDR + golden set

Status: done
Tipo: AFK
Prioridade: P0

## Parent

`PLANO_NOVO.md` TODO-10; seção 11.

## What to build

Gerador reprodutível (seed fixo) em `synth/`: UFDR falso com `report.xml`, SQLite de Conversations com Messages em português, chamadas, contatos, localizações, histórico web, fotos com EXIF (algumas com placa/rosto), áudios curtos ou stubs com transcrição esperada, e gabarito JSON com os fatos verdadeiros. Golden set de 30–80 perguntas em `evals/` cobrindo: CPF, telefone, placa, data, rotina, vínculo, busca sem resposta, pergunta que exige RAG textual e pergunta que exige SQL estruturado. Nunca usar evidência real.

## Acceptance criteria

- [ ] Mesmo seed gera o mesmo corpus e o mesmo gabarito (teste de reprodutibilidade)
- [ ] UFDR sintético é um ZIP válido com `report.xml` e SQLites parseáveis
- [ ] Golden set em formato consumível pelo harness de evals com resposta esperada + Source esperada
- [ ] Gabarito cobre todas as categorias de pergunta listadas

## Blocked by

None - can start immediately
