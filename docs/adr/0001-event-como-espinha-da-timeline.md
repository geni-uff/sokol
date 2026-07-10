# Event como espinha universal da timeline

Toda ocorrência com timestamp (Message, chamada, localização, captura de Media, visita web) projeta **exatamente um Event**, que aponta para sua fonte por `ref_table`/`ref_id`. Escolhemos essa projeção em vez de fazer `UNION` de `messages` + demais tabelas em tempo de consulta, porque mantém "o que aconteceu no dia X" respondível a partir de uma única tabela indexada por `events(case_id, ts)` — simplificando o `query_timeline` e a semântica de contagem do agente.

## Considered Options

- **Event como espinha (escolhido)** — inclui cada mensagem como `Event(kind='message')`.
- **events sem mensagens + UNION na consulta** — `events` menor, mas toda timeline e contagem passam a depender de UNION em duas fontes.
- **Event só para ocorrências curadas** — torna "evento" ambíguo (bruto vs curado).

## Consequences

- `events` fica grande (dezenas de milhares de linhas por device); depende dos índices já previstos.
- A ingestão precisa projetar um Event por linha de origem de forma idempotente (reingestão não pode duplicar).
