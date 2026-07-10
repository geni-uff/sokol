# Estrutura UFDR — Referência Completa para SOKOL

> Documento de referência técnica para implementação do parser UFDR.
> Baseado na análise de 5 UFDRs reais (2 Apple, 2 Google, 1 Apple iCloud).
> Ferramenta de extração: Cellebrite UFED Physical Analyzer v10.7.1.5013.
> Data da análise: 2026-07-08.

---

## 1. O que é um UFDR

UFDR (**Universal Forensic Data Report**) é o formato de saída do Cellebrite
Physical Analyzer. Ele contém toda a evidência extraída de um dispositivo ou
conta, organizada em:

1. Um arquivo **XML estruturado** (`report.xml`) com metadados, arquivos
   indexados e dados decodificados.
2. Uma pasta **`files/`** com os binários extraídos organizados por categoria.
3. Opcionalmente, uma pasta **`DbData/`** com banco de dados e metadados de caso.
4. Opcionalmente, um **`settings.json`** com configurações de exibição.

---

## 2. UFDR é um ZIP

**Confirmado:** todo arquivo `.ufdr` é um **Zip archive** (compression method=
`store` ou `deflate`). A extensão `.ufdr` é apenas uma renomeação de `.zip`.

### 2.1 Evidência

```
$ file sample.ufdr
Zip archive data, at least v4.5 to extract, compression method=store
```

### 2.2 Comparação .ufdr vs .ZIP

Nos testes, os arquivos `.ZIP` e `.ufdr` do mesmo caso são **byte-a-byte
idênticos** (MD5 confirma). São três cópias do mesmo conteúdo:

| Cópia | Localização |
|---|---|
| `.ZIP` | Pasta pai (ex: `PA10_Google/`) |
| `.ufdr` | Dentro da pasta extraída pelo Cellebrite (ex: `2025-11-03.17-15-20/google/`) |
| Pasta extraída | Mesmo conteúdo do ZIP, descompactado pelo PA |

### 2.3 Implicação para SOKOL

O parser deve aceitar `.ufdr` como entrada e tratar como **qualquer ZIP**.
Não há necessidade de converter extensão. A estrutura interna é padronizada.

---

## 3. Estrutura de Diretórios Interna

### 3.1 Layout padrão (Apple iCloud Backup)

```
report.xml                          # XML principal (~500MB, ~8M linhas)
settings.json                       # Configurações de exibição (opcional)
ThumbnailCache.s3db                 # Cache de thumbnails SQLite (opcional)
email/                              # Anexos de email (opcional)
  075de89f155163989a3a.png
  Apple_Support_Appt.ics
  Fatura_012022_DANILO_*.PDF
  IMG_3156.jpg
  Nubank_2021-12-21.pdf
DbData/                             # Banco de dados do caso (opcional)
  database.db                       # PostgreSQL custom dump (NÃO SQLite)
  database.json                     # Metadados do caso
files/                              # Binários extraídos
  Archives/                         # Arquivos compactados (WhatsApp, iCloud)
  Audio/                            # Áudios (.opus, .m4a, .mp3, .aac)
  Configuration/                    # Arquivos de configuração (plist, etc.)
  Database/                         # Bancos de dados (.sqlite, .db, .realm)
  Document/                         # Documentos (.pdf, .xlsx, .docx)
  Exchange/                         # Emails (.eml)
  Image/                            # Imagens (.jpg, .png, .webp, .heic, .thumb)
  Text/                             # Texto (.xml, .txt, .csv, .log)
  Uncategorized/                    # Diversos (.vcf, .bnk, .pak, .iwa, .tml)
  Video/                            # Vídeos (.mp4, .mov)
```

### 3.2 Layout padrão (Google Warrant Return)

```
report.xml                          # XML principal (~89MB, ~1.7M linhas)
settings.json                       # Configurações de exibição (opcional)
DbData/                             # Banco de dados do caso (opcional)
  database.db                       # PostgreSQL custom dump (NÃO SQLite)
  database.json                     # Metadados do caso
files/                              # Binários extraídos
  Archives/                         # Google Takeout ZIPs
  Image/                            # Imagens extraídas dos ZIPs
  Text/                             # HTML, TXT, CSV, ExportSummary
  Uncategorized/                    # JSON (LocationHistory, SemanticLocation)
```

### 3.3 Pasta de extração do Cellebrite

O Cellebrite UFED cria uma pasta com timestamp:

```
{data}.{hora}.{minuto}.{segundo}/
  {device_name}/
    {device_name}_{date}_Relatório.ufdr    # O arquivo UFDR
    CellebriteReader.exe                     # Viewer Cellebrite (Windows)
    AccountPackage/                          # Apple only
      AccountPackage.ucae                    # Pacote de conta Apple
      What to do with the Account Package.pdf
```

---

## 4. report.xml — Esquema Completo

### 4.1 Namespace e raiz

```xml
<project xmlns="http://pa.cellebrite.com/report/2.0"
         id="UUID"
         name="string"
         reportVersion="8.5"
         licenseID="string"
         containsGarbage="True|False"
         extractionType="Legacy|Full|..."
         NodeCount="int"
         ModelCount="int">
```

**Atributos do `<project>`:**

| Atributo | Tipo | Descrição |
|---|---|---|
| `id` | UUID | Identificador único do projeto |
| `name` | String | Nome do projeto (ex: "google", "apple") |
| `reportVersion` | Float | Versão do formato UFDR (8.5 observado) |
| `licenseID` | String | ID da licença Cellebrite |
| `containsGarbage` | Bool | Se contém dados deletados/garbage |
| `extractionType` | String | Tipo de extração (Legacy, Full, etc.) |
| `NodeCount` | Int | Total de nós de arquivo |
| `ModelCount` | Int | Total de modelos decodificados |

### 4.2 Seções do XML (em ordem)

#### 4.2.1 `<sourceExtractions>`

```xml
<sourceExtractions>
  <extractionInfo id="0" name="Legacy" type="Legacy"
                  deviceName="Google Warrant Return"
                  fullName="Google Warrant Return"
                  index="0"
                  IsPartialData="False"
                  IsStoppedByUser="False"
                  IsTriageExtraction="False"
                  IsSelectiveExtraction="False" />
</sourceExtractions>
```

**Atributos de `<extractionInfo>`:**

