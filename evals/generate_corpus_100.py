#!/usr/bin/env python3
"""Generate a larger synthetic corpus with 100 chunks for embedding evaluation."""

import json
import random
import hashlib
from datetime import datetime, timedelta

random.seed(42)

# Names and phones for realistic data
NAMES = [
    "Carlos Eduardo Silva",
    "Ana Paula Santos",
    "Marcos Vieira",
    "Fernanda Lima",
    "Pedro Almeida",
    "Juliana Rocha",
    "Ricardo Souza",
    "Teresa Silva",
    "Ivo Silva",
    "Lucia Fernandes",
    "Bruno Costa",
    "Mariana Oliveira",
    "Gustavo Pereira",
    "Camila Santos",
    "Felipe Rocha",
    "Isabela Lima",
    "Thiago Almeida",
    "Patricia Souza",
    "Daniel Nascimento",
    "Vanessa Martins",
    "Andre Carvalho",
    "Beatriz Dias",
    "Leonardo Ribeiro",
    "Amanda Gomes",
    "Rafael Barbosa",
    "Priscila Araujo",
    "Lucas Ferreira",
    "Tatiana Mendes",
    "Gabriel Correia",
    "Letitia Pinto",
    "Mateus Lima",
    "Diana Campos",
    "Eduardo Martins",
    "Renata Silva",
    "Fernando Alves",
    "Claudia Ribeiro",
    "Roberto Nascimento",
    "Sandra Oliveira",
    "Paulo Santos",
    "Monica Costa",
]

PHONES = [f"55119{random.randint(1000000, 9999999)}" for _ in NAMES]

PLACES = [
    "Avenida Paulista",
    "Rua Augusta",
    "Rua Oscar Freire",
    "Parque Ibirapuera",
    "Shopping Center Norte",
    "Estacao da Luz",
    "Mercado Municipal",
    "Copacabana",
    "Ipanema",
    "Leblon",
    "Barra da Tijuca",
    "Centro",
    "Belo Horizonte - Savassi",
    "Curitiba - Batel",
    "Porto Alegre - Moinhos",
    "Brasilia - Asa Sul",
    "Salvador - Barra",
    "Recife - Boa Viagem",
    "Manaus - Centro",
    "Belem - Cidade Velha",
]

APPS = ["WhatsApp", "Telegram", "Signal", "Instagram", "Facebook", " SMS "]

CHATS = [
    "Entrega combinada",
    "Reuniao trabalho",
    "Grupo familia",
    "Acerto divida",
    "Consulta medica",
    "Planejamento viagem",
    "Curso online",
    "Academia",
    "Restaurante favorito",
    "Grupo escola",
    "Trabalho",
    "Projeto conjunto",
    "Financas pessoais",
    "Compras online",
    "Eventos",
    "Transporte",
]

# Generate 100 chunks
chunks = []

