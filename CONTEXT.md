# SOKOL

Plataforma forense local que transforma evidências digitais (UFDR, documentos, mídia) em dados estruturados, pesquisáveis e auditáveis, organizados por caso.

## Language

### Caso

**Case (Caso)**:
Container de topo da investigação; **todo** dado (Document, Artifact, Message, Event, Entity, Chunk, Job, Source) é escopado por `case_id`. Acesso é por **RBAC** por caso; busca cross-case é exceção auditada com justificativa.
_Avoid_: Projeto, investigação (como sinônimo de tabela), operação

**Admin (papel de caso)**:
Papel de caso com controle total: gerencia membros, autoriza cross-case, e detém a administração de sistema (modelos, GPU, backup/restore, tela de Operação).
_Avoid_: Dono, superusuário

**Analista (papel de caso)**:
Papel de caso operacional: ingere, busca, usa o **Agent**, cria **Bookmarks**, resolve **Pendências** (Indicator→Fact) e gera relatório/laudo.
_Avoid_: Usuário, operador, perito

**Leitor (papel de caso)**:
Papel de caso somente-leitura: busca, timeline e visualização de relatórios; não ingere, não resolve **Pendência**, não gera laudo.
_Avoid_: Convidado, visitante

### Evidência e procedência

**Document**:
Fonte ingerida de topo — a unidade que o operador importa (o arquivo `.ufdr` inteiro, um PDF ou DOCX avulso, uma imagem solta).
_Avoid_: Evidência (como sinônimo técnico), arquivo, upload

**Artifact**:
Unidade individual extraída de dentro de um **Document** (uma conversa, uma imagem, um membro SQLite do ZIP, um documento embutido). É o nível em que enriquecimento e status são rastreados.
_Avoid_: Evidência (como sinônimo técnico), item, anexo

**Media**:
Conteúdo binário deduplicado por SHA-256 e referenciado por hash. Vários **Artifacts** podem apontar para a mesma **Media**.
_Avoid_: Arquivo binário, blob, mídia bruta

### Timeline

**Event**:
Espinha universal da timeline — uma linha por ocorrência com timestamp, apontando para sua fonte via `ref_table`/`ref_id`. Unifica mensagens, chamadas, localizações, mídia e histórico web num único fluxo consultável por SQL.
_Avoid_: Ocorrência, registro de linha do tempo, atividade

**Message**:
Linha de comunicação estruturada (WhatsApp, SMS, etc.) com remetente, destinatário, app, chat e texto. Guarda o detalhe rico; sua projeção na timeline é um **Event** (`kind='message'`).
_Avoid_: Chat (que é o agrupamento), texto, comunicação

**Conversation**:
A thread forense que agrupa **Messages** de um mesmo diálogo (o que a coluna `chat_id` identifica). É dado investigado.
_Avoid_: Chat (reservar só como nome de coluna `chat_id`), diálogo, thread

**tz_original**:
O offset/zona que a **fonte** gravou para um **Event** (o horário de parede que o device mostrava). Preservado intacto; é o que a **Source** exibe.
_Avoid_: Timezone genérico, fuso do servidor

**Case timezone (fuso do caso)**:
O fuso de referência que define a fronteira de "dia" em consultas temporais (default do caso, ex.: `America/Sao_Paulo`; override explícito por request). Não é UTC por default.
_Avoid_: Fuso do servidor, UTC (como default de consulta)

### Agente e busca

**Agent**:
A feature de pergunta-e-resposta com IA (`POST /chat/agent`) — o operador pergunta, o Agent chama ferramentas SQL/busca e sintetiza com fontes. É ferramenta do operador, nunca a thread investigada.
_Avoid_: Chat, chat investigativo, assistente, bot

**Source**:
Uma citação que ancora uma afirmação (resposta do **Agent**, resultado de busca, trecho de relatório) num **registro de origem** com cadeia de custódia — a **Message**, a **Media** (por SHA-256) ou o **Document**+página+bbox. O **Event** pode acompanhar só como contexto de navegação.
_Avoid_: Fonte apontando para Event como referência canônica, referência, link