| Atributo | Descrição |
|---|---|
| `id` | Índice da extração |
| `name` | Nome da extração |
| `type` | Tipo (Legacy, Full, etc.) |
| `deviceName` | Nome do dispositivo/fonte |
| `fullName` | Nome completo |
| `IsPartialData` | Se é extração parcial |
| `IsStoppedByUser` | Se foi interrompida pelo usuário |
| `IsTriageExtraction` | Se é extração de triagem |
| `IsSelectiveExtraction` | Se é extração seletiva |

#### 4.2.2 `<caseInformation>`

```xml
<caseInformation>
  <field name="Nome do examinador" isSystem="True" isRequired="False"
         fieldType="ExaminerName" multipleLines="False">
    TESTE
  </field>
  <field name="Nome do caso" isSystem="True" isRequired="False"
         fieldType="CaseName" multipleLines="False">
    google
  </field>
</caseInformation>
```

**Campos do caso (Português/pt-BR):**

| Nome do Campo | `fieldType` | Descrição |
|---|---|---|
| Nome do examinador | `ExaminerName` | Nome do perito examinador |
| Nome do caso | `CaseName` | Nome/identificação do caso |
| Localização | `Location` | Localização do exame |
| Número do caso | `CaseNumber` | Número do mandado/processo |
| Número de evidência | `EvidenceNumber` | Número da evidência |
| Departamento | `Department` | Departamento responsável |
| Organização | `Organization` | Organização/autoria |
| Investigador | `Investigator` | Investigador responsável |
| Tipo de crime | `CrimeType` | Classificação do crime |
| Anotações | `Notes` | Observações livres |

#### 4.2.3 `<metadata>`

Duas seções de metadados:

**"Additional Fields":**

```xml
<metadata>
  <item name="DeviceInfoCreationTime" systemtype="System.String">
    03/11/2025 17:15:40
  </item>
  <item name="UFED_PA_Version" systemtype="System.String">
    10.7.1.5013
  </item>
  <item name="UfdrLanguage" systemtype="System.String">
    pt-BR
  </item>
  <item name="SourceProjectId" systemtype="System.String">
    aa720bbc-1113-46ad-aca2-89e505aa5247
  </item>
</metadata>
```

**"Extraction Data":**

```xml
<metadata>
  <item name="DeviceInfoExtractionDecodingDateTime" systemtype="System.String">
    03/11/2025 17:07:41
  </item>
  <item name="DeviceInfoSelectedDeviceName" systemtype="System.String">
    Google Warrant Return
  </item>
  <item name="DeviceInfoSelectedManufacturer" systemtype="System.String">
    Google
  </item>
  <item name="Time zone settings (ID)" systemtype="System.String">
    _America/Sao_Paulo
  </item>
</metadata>
```

**Metadados chave para SOKOL:**

| Chave | Descrição | Uso no SOKOL |
|---|---|---|
| `DeviceInfoCreationTime` | Data de criação do relatório | `Document.created_at` |
| `UFED_PA_Version` | Versão do PA | Auditoria |
| `UfdrLanguage` | Idioma do relatório | Normalização |
| `DeviceInfoSelectedDeviceName` | Nome do dispositivo | `Document.title` |
| `DeviceInfoSelectedManufacturer` | Fabricante (Apple/Google) | Tipo de extração |
| `Time zone settings (ID)` | Fuso horário | `Case.reference_timezone` |

#### 4.2.4 `<images>`

Referência à imagem de origem (disco/extração):

```xml
<images>
  <image key="Pasta" path="3. DESCOMPACTADO" size="2972319447"
         type="File" verify="Verified" extractionId="0" />
</images>
```

#### 4.2.5 `<HashSetsInfo>`

Informações de hash sets (MD5/SHA-256) para identificação de arquivos conhecidos.
Pode estar vazio ou conter referências a hash sets de inteligência.

#### 4.2.6 `<MalwareScanner>`

```xml
<MalwareScanner ScanPerformed="False" />
```

Status do scanner de malware. Raramente ativo em extrações forenses.

#### 4.2.7 `<taggedFiles>` — SEÇÃO CRÍTICA

Esta é a seção mais importante para o SOKOL. Contém **todos os arquivos**
extraídos com seus metadados completos.

**Estrutura de cada `<file>`:**

```xml
<file fs="472538-ICLOUDDRIVE"
      fsid="9795c740-d66d-46f1-b978-485e9ba24200"
      path="/17538487441/472538/daniloidelfonso@icloud.com-472538/iclouddrive/..."
      name="Document.tar"
      size="11313664"
      id="dc837e8e-63e2-4491-8696-e2397c9c5efe"
      extractionId="1"
      deleted="Intact"
      embedded="false"
      isrelated="False"
      isNative="True"
      source_index="934">

  <!-- Timestamps de acesso -->
  <accessInfo>
    <timestamp name="ModifyTime" format="TimeStampKnown"
               formattedTimestamp="2021-10-09T09:54:22+00:00">
      2021-10-09T09:54:22.000+00:00
    </timestamp>
  </accessInfo>

  <!-- Metadados do arquivo -->
  <metadata section="File">
    <item name="Local Path" systemtype="System.String">
      <![CDATA[files\Archives\Document.tar]]>
    </item>
    <item name="SHA256" systemtype="System.String">
      <![CDATA[e4e2f7596ff8dffd70e409806f97848fe498d03bfb45a04b36bfb717b14f43f1]]>
    </item>
    <item name="MD5" systemtype="System.String">
      <![CDATA[24fc0ce0091ebf40f969c5c82438584b]]>
    </item>
    <item name="Tags" systemtype="System.String">
      <![CDATA[Archives]]>
    </item>
  </metadata>

  <!-- Metadados do sistema de arquivos -->
  <metadata section="MetaData">
    <item name="CoreFileSystemFileSystemNodeChangeTime" ... />
    <item name="CoreFileSystemFileSystemNodeCreationTime" ... />
    <item name="CoreFileSystemFileSystemNodeDeletedTime" ... />
    <item name="CoreFileSystemFileSystemNodeFileChunks" ... />
    <item name="CoreFileSystemFileSystemNodeFileDataOffsetName" ... />
    <item name="CoreFileSystemFileSystemNodeFilePath" ... />
    <item name="CoreFileSystemFileSystemNodeLastAccessTime" ... />
    <item name="CoreFileSystemFileSystemNodeModifyTime" ... />
    <item name="GlobalNumberOfFiles" ... />
  </metadata>

  <!-- Metadados EXIF (apenas para Images com Tag) -->
  <metadata section="MetaData" group="EXIF">
    <item name="ExifEnumDateTimeOriginal" ... />
    <item name="ExifEnumMake" ... />
    <item name="ExifEnumModel" ... />
    ...
  </metadata>

  <!-- Hash sets (opcional) -->
  <HashSetsInfo>
    <Hash subCategory="" sevirity="">
      <![CDATA[0ad6ffb3-95b3-4eb2-a59d-9ce124fb418c]]>
    </Hash>
  </HashSetsInfo>
</file>
```

