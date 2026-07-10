# Indício (Indicator) vs Fato (Fact): Pendência é o portão

Resultados automáticos de enriquecimento (face, placa, label de visão) não confirmados são **Indicators** — visíveis em busca e exploração, sempre rotulados com score, mas **nunca** afirmáveis como fato pelo Agent nem citáveis como asserção em relatório. Um resultado só vira **Fact** — assertável e report-grade — quando confirmado por humano na resolução de uma **Pendência**, ou quando é determinístico (SHA-256, timestamp de Message). A **Pendência** é a transição auditada Indicator → Fact.

Escolhemos isso em vez de aceitar resultados acima de um limiar como fato automático, porque cadeia de custódia forense exige que a máquina não decida sozinha o que é periciado. Preserva a regra do plano: "resultado incerto não entra como fato validado sem ação humana".

## Consequences

- Todo resultado de face/placa/visão carrega um estado de confirmação, não só um score.
- O prompt e o **Validator** do Agent devem impedir que um Indicator seja redigido como afirmação categórica ("o veículo é X"); no máximo "há indício de X, não confirmado".
- Relatórios filtram Indicators de seções de asserção factual.
