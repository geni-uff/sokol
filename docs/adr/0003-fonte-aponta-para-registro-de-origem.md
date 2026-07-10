# Fonte (Source) aponta para o registro de origem, não para o Event

Uma **Source** (citação) resolve para o **registro de origem mais específico** com cadeia de custódia — a Message, a Media (por SHA-256) ou o Document + página + bbox — e não para o Event. O Event, sendo dado derivado (ver ADR-0001), pode acompanhar apenas como contexto de navegação (`event_id` opcional). Isso garante que toda afirmação em relatório ou resposta do Agent seja rastreável até o dado com custódia, resistindo a contestação pericial.

Contradiz o exemplo atual da seção 5.7 do `PLANO_NOVO.md`, que cita `ref_table: "events"` como fonte primária — esse exemplo deve ser corrigido para citar a origem.

## Consequences

- O contrato de `sources` passa a ser `{origin_ref_table, origin_ref_id, event_id?, label}`.
- O **Validator** valida a existência e o `case_id` do registro de origem, não do Event.