**Atributos de `<file>`:**

| Atributo | Tipo | Descrição | Uso no SOKOL |
|---|---|---|---|
| `fs` | String | Nome do filesystem de origem | Rastreabilidade |
| `fsid` | UUID | ID do filesystem | Rastreabilidade |
| `path` | String | Caminho completo no FS original | `Artifact.source_member` |
| `name` | String | Nome do arquivo | `Artifact.source_member` |
| `size` | Int | Tamanho em bytes | `Artifact.size_bytes` |
| `id` | UUID | ID único do arquivo | `Artifact.id` |
| `extractionId` | Int | Índice da extração | Rastreabilidade |
| `deleted` | String | Estado: `Intact`, `Deleted`, etc. | `Artifact.meta.deleted` |
| `embedded` | Bool | Se foi extraído de dentro de um ZIP | `Artifact.meta.embedded` |
| `isrelated` | Bool | Se está relacionado a outro arquivo | `Artifact.meta.isrelated` |
| `isNative` | Bool | Se é arquivo nativo do dispositivo | `Artifact.meta.is_native` |
| `source_index` | Int | Índice na fonte original | Rastreabilidade |

**Timestamps disponíveis (`<accessInfo>`):**

| Nome | Descrição |
|---|---|
| `CreationTime` | Data de criação |
| `ModifyTime` | Data de modificação |
| `AccessTime` | Último acesso |
| `DeletedTime` | Data de deleção (se disponível) |
| `ChangedTime` | Data de mudança |

**Itens de metadados do arquivo (`<metadata section="File">`):**

| Nome | Descrição | Uso no SOKOL |
|---|---|---|
| `Local Path` | Caminho relativo no `files/` | Mapeamento para binário |
| `SHA256` | Hash SHA-256 | `Artifact.media_hash` |
| `MD5` | Hash MD5 | Auditoria |
| `Tags` | Categoria do arquivo | `Artifact.kind` |

**Tags observadas (Cellebrite):**

| Tag | Descrição | Correspondência SOKOL |
|---|---|---|
| `Image` | Imagens (JPG, PNG, HEIC, etc.) | `kind=image` |
| `Audio` | Áudios (OPUS, M4A, MP3, AAC) | `kind=audio` |
| `Video` | Vídeos (MP4, MOV) | `kind=video` |
| `Text` | Arquivos de texto | `kind=document` |
| `Document` | Documentos (PDF, DOCX, XLSX) | `kind=document` |
| `Database` | Bancos de dados | `kind=database` |
| `Archives` | Arquivos compactados | `kind=archive` |
| `Configuration` | Configurações | `kind=config` |
| `Exchange` | Emails (EML) | `kind=email` |
| `Uncategorized` | Sem categoria | `kind=other` |
| `Shortcut` | Atalhos iOS | `kind=config` |

**Metadados EXIF (para imagens com Tag=Image):**

Grupo `EXIF`:
- `ExifEnumDateTimeOriginal` — Data/hora da captura
- `ExifEnumMake` — Fabricante da câmera
- `ExifEnumModel` — Modelo da câmera
- `ExifEnumFNumber` — Abertura
- `ExifEnumExposureTime` — Velocidade do obturador
- `ExifEnumISOSpeedRatings` — ISO
- `ExifEnumFocalLength` — Distância focal
- `ExifEnumOrientation` — Orientação
- `ExifEnumFlash` — Flash
- `ExifEnumPixelXDimension` — Largura em pixels
- `ExifEnumPixelYDimension` — Altura em pixels
- `ExifEnumSoftware` — Software used

Grupo `File Metadata`:
- `EXIFCameraMaker` — Fabricante
- `EXIFCameraModel` — Modelo
- `EXIFCaptureTime` — Data de captura
- `MetaDataPixelResolution` — Resolução (ex: "552x828")

#### 4.2.8 `<decodedData>` — SEÇÃO CRÍTICA

Contém todos os modelos forenses decodificados pelo Cellebrite. Cada modelo
representa um tipo de dado estruturado extraído do dispositivo.

**Estrutura:**

```xml
<decodedData>
  <modelType type="Chat">
    <model type="Chat" id="UUID" deleted_state="Intact"
            decoding_confidence="High" isrelated="False"
            source_index="134077" extractionId="0">

      <field name="Source" type="String">
        <value type="String"><![CDATA[WhatsApp]]></value>
      </field>

      <field name="Id" type="String">
        <value type="String"><![CDATA[5521965694862@status]]></value>
      </field>

      <field name="StartTime" type="TimeStamp">
        <value type="TimeStamp" format="TimeStampKnown"
               formattedTimestamp="2021-05-21T02:38:43+00:00">
          2021-05-21T02:38:43.000+00:00
        </value>
      </field>

      <multiModelField name="Participants" type="Party">
        <model type="Party" id="UUID" ...>
          <field name="Identifier" type="String">
            <value type="String"><![CDATA[5521965694862@s.whatsapp.net]]></value>
          </field>
          <field name="Role" type="PartyRole">
            <value type="PartyRole"><![CDATA[General]]></value>
          </field>
          <field name="Name" type="String">
            <value type="String"><![CDATA[Diniz]]></value>
          </field>
        </model>
      </multiModelField>
    </model>
  </modelType>
</decodedData>
```

**Atributos de `<model>`:**

| Atributo | Tipo | Descrição |
|---|---|---|
| `type` | String | Tipo do modelo |
| `id` | UUID | ID único |
| `deleted_state` | String | `Intact`, `Deleted`, `Unknown` |
| `decoding_confidence` | String | `High`, `Medium`, `Low` |
| `isrelated` | Bool | Relacionado a outro modelo |
| `source_index` | Int | Índice na fonte |
| `extractionId` | Int | Índice da extração |
| `iscarved` | Bool | Se foi recuperado de disco (carved) |

**Tipos de campo:**

