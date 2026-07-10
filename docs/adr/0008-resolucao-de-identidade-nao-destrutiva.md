# Resolução de identidade é não-destrutiva (resolves_to)

Observações de entidade (`phone`, `contact`, `face`, `account`) são resolvidas a uma **Identity** por uma aresta tipada `resolves_to` em `entity_links`, e **não** por fusão destrutiva de linhas. A observação permanece como entidade própria; mesclar duas Identities funde os nós `identity` repontando arestas, sem apagar as observações.

Escolhemos preservar proveniência porque cadeia de custódia exige que o perito exiba *por que* um número liga a uma pessoa, e possa **desfazer** uma associação errada sem perder o dado bruto. Dedupe destrutivo apagaria exatamente essa trilha.

Tipos de entidade v1: `identity`, `phone`, `email`, `account`, `device`, `plate`, `face`, `contact`.

## Consequences

- `entity_links` precisa de tipo de aresta (`resolves_to`, `communicated_with`, `contact_of`, `appears_in`, ...) e suporta reversão auditada.
- A UI de **Pendências**/Identidades opera sobre arestas, não sobre exclusão de linhas.
- Uma observação pode, por erro, apontar para a Identity errada; corrigir = mover a aresta, preservando histórico.