**Validator**:
Camada determinística que verifica, antes de entregar a resposta do **Agent**, que toda **Source** existe, pertence ao mesmo caso, e que datas/contagens citadas batem com o retorno das ferramentas.
_Avoid_: Verificador genérico, guardrail, checagem

**Chunk**:
Janela de **Conversation** (por chat, período e participantes, com `message_ids`) — a unidade de texto embedada para busca semântica. Carrega `embedding_model_id`; rastreável até as **Messages** de origem.
_Avoid_: Trecho, fragmento, passagem, Message (não é uma mensagem)

**Structured tool**:
Ferramenta do **Agent** que executa SQL parametrizado sobre views read-only (`query_timeline`, `query_messages`, `query_calls`, `query_geo`, `query_graph`) — autoritativa para fatos, datas e contagens. Distinta de `semantic_search`, que só recupera texto relevante e nunca responde contagem/agregação/filtro temporal.
_Avoid_: Tool genérica, função, RAG (semantic_search não é a fonte de fatos)

### Processo de entrada

**Import**:
Primeira fase — traz o arquivo do host/`inbox` para o `staging` controlado (cópia/hardlink + SHA-256 + snapshot). Mede bytes. Tem progresso próprio.
_Avoid_: Upload, ingestão (é fase distinta), cópia

**Ingestion**:
Fase estrutural — faz parse do **Document** e popula `messages`/`events`/`media`, incluindo `tsv` para busca exata/lexical. **Marco em que o caso vira consultável.** Tem progresso próprio.
_Avoid_: Importação, enriquecimento, processamento

**Enrichment**:
Fase assíncrona pós-**Ingestion** — jobs por **Artifact**: OCR/ASR/visão/face/placa **e** embedding vetorial (que habilita busca semântica/híbrida). O caso já está usável e vai ficando mais rico.
_Avoid_: Ingestão, indexação (é sub-parte), processamento

### Confiança e revisão humana

**Indicator (Indício)**:
Resultado automático **não confirmado** (face, placa, label) com score. Aparece em busca/exploração sempre rotulado, mas **nunca** é afirmado como fato pelo **Agent** nem entra em relatório como asserção.
_Avoid_: Fato, resultado, detecção (como se fosse verdade)

**Fact (Fato)**:
Afirmação com custódia: confirmada por humano (resolução de **Pendência**) ou determinística (SHA-256, timestamp de **Message**). É o único nível assertável pelo **Agent** e citável em relatório.
_Avoid_: Indício, resultado provável

**Pendência**:
Item na fila de revisão humana; é a transição auditada **Indicator → Fact** para faces, placas e identidades de baixa confiança.
_Avoid_: Tarefa, alerta, review genérico

### Investigação e saída

**Watchlist**:
Conjunto de seletores monitorados (telefone, placa, CPF) que rodam durante **Ingestion** e **Enrichment** para sinalizar ocorrências de interesse.
_Avoid_: Lista, filtro, alerta

**Hit**:
Uma ocorrência de um seletor de **Watchlist** casando com dado ingerido.
_Avoid_: Match genérico, resultado, achado

**Bookmark**:
Referência a uma evidência selecionada pelo operador e guardada para montar relatório.
_Avoid_: Favorito, marcador, seleção

**Playbook**:
Workflow versionado e mais determinístico que o **Agent** livre — plano fixo, com síntese LLM só no final (`triagem-ufdr`, `perfil-do-alvo`, `padrao-de-vida`...).
_Avoid_: Fluxo, script, receita, macro