| Tipo | Descrição | Formato do valor |
|---|---|---|
| `String` | Texto | `<![CDATA[...]]>` |
| `TimeStamp` | Data/hora | ISO 8601 com offset |
| `Int32` | Inteiro 32 bits | Numérico |
| `UInt32` | Inteiro sem sinal 32 bits | Numérico |
| `Double` | ponto flutuante | Numérico |
| `Boolean` | Lógico | `True`/`False` |
| `TimeSpan` | Duração | `HH:MM:SS.fffffff` |
| Enumerados | Valores fixos | Texto (ex: `Outgoing`) |

**Valores vazios:**

Campos vazios usam `<empty />` em vez de `<value>`:
```xml
<field name="Name" type="String">
  <empty />
</field>
```

O parser deve tratar `<empty />` como string vazia `""`.

**Timestamps com atributo `formattedTimestamp`:**

Campos `TimeStamp` podem ter o valor no atributo `formattedTimestamp`:
```xml
<field name="TimeStamp" type="TimeStamp">
  <value type="TimeStamp" format="DateTimeOnly"
         formattedTimestamp="2024-10-29T17:17:48+00:00">
    2024-10-29T17:17:48.838
  </value>
</field>
```

O parser deve usar `formattedTimestamp` quando disponível, pois contém o
timezone offset completo.

### 4.3 ModelTypes decodificados

#### Apple (iCloud Backup) — 15 modelTypes

| modelType | Contagem | Descrição | Campos principais |
|---|---|---|---|
| `Chat` | ~158.000 | Conversas (WhatsApp, etc.) | Source, Id, StartTime, LastActivity, Participants |
| `Contact` | ~9.300 | Contatos | Type, Domain, Value, Category |
| `LogEntry` | ~7.500 | Logs do sistema | Application, Body, Severity, TimeStamp |
| `DeviceConnectivity` | ~2.100 | Conexões de rede | ConnectivityMethod, DeviceType, Key |
| `Email` | ~2.700 | Emails | Account, Folder, From, TimeStamp, Priority |
| `Call` | ~725 | Chamadas | Direction, Duration, Status, TimeStamp, Parties |
| `Cookie` | ~213 | Cookies de browser | Domain, Name, Value, Expiry |
| `CalendarEntry` | ~67 | Eventos de calendário | Subject, StartDate, EndDate, Status |
| `Location` | ~285 | Localizações GPS | Latitude, Longitude, TimeStamp, Confidence |
| `UserAccount` | ~27 | Contas de usuário | Username, ServiceType, ServiceIdentifier |
| `SearchedItem` | ~30 | Itens pesquisados | Value, TimeStamp, Origin |
| `WebBookmark` | ~13 | Favoritos web | Title, Url, VisitCount |
| `InstalledApplication` | ~154 | Apps instalados | Identifier, DecodingStatus |
| `DeviceInfoEntry` | ~13 | Info do dispositivo | EntryName, EntryValue |
| `Note` | ~4 | Notas | Body, Source |

#### Google (Warrant Return) — 1 modelType

| modelType | Contagem | Descrição |
|---|---|---|
| `Location` | ~40.200 | Localizações GPS (Google Timeline) |

**Nota:** Google extractions contêm apenas dados de localização decodificados.
Outros dados (Calendar, MyActivity, etc.) estão nos arquivos ZIP/CSV/JSON em
`files/`.

---

## 5. settings.json

```json
{
  "Version": "1.0",
  "ShowAllItems": true,
  "MergeSingleProject": false,
  "SingleProjectRemoveDuplicates": false,
  "TimeStampCreated": true,
  "TimeStampCaptured": true,
  "TimeStampModified": true,
  "TimeStampAccessed": true,
  "TimeStampDeleted": true,
  "TimeStampChanged": true,
  "DataFileImage": true,
  "DataFileAudio": true,
  "DataFileVideo": true,
  "ShowActivitiesModel": true,
  "ShowAppGenieModels": true,
  "ShowDeviceEventsModel": true
}
```

Controle de quais tipos de dados e timestamps são exibidos no viewer do
Cellebrite. **Não é essencial para parsing**, mas pode indicar quais dados
estão disponíveis.

---

## 6. DbData/ — Banco de Dados do Caso

### 6.1 database.db — PostgreSQL Custom Dump (191 tabelas!)

**Importante:** `database.db` é um **PostgreSQL custom dump** (magic bytes
`PGDMP`), não um SQLite.

```
Header: PGDMP001\016
PostgreSQL version: 14.2
Database name: case_{UUID}
Dump version: 1.14-0
TOC Entries: 1190
Format: CUSTOM
```

**Descoberta:** O dump contém um schema relacional **completo e rico** com
**191 tabelas únicas**, **171 índices**, **292 constraints** e **100 foreign keys**.
É a fonte de dados **mais estruturada** disponível no UFDR.

Para acessar: `pg_restore --list database.db` (lista objetos) ou restaurar em
PostgreSQL temporário para queries diretas.

#### 6.1.1 Schema do banco

O banco usa um **schema por dispositivo**: `device_{DeviceId}`.

Exemplo: `device_aa720bbc-1113-46ad-aca2-89e505aa5247`

#### 6.1.2 Tabelas com dados (Google Warrant Return — 40.199 localizações)

| Tabela | Linhas | Descrição |
|---|---|---|
| **SourceInfoNodes** | 40.662 | Vínculo SourceInfo ↔ Node |
| **GeneralData** | 40.637 | Dados gerais (tipo, timeline, localização) |
| **SourceInfos** | 40.636 | Entidades fonte (Id, ImageId, NodeId) |
| **LocationsItems** | 40.382 | Itens de localização |
| **Coordinates** | 40.382 | Coordenadas GPS (Latitude, Longitude) |
| **Locations** | 40.199 | Localizações completas |
| **TimeStampFields** | 39.731 | Timestamps de cada entidade |
| **TimeLines** | 39.652 | Linha do tempo unificada |
| **NodesMetaData** | 15.825 | Metadados de nós (chave-valor) |
| **FilePageContent** | 1.097 | Conteúdo textual por página |
| **Nodes** | 464 | Todos os arquivos/nós extraídos |
| **GlobalSearch** | 438 | Índice de busca global |
| **ReportPaths** | 436 | Caminhos de relatório |

**Todas as outras tabelas estão vazias** (0 linhas) nesta extração Google.

#### 6.1.3 Schema das tabelas principais

