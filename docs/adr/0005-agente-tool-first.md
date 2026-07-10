# Agente é tool-first: SQL estruturado é autoritativo, não RAG

O **Agent** responde chamando **Structured tools** — funções que executam SQL parametrizado sobre views read-only (`query_timeline`, `query_messages`, `query_calls`, `query_geo`, `query_graph`). Essas ferramentas são a **única** fonte autoritativa de fatos, datas, contagens e agregações. `semantic_search` é apenas recuperação de texto relevante e **nunca** responde contagem, agregação ou filtro temporal. O LLM **nunca** escreve SQL livre: ele só escolhe ferramentas e parâmetros; o backend monta o SQL.

Registramos isto porque é uma deriva deliberada do caminho óbvio (um RAG-first responderia tudo por similaridade vetorial). Sem este ADR, um futuro dev "simplificaria" jogando perguntas temporais/numéricas no `semantic_search` e reintroduziria alucinação de contagem.

## Consequences

- Perguntas como "quantas mensagens em 12/03?" ou "o que aconteceu no dia X?" devem rotear para ferramentas SQL, não para busca vetorial.
- O **Validator** cruza contagens/datas citadas contra o retorno das ferramentas.
- Novas capacidades de consulta entram como novas Structured tools, não como prompt engineering sobre RAG.