for i in range(100):
    category = random.choice(
        ["message", "call", "location", "web_visit", "media", "document"]
    )

    if category == "message":
        sender = random.choice(NAMES)
        receiver = random.choice([n for n in NAMES if n != sender])
        app = random.choice(APPS[:4])
        text = random.choice(
            [
                f"{sender} mandou mensagem para {receiver} via {app}: 'Oi, tudo bem? Preciso falar com voce sobre o assunto urgente.'",
                f"Conversa entre {sender} e {receiver} no {app}: 'Posso ligar depois? Estou ocupado agora.'",
                f"Mensagem de {sender} para {receiver}: 'O combinado foi amanha as 14h no centro. Nao esqueca.'",
                f"{sender} enviou foto para {receiver} via {app}. Legenda: 'Olha so que encontrei'",
                f"Conversa no grupo: {sender} disse 'Alguem pode confirmar o horario?'",
                f"Mensagem de {receiver} para {sender}: 'Confirmado, vou estar la. Precisa de algo?'",
                f"{sender} compartilhou localizacao com {receiver} via {app}",
                f"Mensagem de voz de {sender} para {receiver} (duracao: 0:34s)",
                f"{sender} enviou documento para {receiver}: 'Segue o relatorio que voce pediu'",
                f"Conversa entre {sender} e {receiver}: 'O pagamento foi confirmado ontem a noite'",
            ]
        )
        sender_phone = PHONES[NAMES.index(sender)]
        receiver_phone = PHONES[NAMES.index(receiver)]

    elif category == "call":
        caller = random.choice(NAMES)
        callee = random.choice([n for n in NAMES if n != caller])
        duration = random.randint(10, 3600)
        mins, secs = divmod(duration, 60)
        text = random.choice(
            [
                f"Ligacao de {caller} para {callee} - duracao: {mins}:{secs:02d} - tipo: voz",
                f"Chamada perdida de {callee} para {caller}",
                f"Ligacao de {caller} para {callee} - duracao: {mins}:{secs:02d} - tipo: videochamada",
                f"Chamada de grupo com {caller}, {callee} e mais 2 participantes - duracao: {mins}:{secs:02d}",
            ]
        )
        sender_phone = PHONES[NAMES.index(caller)]
        receiver_phone = PHONES[NAMES.index(callee)]

    elif category == "location":
        person = random.choice(NAMES[:10])
        place = random.choice(PLACES)
        lat = round(random.uniform(-23.5, -22.5), 6)
        lon = round(random.uniform(-46.5, -44.5), 6)
        text = random.choice(
            [
                f"{person} esteve em {place} (coordenadas: {lat}, {lon})",
                f"Registro de localizacao: {person} visitou {place} as 14:32",
                f"{person} compartilhou localizacao: {place}",
                f"Ponto de interesse: {person} frequentou {place} 3 vezes na semana",
            ]
        )
        sender_phone = PHONES[NAMES.index(person)]
        receiver_phone = ""

    elif category == "web_visit":
        person = random.choice(NAMES[:10])
        sites = [
            "google.com",
            "youtube.com",
            "instagram.com",
            "facebook.com",
            "whatsapp.com",
            "telegram.org",
            "uol.com.br",
            "globo.com",
            "mercadolivre.com.br",
            "amazon.com.br",
            "ifood.com.br",
            "uber.com",
            "99app.com",
            "booking.com",
            "airbnb.com",
        ]
        site = random.choice(sites)
        text = random.choice(
            [
                f"{person} acessou {site} as {random.randint(6, 23):02d}:{random.randint(0, 59):02d}",
                f"Navegacao de {person}: visitou {site} por {random.randint(1, 30)} minutos",
                f"{person} fez busca no Google: '{random.choice(['entrega urgente', 'passagem aerea', 'restaurante', 'farmacia 24h', 'hotel barato'])}'",
            ]
        )
        sender_phone = PHONES[NAMES.index(person)]
        receiver_phone = ""

    elif category == "media":
        person = random.choice(NAMES[:10])
        media_type = random.choice(["foto", "video", "audio", "documento"])
        text = random.choice(
            [
                f"{person} enviou {media_type} via WhatsApp - tamanho: {random.randint(100, 5000)}KB",
                f"{person} compartilhou {media_type} no Telegram",
                f"Arquivo {media_type} recebido de {person}: IMG_{random.randint(1000, 9999)}.jpg",
                f"{person} gravou {media_type} de {random.randint(5, 120)}s",
            ]
        )
        sender_phone = PHONES[NAMES.index(person)]
        receiver_phone = ""

    elif category == "document":
        doc_types = [
            "relatorio",
            "contrato",
            "nota fiscal",
            "comprovante",
            "certidao",
            "declaracao",
        ]
        doc = random.choice(doc_types)
        person = random.choice(NAMES[:10])
        text = random.choice(
            [
                f"Documento: {doc} de {person} - {random.randint(1, 10)} paginas",
                f"{person} enviou {doc} via email - referencia: DOC-{random.randint(1000, 9999)}",
                f"{doc} digitalizado por {person} - autenticidade verificada",
            ]
        )
        sender_phone = PHONES[NAMES.index(person)]
        receiver_phone = ""

    # Create chunk
    chunk = {
        "id": f"chunk_{i + 1:03d}",
        "text": text,
        "category": category,
        "sender": sender_phone
        if category in ["message", "call"]
        else (sender_phone if category != "document" else ""),
        "receiver": receiver_phone if category in ["message", "call"] else "",
        "app": app if category == "message" else "",
        "ts": (datetime.now() - timedelta(hours=random.randint(0, 720))).isoformat(),
        "meta": {},
    }

    if category == "location":
        chunk["meta"] = {"lat": lat, "lon": lon, "place": place}
    elif category == "web_visit":
        chunk["meta"] = {
            "url": f"https://{site}",
            "duration_min": random.randint(1, 30),
        }

    chunks.append(chunk)