**`Nodes`** — Todos os arquivos extraídos (464 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único do nó |
| `Type` | Integer | Tipo do nó (2=arquivo, 10=extraído de ZIP) |
| `Name` | Text | Nome do arquivo |
| `FileExtension` | Text | Extensão |
| `FullPath` | Text | Caminho completo no FS de origem |
| `FileSize` | BigInt | Tamanho em bytes |
| `Sha256` | Text | Hash SHA-256 |
| `Md5` | Text | Hash MD5 |
| `Tag` | Text | Categoria (Image, Text, Archives, Uncategorized) |
| `CreationTime` | Timestamp | Data de criação |
| `ModifyTime` | Timestamp | Data de modificação |
| `AccessTime` | Timestamp | Último acesso |
| `DeletedTime` | Timestamp | Data de deleção |
| `IsCarved` | Boolean | Se foi recuperado de disco |
| `FileSystemId` | UUID | ID do filesystem |
| `ParentId` | UUID | Nó pai |
| `ImageFormat` | Text | Formato da imagem (Jpeg, etc.) |
| `Thumbnail` | Bytea | Thumbnail em bytes |
| `LocationPositionId` | UUID | Vínculo com Coordinates |
| `LocationTimeStamp` | Timestamp | Timestamp da localização |
| `IsAttachment` | Boolean | Se é anexo |
| `Labels` | Integer | Labels/classificações |
| `ParserTags` | Array | Tags do parser |
| `SourceModelsName` | Array | Modelos de origem |
| `SourceApplicationName` | Text | App de origem |

**`Locations`** — Localizações GPS (40.199 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único |
| `PositionId` | UUID | FK → Coordinates |
| `AddressId` | UUID | FK → endereço |
| `TimeStamp` | Timestamp | Data/hora da localização |
| `Name` | Text | Nome do local |
| `Description` | Text | Descrição |
| `Type` | Text | Tipo |
| `Confidence` | Integer | Confiança (0-100) |
| `GpsHorizontalAccuracy` | Double | Precisão horizontal GPS |
| `PositionAddress` | Text | Endereço |
| `Origin` | Integer | Origem |
| `DeviceLocationAffiliation` | Integer | Afiliação ao dispositivo |
| `AccountLocationAffiliation` | Integer | Afiliação à conta |
| `IsCarved` | Boolean | Se foi carved |
| `DecodingConfidence` | Integer | Confiança do decoding |
| `DedupHash` | Text | Hash de deduplicação |
| `Source` | Text | Fonte |
| `ServiceIdentifier` | Text | Serviço de origem |

**`Coordinates`** — Coordenadas GPS puras (40.382 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único |
| `Latitude` | Double | Latitude em graus decimais |
| `Longitude` | Double | Longitude em graus decimais |

**`TimeLines`** — Linha do tempo unificada (39.652 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único |
| `TimeStamp` | Timestamp | Data/hora do evento |
| `Source` | Text | Fonte/app |
| `Description` | Text | Descrição do evento |
| `Deleted` | Smallint | Estado de deleção |

**`GeneralData`** — Dados gerais com classificações (40.637 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único |
| `Type` | Text | Tipo (Image, Text, Archives, Uncategorized) |
| `MarkForReport` | Boolean | Marcado para relatório |
| `IsTimeline` | Boolean | Aparece na timeline |
| `IsLocation` | Boolean | Tem localização |
| `RelatedToId` | UUID | Entidade relacionada |
| `RelatedItemsCount` | Integer | Itens relacionados |

**`TimeStampFields`** — Timestamps por entidade (39.731 linhas):

| Coluna | Tipo | Descrição |
|---|---|---|
| `Id` | UUID | ID único |
| `TimeStamp` | Timestamp | Data/hora |
| `ManuallyDecoded` | Boolean | Decodificado manualmente |
| `IsCarved` | Boolean | Se foi carved |
| `DecodingConfidence` | Integer | Confiança |
| `SourceExtraction` | UUID | Extração de origem |

#### 6.1.4 Tabelas disponibles mas vazias (Google)

Todas as tabelas abaixo existem no schema mas contêm 0 linhas nesta extração
Google. Elas seriam populadas em extrações Apple/iCloud mais ricas:

**Comunicação:** Chats, Chats_Participants, ChatActivities, ChatActivities_Participant,
Calls, Calls_Parties, InstantMessages, InstantMessages_From/To/Cc/Bcc,
EmbeddedInstantMessages, InstantMessageExtraDatas

**Contatos:** Contacts, ContactEntries, ContactPhotos

**Email:** Emails, Emails_From/To/Cc/Bcc, EmailsTo

**Social:** SocialMediaActivities, SocialMediaActivities_Author/TaggedParties,
Reactions, Reactions_Actor

**Apps/Device:** InstalledApplications, ApplicationUsages, AppsUsageLogs,
DeviceConnectivities, DeviceEvents, DeviceIdentifiers, DeviceInfoEntries,
BluetoothDevices, WirelessNetworks, PeripherialDevices

**Mídia:** Images, Recordings, SpeechToText, MediaAttributes,
MediaClassificationResults, Thumbnails

**Financeiro:** FinancialAccounts, FinancialAssets, CreditCards, Purchases,
TransferOfFunds, Prices, LineItems, Products

**Browser/Web:** Cookies, VisitedPages, WebBookmarks, FileDownloads,
FileUploads, SharedFiles

**Localização:** AggregatedLocations, Journeys, CellTowers, Maps,
StreetAddressess, LocationAggregationByCategory

**Segurança:** Passwords, Autofills, HexBookmarks, MalwareInfos,
RiskExposureInfos, RiskExposureCategoryInfos

**Sistema:** LogEntrys, OSLogEntries, PoweringEvents, Notes,
Notifications, GlobalSearch, SearchedItems

**Forense:** CarvedStrings, CryptoArtifacts, ExternalCryptoRequests,
ProviderCryptoAnalysisResults, HashDbHitsData, WatchlistData

#### 6.1.5 O que o PostgreSQL tem que o XML e os arquivos NÃO têm

| Dado | PostgreSQL | XML report | files/ |
|---|---|---|---|
| Schema relacional completo com FKs | ✅ | ❌ | ❌ |
| Join entre Locations ↔ Coordinates ↔ TimeLines | ✅ | ❌ | ❌ |
| Classificação IsTimeline/IsLocation por arquivo | ✅ | ❌ | ❌ |
| GeneralData com MarkForReport | ✅ | ❌ | ❌ |
| TimeStampFields isolados por entidade | ✅ | Parcial | ❌ |
| Nodes com ParentId (hierarquia de arquivos) | ✅ | Parcial | ❌ |
| NodesMetaData como chave-valor genérico | ✅ | ❌ | ❌ |
| FilePageContent (texto por página) | ✅ | ❌ | ❌ |
| GlobalSearch (índice de busca) | ✅ | ❌ | ❌ |
| Thumbnails como bytea | ✅ | ❌ | ❌ |
| SourceInfoNodes (vínculo arquivo→modelo) | ✅ | ❌ | ❌ |
| DedupHash por entidade | ✅ | ❌ | ❌ |
| Dados de Chats/Calls/Contacts/Emails | ❌ (Google) | ✅ (Apple) | ❌ |
| Binários de mídia | ❌ | ❌ | ✅ |
| Conteúdo textual de HTML/TXT | ❌ | ❌ | ✅ |

#### 6.1.6 Decisão para o SOKOL

O `database.db` é uma fonte de dados **extremamente valiosa** que complementa
o `report.xml`:

1. **Para extrações Google:** O PostgreSQL é a **única fonte** de dados
   estruturados de localização. O XML contém os mesmos dados mas em formato
   menos consultável (XML aninhado).

2. **Para extrações Apple:** O XML contém os models decodificados (Chat, Call,
   Contact, etc.) que **não estão no PostgreSQL** destas extrações Google.
   Mas o PostgreSQL pode conter dados complementares.

3. **Recomendação:** O parser do SOKOL deve:
   - Tentar restaurar `database.db` em PostgreSQL temporário
   - Se bem-sucedido, usar como fonte primária para dados estruturados
   - Se falhar (dump corrompido/versão incompatível), fallback para XML
   - Mapear tabelas Cellebrite para schema SOKOL via tabela de tradução

### 6.2 database.json

```json
{
  "CaseId": "0ceab625-592f-4565-a595-6d34d8fdd6fc",
  "DeviceId": "aa720bbc-1113-46ad-aca2-89e505aa5247",
  "SourceExtractionIds": ["c17a7041-d736-46dd-8f19-bc5182cbec89"],
  "DatabaseVersion": "10.7.1.5013",
  "ActiveWatchListIds": [],
  "AdditionalFieldsInfo": [...],
  "TimeZoneInfo": "(UTC-03:00)  Sao_Paulo  (America)",
  "SourceId": "aa720bbc-1113-46ad-aca2-89e505aa5247"
}
```

| Campo | Descrição | Uso no SOKOL |
|---|---|---|
| `CaseId` | UUID do caso | `Case.id` (se gerado pelo Cellebrite) |
| `DeviceId` | UUID do dispositivo | `Document.device_id` |
| `SourceExtractionIds` | IDs das extrações | Rastreabilidade |
| `DatabaseVersion` | Versão do PA | Auditoria |
| `TimeZoneInfo` | Fuso horário | `Case.reference_timezone` |
| `AdditionalFieldsInfo` | Campos do caso | Metadados do caso |

---

## 7. Categorias de Arquivos — Análise Detalhada

### 7.1 Apple (PA10_Apple) — 57.339 arquivos no ZIP

| Categoria | Contagem | Tamanhos | Conteúdo |
|---|---|---|---|
| Image | 36.751 | 458 MB | `.thumb` (15.680), `.jpg` (1.943), `.webp` (881), `.png` (71), `.jpeg` (25), `.heic` (2) |
| Audio | 12.345 | 296 MB | `.opus` (12.333), `.m4a` (12), `.mp3` (24), `.aac` (4) |
| Uncategorized | 5.488 | 2.2 GB | `.vcf` (697 contatos), `.bnk` (48 jogos), `.pak` (2.834 recursos), `.iwa` (397 iWork), `.tml` (383 templates) |
| Shortcut | 3.571 | — | Atalhos iOS |
| Configuration | 1.096 | 11 MB | `.plist` (675), configs de apps |
| Exchange | 876 | 62 MB | `.eml` emails (858 pares metadata+conteúdo) |
| Video | 218 | 1.008 MB | `.mp4` (190), `.mov` (2) |
| Database | 217 | 88 MB | `.db` (61), `.sqlite` (48), `.sql` (34), `.sqlite3` (21), `.sqlitedb` (12), `.realm` (3) |
| Document | 146 | 13 MB | `.pdf` (79), `.xlsx` (8), `.docx` (3) |
| Text | 78 | 1.9 MB | `.xml`, `.txt`, `.csv`, `.log` |
| Archives | 20 | 525 MB | WhatsApp: `Media.tar` (494 MB), `Document.tar`, `Stickers.tar`, `Thumbnail.tar`, `GIFs.tar`; Apple: `Index_*.zip`, `tssmua.zip` |

### 7.2 Google (PA10_Google) — 398 arquivos no ZIP

| Categoria | Conteúdo |
|---|---|
| Archives | Google Takeout ZIPs: `GooglePhotos.PhotoResource_001.zip` (1.65 GB), `retorno_mandado_google.zip` (571 MB), `DriveMobileBackups.Backup_001.zip` (570 MB), `LocationHistory.Records_001.zip`, `MyActivity.MyActivity_001.zip`, etc. |
| Image | 365 JPGs extraídos dos ZIPs de Google Photos e Drive backups |
| Text | 17 arquivos: `LocationHistory.csv` (2.86 MB), `MyActivity_*.html` (5), `SubscriberInfo.html`, `ExportSummary.txt` (6), `Drive.txt`, `settings.txt.txt` |
| Uncategorized | 3 arquivos: `LocationHistory.json` (5.87 MB), `SemanticLocationHistory.json` (544 KB), `ics.ics` |

---

## 8. Dados de Localização — Formatos

### 8.1 CSV (Google Location History)

```csv
Timestamp (UTC),Latitude,Longitude,Country Codes,Display Radius (Meters),Source,Device Tag,Platform
2020-07-03T00:32:27.825Z,-22.8225613,-43.4161997,BR,15,WIFI,-9194173,android/samsung/j8y18lteub/...
```

**~19.600 registros** por extração Google.

### 8.2 JSON (Google Location History)

```json
{
  "timestampMs": "1593752547825",
  "latitudeE7": -228225613,
  "longitudeE7": -434161997,
  "accuracy": 15,
  "source": "WIFI",
  "deviceTag": -9194173,
  "platform": "ANDROID"
}
```

**Nota:** `latitudeE7` e `longitudeE7` são divididos por 10^7 para graus decimais.

### 8.3 Semantic Location History (JSON)

```json
{
  "placeVisit": {
    "location": {
      "address": "Rua ...",
      "placeId": "ChIJ...",
      "semanticType": "TYPE_HOME",
      "latitudeE7": -228225613,
      "longitudeE7": -434161997,
      "locationConfidence": 85
    },
    "duration": {
      "startTimestampMs": "1593752547825",
      "endTimestampMs": "1593760000000"
    },
    "placeConfidence": "HIGH",
    "visitConfidence": 85
  }
}
```

### 8.4 Decoded XML (Apple)

```xml
<model type="Location" decoding_confidence="High" iscarved="True">
  <modelField name="Position" type="Coordinate">
    <model type="Coordinate">
      <field name="Longitude" type="Double"><value>-43.4161997</value></field>
      <field name="Latitude" type="Double"><value>-22.8225613</value></field>
    </model>
  </modelField>
  <field name="TimeStamp" type="TimeStamp">
    <value format="TimeStampKnown" formattedTimestamp="2024-10-29T17:17:48+00:00">
      2024-10-29T17:17:48.838
    </value>
  </field>
  <field name="Confidence" type="Int32"><value>51</value></field>
  <field name="Origin" type="LocationOrigin"><value>Unknown</value></field>
</model>
```

---

## 9. Conversas e Chamadas — Formato

### 9.1 Chat (WhatsApp)

```xml
<model type="Chat">
  <field name="Source"><value>WhatsApp</value></field>
  <field name="Id"><value>5521965694862@status</value></field>
  <field name="StartTime" type="TimeStamp">...</field>
  <field name="LastActivity" type="TimeStamp">...</field>
  <multiModelField name="Participants" type="Party">
    <model type="Party">
      <field name="Identifier"><value>5521965694862@s.whatsapp.net</value></field>
      <field name="Role"><value>General</value></field>
      <field name="Name"><value>Diniz</value></field>
    </model>
  </multiModelField>
</model>
```

**Campos do Chat:**

| Campo | Tipo | Descrição |
|---|---|---|
| `Source` | String | App de origem (WhatsApp, SMS, etc.) |
| `Id` | String | ID da conversa (ex: `5521965694862@status`) |
| `StartTime` | TimeStamp | Início da conversa |
| `LastActivity` | TimeStamp | Última atividade |
| `Participants` | Party[] | Participantes |

**Campos do Party (participante):**

| Campo | Tipo | Descrição |
|---|---|---|
| `Identifier` | String | Identificador (ex: `5521965694862@s.whatsapp.net`) |
| `Role` | PartyRole | Papel: `General`, `To`, `From` |
| `Name` | String | Nome do contato |
| `Status` | PartyStatus | Status: `Unknown` |

### 9.2 Call (Chamadas)

```xml
<model type="Call">
  <field name="Source"><value>WhatsApp</value></field>
  <field name="Direction"><value>Outgoing</value></field>
  <field name="Status"><value>Established</value></field>
  <field name="TimeStamp" type="TimeStamp">...</field>
  <field name="Duration" type="TimeSpan"><value>00:00:33.6090010</value></field>
  <multiModelField name="Parties" type="Party">...</multiModelField>
</model>
```

**Campos da Call:**

| Campo | Tipo | Descrição |
|---|---|---|
| `Source` | String | App de origem |
| `Direction` | ModelDirections | `Incoming`, `Outgoing` |
| `Status` | TelephonyCallStatus | `Established`, `Missed`, `Rejected` |
| `TimeStamp` | TimeStamp | Data/hora da chamada |
| `Duration` | TimeSpan | Duração (HH:MM:SS.fffffff) |
| `Distance` | Double | Distância (se GPS disponível) |
| `NetworkName` | String | Nome da rede |
| `VideoCall` | Boolean | Se é chamada de vídeo |
| `Parties` | Party[] | Participantes |

---

## 10. Extrações Observadas — Comparativo

| Característica | PA10_Apple | PA7_Apple | PA10_Google | PA7_Google | cpx.mrusso.44 |
|---|---|---|---|---|---|
| **Tipo** | Apple iCloud Backup | Apple iCloud Backup | Google Warrant Return | Google Warrant Return | Google (pequeno) |
| **report.xml** | 525 MB / 7.9M linhas | 517 MB / 7.9M linhas | 89 MB / 1.75M linhas | 81 MB | Pequeno |
| **modelTypes** | 15 (Chat, Call, Contact, etc.) | 14 (mesmos) | 1 (Location) | 1 (Location) | 5 (Note, UserAccount, etc.) |
| **settings.json** | ✅ | ❌ | ✅ | ❌ | ✅ |
| **DbData/** | ✅ (database.db + .json) | ❌ | ✅ (database.db + .json) | ❌ | ✅ (database.db + .json) |
| **ThumbnailCache.s3db** | ❌ | ✅ (127 MB) | ❌ | ✅ (1 MB) | ❌ |
| **email/** | ❌ | ✅ (7 arquivos) | ❌ | ❌ | ❌ |
| **AccountPackage/** | ✅ (.ucae) | ✅ (.ucae) | ❌ | ❌ | ❌ |
| **files/** | 10 categorias | 10 categorias | 4 categorias | 4 categorias | 5 categorias |
| **Total ZIP entries** | 32.427 | 57.339 | 398 | 438 | 458 |
| **Tamanho UFDR** | 5.4 GB | 5.9 GB | 3.1 GB | 3.6 GB | ~12 GB |

### 10.1 Padrões observados

1. **Apple extractions** contêm dados ricos: chats, chamadas, contatos, emails,
   apps instalados, localizações, calendário, cookies, bookmarks, logs.
2. **Google extractions** contêm primariamente dados de localização e arquivos
   do Google Takeout (Photos, Drive, Calendar, MyActivity, Location History).
3. **`database.db`** está presente em extrações mais recentes (PA10) mas não
   em todas. É PostgreSQL dump, não SQLite.
4. **`ThumbnailCache.s3db`** está presente em extrações mais antigas (PA7)
   mas não nas mais recentes (PA10).
5. **`email/`** folder aparece apenas em PA7_Apple, contendo anexos extraídos
   de emails.
6. **`AccountPackage/`** (.ucae) aparece em Apple extractions, contendo dados
   de conta iCloud.

---

## 11. Implicações para o Parser SOKOL

### 11.1 Fluxo de Ingestão

```
.ufdr (ZIP)
  │
  ├── report.xml          → Parse streaming
  │   ├── <taggedFiles>   → Mapear cada <file> para Artifact
  │   └── <decodedData>   → Extrair models para Messages/Events
  │
  ├── files/              → Copiar binários para staging
  │   └── {Local Path}    → Caminho relativo dentro do ZIP
  │
  ├── DbData/database.json → Metadados do caso
  │
  └── settings.json       → Ignorar (configuração do viewer)
```

### 11.2 Mapeamento para Schema SOKOL

| Fonte UFDR | Destino SOKOL | Observação |
|---|---|---|
| `<project>@name` | `Document.title` | Nome do caso/device |
| `<project>@id` | `Document.meta.project_id` | UUID do projeto |
| `<file>@id` | `Artifact.id` | UUID do arquivo |
| `<file>@name` | `Artifact.source_member` | Nome do arquivo |
| `<file>@size` | `Artifact.size_bytes` | Tamanho |
| `<file> <item name="SHA256">` | `Artifact.media_hash` | Hash SHA-256 |
| `<file> <item name="Tags">` | `Artifact.kind` | Categoria |
| `<file> <item name="Local Path">` | Caminho no `files/` | Mapeamento para binário |
| `<file> <timestamp name="ModifyTime">` | `Artifact.meta.modified_at` | Timestamp |
| `<file>@deleted` | `Artifact.meta.deleted_state` | Estado de deleção |
| `<model type="Chat">` | `Message` + `Event` | Conversa |
| `<model type="Call">` | `Event(kind="call")` | Chamada |
| `<model type="Contact">` | `Entity(kind="contact")` | Contato |
| `<model type="Location">` | `Event(kind="location")` + `geo` | Localização |
| `<model type="Email">` | `Message` + `Event` | Email |
| `database.json@CaseId` | `Case.id` | UUID do caso |
| `database.json@TimeZoneInfo` | `Case.reference_timezone` | Fuso horário |
| `files/Image/*.jpg` | `Media` (por SHA-256) | Imagens deduplicadas |
| `files/Audio/*.opus` | `Media` (por SHA-256) | Áudios |
| `files/Video/*.mp4` | `Media` (por SHA-256) | Vídeos |
| `files/Database/*.sqlite` | `Artifact(kind="database")` | Bancos de dados |

### 11.3 Desafios de Parsing

1. **Tamanho do XML:** report.xml pode ter 90MB-525MB e 1.7M-7.9M linhas.
   Usar **streaming XML** (iterparse ou SAX), não carregar em memória.

2. **Nested models:** `<multiModelField>` contém modelos aninhados (Party
   dentro de Chat/Call). O parser precisa rastrear contexto de hierarquia.

3. **`<modelField>` (singular):** Usado para嵌套 modelos únicos (ex:
   `Position` dentro de `Location`). Diferente de `<multiModelField>` que
   contém múltiplos modelos. O parser deve:
   - Extrair o modelo aninhado recursivamente
   - Achatar campos com notação pontilhada (ex: `Position.Latitude`)
   - Fallback para campos diretos quando disponível

4. **Timestamps:** Formato ISO 8601 com offset (`2021-05-21T02:38:43+00:00`).
   Preservar o offset original para `tz_original`.

5. **Arquivos embedded:** Imagens podem ser extraídas de ZIPs internos
   (Google Photos, Drive backups). O `Local Path` aponta para o binário
   já extraído pelo Cellebrite.

6. **WhatsApp:** Os backups do WhatsApp estão em `files/Archives/` como
   `.tar` (Media.tar, Document.tar). Conteúdo precisa de extração adicional.

7. **Contatos:** Podem vir de `Contact` model (decodedData) OU de arquivos
   `.vcf` em `files/Uncategorized/`. Unificar dedup.

8. **Google Takeout:** Dados em múltiplos formatos (CSV, JSON, HTML, ZIP)
   dentro de `files/`. Cada formato requer parser específico.

### 11.4 Implementação do Parser (worker/ufdr_parser.py)

**Função `_extract_model_fields()`:**

Extrai campos de um elemento `<model>` XML para um dicionário Python.
Suporta três tipos de campos:

```python
# 1. <field> — valores escalares
<field name="Latitude" type="Double">
  <value type="Double"><![CDATA[-23.133690]]></value>
</field>

# 2. <modelField> — modelo嵌套 único (Google format)
<modelField name="Position" type="Coordinate">
  <model type="Coordinate">
    <field name="Longitude" type="Double"><value>-43.546154</value></field>
    <field name="Latitude" type="Double"><value>-23.133690</value></field>
  </model>
</modelField>

# 3. <multiModelField> — múltiplos modelos aninhados (Apple format)
<multiModelField name="Participants" type="Party">
  <model type="Party">
    <field name="Identifier"><value>5521965694862@s.whatsapp.net</value></field>
  </model>
</multiModelField>
```

**Estrutura de saída:**

```python
{
    "id": "dc291f8e-...",
    "type": "Location",
    "fields": [
        {"name": "Latitude", "type": "Double", "value": "-23.133690"},
        {"name": "Position.Latitude", "type": "Double", "value": "-23.133690"},  # flattened
    ],
    "modelFields": [
        {"name": "Position", "type": "Coordinate", "model": {...}}
    ],
    "multiModelFields": [...]
}
```

**Função `parse_location()` (worker/parsers/location.py):**

```python
# Fallback chain para coordenadas:
lat = _extract_field(model, "Latitude")           # Apple format
lat = _extract_field(model, "Position.Latitude")  # Google format (flattened)
```

**Resultado real (Google Warrant Return 3.1GB):**
- 40,199 Location models parseados
- 40,199 eventos inseridos com coordenadas válidas
- 0 erros de parsing
- Coordenadas: Rio de Janeiro (lat -22 a -23, lon -43 a -44)

---

## 12. Dump de Chaves de Identificação

### Apple
- Email do iCloud: `daniloidelfonso@icloud.com` (PA7, PA10)
- Phone number: `5521970082771` (observado em paths WhatsApp)
- Account ID: `472538`

### Google
- Email: `julianamarinho586@gmail.com`
- Account ID: `671559985358`
- Recovery email: `julianamarinjo586@gmail.com` (com typo)
- Recovery SMS: `+5521996698388`
- Name: Juliana Souza

### cpx.mrusso.44
- Email: `cpx.mrusso.44@gmail.com`

---

## 13. Referências

- Cellebrite UFED Physical Analyzer v10.7.1.5013
- Namespace XML: `http://pa.cellebrite.com/report/2.0`
- Report version: `8.5`
- Database format: PostgreSQL custom dump v1.14-0 (PGDMP)
- Timestamp format: ISO 8601 com timezone offset
- Hash algorithms: SHA-256, MD5
