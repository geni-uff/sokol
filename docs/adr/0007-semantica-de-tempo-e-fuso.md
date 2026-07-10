# Semântica de tempo: UTC canônico, fronteira do dia pelo fuso do caso

O tempo é tratado em três camadas fixas:

1. **Armazenamento** — `ts` é `timestamptz` (instante absoluto, UTC internamente). `tz_original` preserva o offset/zona que a fonte gravou.
2. **Consulta** — a fronteira de "dia" em ferramentas temporais (`query_timeline` etc.) usa um **fuso de referência explícito por request**, com default no **fuso do caso** (ex.: `America/Sao_Paulo`), **nunca UTC por default**. O Agent registra qual fuso usou.
3. **Citação/exibição** — a **Source** mostra sempre o horário de parede original (`tz_original`) com o offset explícito; nada é convertido silenciosamente.

Escolhemos o fuso do caso (não UTC) como default porque "o que aconteceu no dia 12/03?" para o investigador significa o dia de parede local; consultar em UTC produziria erros de ±1 dia e contagens enganosas perto da meia-noite. Escolhemos um fuso de caso uniforme (não o `tz_original` por-evento) para que "um dia" seja uma janela única e explicável, mesmo com devices que mudaram de fuso — a fidelidade ao device é preservada na exibição via `tz_original`.

## Consequences

- Todo endpoint/ferramenta temporal aceita um parâmetro de fuso, default = fuso do caso.
- O caso ganha um atributo de fuso de referência.
- Respostas do Agent e relatórios devem tornar o fuso de consulta explícito para evitar ambiguidade de ±1 dia.
