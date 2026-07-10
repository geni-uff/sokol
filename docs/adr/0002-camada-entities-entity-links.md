# Camada de entidades genérica (entities + entity_links)

A camada de entidades persistentes — telefones, contatos, identidades (pessoas reais), placas, e-mails — será modelada como uma tabela genérica de **entidades tipadas** (`entities`) mais uma tabela de **vínculos** (`entity_links`), em vez de tabelas concretas separadas por tipo. Essa é a base direta de `query_graph`, da tela de Grafo, das watchlists e da resolução de **Identity** a partir de múltiplas observações.

Isto **preenche uma lacuna do plano**: a seção 4 (contratos de banco) não define hoje nenhuma tabela de entidade/identidade, embora grafo, watchlists, pendências de face e o playbook `perfil-do-alvo` dependam dela. As migrations do TODO-04 devem incluir `entities` e `entity_links`.

## Considered Options

- **entities + entity_links genérico (escolhido)** — novos tipos de entidade não exigem migration; grafo é uniforme.
- **Tabelas concretas (contacts, identities, vehicles)** — mais type-safe por tipo, mas `query_graph` precisa conhecer cada tabela e cada novo tipo exige migration.
- **Sem entidade de 1ª classe** — entidades só como strings em `messages.sender`/`events.actor`; deixa grafo, watchlists e "perfil do alvo" frágeis, sem identidade resolvida.

## Consequences

- **Contact** (observação bruta de agenda) e **Identity** (pessoa real resolvida) são conceitos distintos; "Mesclar identidade" funde duas Identities e é decisão humana auditada.
- Validação de tipo passa a ser responsabilidade da aplicação, não do schema.