**Job**:
Unidade de trabalho assíncrono na fila (**Ingestion**/**Enrichment**), retomável via `FOR UPDATE SKIP LOCKED`, com `attempts`/`heartbeat`/`pipeline_version`.
_Avoid_: Tarefa, processo, worker (worker é quem executa)

**Evidência**:
Termo guarda-chuva coloquial (usado na UI e em relatórios). **Não é uma entidade.** Em contexto técnico, deve ser substituído por **Document** ou **Artifact** conforme o alvo real.
_Avoid_: usar como nome de tabela, campo ou tipo

### Entidades e vínculos

**Entity**:
Nó tipado do grafo do caso. Tipos v1: `identity`, `phone`, `email`, `account` (conta de app/handle), `device` (aparelho apreendido), `plate` (placa), `face` (cluster facial), `contact`. Extraída/observada a partir de **Artifacts** e **Messages**.
_Avoid_: Nó, objeto, registro

**resolves_to**:
Vínculo tipado que liga uma observação (`phone`, `contact`, `face`, `account`) a uma **Identity**. É **não-destrutivo**: a observação permanece como entidade própria, preservando a proveniência da associação.
_Avoid_: Merge, dedupe, mesma-pessoa (sem aresta)

**Contact**:
Uma entrada de agenda **observada** dentro de um Document (nome + número como salvos no aparelho de alguém). É uma observação/evidência, não a pessoa real.
_Avoid_: Pessoa, identidade, número

**Identity**:
A **pessoa real do mundo** resolvida — o alvo ao qual vários **Contacts**, números e faces convergem depois de deduplicação/mesclagem. É o resultado de decisão (humana ou automática com limiar), não um dado bruto.
_Avoid_: Pessoa (como sinônimo de Contact), perfil, usuário

**Link (entity_link)**:
Aresta entre duas **Entities** (ex.: Identity↔phone, Contact↔phone, Identity↔face), com tipo e força.
_Avoid_: Vínculo genérico sem tipo, relação, edge solto

## Relationships

- Um **Document** contém um ou mais **Artifacts**
- Um **Artifact** referencia no máximo uma **Media** (por `media_hash`)
- Uma **Media** pode ser referenciada por vários **Artifacts** (dedupe por SHA-256)
- Todo **Document** e **Artifact** pertence a exatamente um caso (`case_id`)
- Toda ocorrência com timestamp (**Message**, chamada, localização, captura de **Media**, visita web) projeta **exatamente um Event**
- Um **Event** aponta para sua fonte por `ref_table`/`ref_id`; um **Message** é sua fonte quando `kind='message'`
- Um **Contact** é observado num **Artifact** e aponta para uma **Entity** do tipo telefone/e-mail
- Uma **Identity** agrega várias **Entities** (**Contacts**, números, faces) via arestas **resolves_to**, resolvendo a mesma pessoa real
- **Mesclar identidade** = fundir dois nós **Identity** em um, repontando arestas (não-destrutivo, auditado)

## Example dialogue

> **Dev:** "Quando ingerimos um `.ufdr`, criamos uma **Evidência**?"
> **Perito:** "Não use 'evidência' aqui. O `.ufdr` é um **Document**. Cada conversa, foto ou banco SQLite dentro dele vira um **Artifact**. O binário de cada foto, deduplicado por hash, é uma **Media**."

## Flagged ambiguities

- "Evidência" era usada para significar Document, Artifact e o `.ufdr` bruto — resolvido: é guarda-chuva coloquial, não entidade; mapeia para **Document** ou **Artifact** conforme o contexto.
- "pessoa/identidade" era usado de forma intercambiável nas faces — resolvido: **Contact** é a observação bruta, **Identity** é a pessoa real resolvida. "Mesclar identidade" opera sobre **Identities**.
- "chat" significava tanto a thread forense (`chat_id`) quanto a feature de IA — resolvido: **Conversation** para a thread investigada, **Agent** para a feature de IA. "chat" isolado é proibido em prosa.
- A seção 6.0 do `PLANO_NOVO.md` colocava "enriquecimento e indexação" dentro da **Ingestion**, contradizendo a promessa de consulta parcial precoce — resolvido: **Ingestion** inclui só `tsv`/busca exata; **Enrichment** cobre ML e embedding vetorial. Corrigir a frase da 6.0.
- Resolver **Pendência** (Indicator→Fact) e assinar laudo **não** são restritos a um papel de Perito — decisão deliberada: qualquer **Analista** pode, e toda decisão é auditada. Não reintroduzir um gate pericial achando que foi esquecimento.