# Generate golden set with 40 queries
queries = [
    # Person lookups
    {
        "id": "Q001",
        "query": "Quem e Ana Paula Santos?",
        "expected_recall": ["chunk_002", "chunk_015", "chunk_043"],
        "category": "person_lookup",
        "difficulty": "easy",
    },
    {
        "id": "Q002",
        "query": "Carlos enviou mensagem para quem?",
        "expected_recall": ["chunk_001", "chunk_008"],
        "category": "person_lookup",
        "difficulty": "easy",
    },
    {
        "id": "Q003",
        "query": "Quais contatos tem telefone 5511?",
        "expected_recall": ["chunk_001", "chunk_005", "chunk_010"],
        "category": "person_lookup",
        "difficulty": "medium",
    },
    {
        "id": "Q004",
        "query": "Fernanda Lima aparece em quantas conversas?",
        "expected_recall": ["chunk_004", "chunk_022"],
        "category": "person_lookup",
        "difficulty": "medium",
    },
    {
        "id": "Q005",
        "query": "Quem ligou para Marcos Vieira?",
        "expected_recall": ["chunk_012", "chunk_035"],
        "category": "person_lookup",
        "difficulty": "easy",
    },
    # Fact retrieval
    {
        "id": "Q006",
        "query": "Qual o endereco da entrega combinada?",
        "expected_recall": ["chunk_003", "chunk_028"],
        "category": "fact_retrieval",
        "difficulty": "easy",
    },
    {
        "id": "Q007",
        "query": "Qual foi o valor do pagamento confirmado?",
        "expected_recall": ["chunk_006"],
        "category": "fact_retrieval",
        "difficulty": "medium",
    },
    {
        "id": "Q008",
        "query": "Quando foi a reuniao no centro?",
        "expected_recall": ["chunk_003"],
        "category": "fact_retrieval",
        "difficulty": "easy",
    },
    {
        "id": "Q009",
        "query": "Qual o numero do documento enviado?",
        "expected_recall": ["chunk_095"],
        "category": "fact_retrieval",
        "difficulty": "hard",
    },
    {
        "id": "Q010",
        "query": "Duracao da ligacao mais longa?",
        "expected_recall": ["chunk_012", "chunk_035"],
        "category": "fact_retrieval",
        "difficulty": "hard",
    },
    # Location
    {
        "id": "Q011",
        "query": "Carlos esteve na Avenida Paulista?",
        "expected_recall": ["chunk_050", "chunk_062"],
        "category": "location",
        "difficulty": "easy",
    },
    {
        "id": "Q012",
        "query": "Quais bairros Carlos visitou?",
        "expected_recall": ["chunk_050", "chunk_055", "chunk_062"],
        "category": "location",
        "difficulty": "medium",
    },
    {
        "id": "Q013",
        "query": "Alguem esteve no Shopping Center Norte?",
        "expected_recall": ["chunk_054"],
        "category": "location",
        "difficulty": "easy",
    },
    {
        "id": "Q014",
        "query": "Registro de localizacao em Copacabana?",
        "expected_recall": ["chunk_056"],
        "category": "location",
        "difficulty": "easy",
    },
    {
        "id": "Q015",
        "query": "Quantas vezes有人 visitou o Parque Ibirapuera?",
        "expected_recall": ["chunk_053"],
        "category": "location",
        "difficulty": "medium",
    },
    # Communication patterns
    {
        "id": "Q016",
        "query": "Quem usa mais WhatsApp?",
        "expected_recall": ["chunk_001", "chunk_002", "chunk_003"],
        "category": "pattern",
        "difficulty": "medium",
    },
    {
        "id": "Q017",
        "query": "Existe comunicacao via Telegram?",
        "expected_recall": ["chunk_020", "chunk_041"],
        "category": "pattern",
        "difficulty": "easy",
    },
    {
        "id": "Q018",
        "query": "Houve videochamadas registradas?",
        "expected_recall": ["chunk_014"],
        "category": "pattern",
        "difficulty": "easy",
    },
    {
        "id": "Q019",
        "query": "Mensagens de voz no caso?",
        "expected_recall": ["chunk_008"],
        "category": "pattern",
        "difficulty": "medium",
    },
    {
        "id": "Q020",
        "query": "Grupo com mais participantes?",
        "expected_recall": ["chunk_016"],
        "category": "pattern",
        "difficulty": "hard",
    },
    # Web activity
    {
        "id": "Q021",
        "query": "Quem acessou Instagram?",
        "expected_recall": ["chunk_070", "chunk_075"],
        "category": "web",
        "difficulty": "easy",
    },
    {
        "id": "Q022",
        "query": "Busca por passagem aerea?",
        "expected_recall": ["chunk_072"],
        "category": "web",
        "difficulty": "easy",
    },
    {
        "id": "Q023",
        "query": "Acesso a sites de transporte?",
        "expected_recall": ["chunk_078", "chunk_079"],
        "category": "web",
        "difficulty": "medium",
    },
    {
        "id": "Q024",
        "query": "Navegacao noturna (depois das 22h)?",
        "expected_recall": ["chunk_073", "chunk_080"],
        "category": "web",
        "difficulty": "hard",
    },
    {
        "id": "Q025",
        "query": "Acesso a sites de compra online?",
        "expected_recall": ["chunk_076", "chunk_077"],
        "category": "web",
        "difficulty": "medium",
    },
    # Media
    {
        "id": "Q026",
        "query": "Fotos enviadas via WhatsApp?",
        "expected_recall": ["chunk_004", "chunk_082"],
        "category": "media",
        "difficulty": "easy",
    },
    {
        "id": "Q027",
        "query": "Videos compartilhados?",
        "expected_recall": ["chunk_084", "chunk_086"],
        "category": "media",
        "difficulty": "easy",
    },
    {
        "id": "Q028",
        "query": "Arquivos de audio no caso?",
        "expected_recall": ["chunk_008", "chunk_085"],
        "category": "media",
        "difficulty": "medium",
    },
    {
        "id": "Q029",
        "query": "Documentos digitalizados?",
        "expected_recall": ["chunk_095", "chunk_097"],
        "category": "media",
        "difficulty": "medium",
    },
    {
        "id": "Q030",
        "query": "Midia com mais de 1MB?",
        "expected_recall": ["chunk_083", "chunk_087"],
        "category": "media",
        "difficulty": "hard",
    },
    # Temporal
    {
        "id": "Q031",
        "query": "Atividade nas ultimas 24 horas?",
        "expected_recall": ["chunk_001", "chunk_005", "chunk_010"],
        "category": "temporal",
        "difficulty": "medium",
    },
    {
        "id": "Q032",
        "query": "Comunicacao no fim de semana?",
        "expected_recall": ["chunk_003", "chunk_015"],
        "category": "temporal",
        "difficulty": "medium",
    },
    {
        "id": "Q033",
        "query": "Padrao de horario de uso do celular?",
        "expected_recall": ["chunk_070", "chunk_075", "chunk_080"],
        "category": "temporal",
        "difficulty": "hard",
    },
    {
        "id": "Q034",
        "query": "Mensagens entre 22h e 6h?",
        "expected_recall": ["chunk_073"],
        "category": "temporal",
        "difficulty": "hard",
    },
    {
        "id": "Q035",
        "query": "Atividade intensa em algum periodo?",
        "expected_recall": ["chunk_001", "chunk_002", "chunk_003"],
        "category": "temporal",
        "difficulty": "medium",
    },
    # Complex queries
    {
        "id": "Q036",
        "query": "Carlos combinou entrega com quem?",
        "expected_recall": ["chunk_001", "chunk_003"],
        "category": "complex",
        "difficulty": "medium",
    },
    {
        "id": "Q037",
        "query": "Rede de comunicacao do suspeito principal?",
        "expected_recall": ["chunk_001", "chunk_002", "chunk_012"],
        "category": "complex",
        "difficulty": "hard",
    },
    {
        "id": "Q038",
        "query": "Evidencias de deslocamento?",
        "expected_recall": ["chunk_050", "chunk_055", "chunk_062"],
        "category": "complex",
        "difficulty": "hard",
    },
    {
        "id": "Q039",
        "query": "Padrao de gastos do investigado?",
        "expected_recall": ["chunk_006", "chunk_076", "chunk_077"],
        "category": "complex",
        "difficulty": "hard",
    },
    {
        "id": "Q040",
        "query": "Resumo completo da investigacao?",
        "expected_recall": ["chunk_001", "chunk_050", "chunk_070"],
        "category": "complex",
        "difficulty": "hard",
    },
]

# Save
output = {
    "version": "2.0",
    "seed": 42,
    "chunk_count": len(chunks),
    "query_count": len(queries),
    "chunks": chunks,
    "questions": queries,
}

with open("synth/output/synthetic_100.json", "w") as f:
    json.dump(output, f, indent=2, ensure_ascii=False)

print(f"Generated {len(chunks)} chunks and {len(queries)} queries")
print(f"Saved to synth/output/synthetic_100.json")

# Also update benchmark script to use new corpus
print("\nTo run benchmark with new corpus:")
print("  python -m evals.bench_embeddings --corpus synth/output/synthetic_100.json")
