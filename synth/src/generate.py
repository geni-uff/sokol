"""SOKOL synth — seed-based synthetic UFDR generator.

Generates a reproducible UFDR package for testing the SOKOL pipeline.
Same seed always produces the same corpus, gabarito, and golden set.

Usage:
    python -m synth.src.generate --seed 42 --output ./synth/output
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import struct
import uuid
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.dom import minidom
from xml.sax.saxutils import escape

# ── Namespace ──────────────────────────────────────────────────────────────
NS = "http://pa.cellebrite.com/report/2.0"
ET.register_namespace("", NS)

# ── Seed-controlled RNG ────────────────────────────────────────────────────
_rng: random.Random | None = None


def _uuid() -> str:
    return str(uuid.UUID(bytes=_rng.randbytes(16)))


def _ts(base: datetime, delta_minutes: int) -> str:
    dt = base + timedelta(minutes=delta_minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+00:00")


def _ts_short(base: datetime, delta_minutes: int) -> str:
    dt = base + timedelta(minutes=delta_minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


# ── Case scenario ──────────────────────────────────────────────────────────
CASE = {
    "examiner": "Dra. Marina Costa",
    "case_name": "Operacao Fênix",
    "case_number": "2026/00142",
    "evidence_number": "EVD-003",
    "department": "Divisao de Investigacao Digital",
    "organization": "Polícia Civil",
    "investigator": "Delegado Ricardo Almeida",
    "crime_type": "Trafico de Drogas",
    "notes": "Investigacao sobre rede de trafico via WhatsApp. Dispositivo apreendido em mandado de busca.",
}

OWNER = {
    "name": "Carlos Eduardo Silva",
    "phone": "5511999887766",
    "service_id": "5511999887766@s.whatsapp.net",
}

CONTACTS = [
    {
        "name": "Ana Paula Santos",
        "phone": "5511988776655",
        "service_id": "5511988776655@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Marcos Vieira",
        "phone": "5521977665544",
        "service_id": "5521977665544@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Fernanda Lima",
        "phone": "5531966554433",
        "service_id": "5531966554433@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Pedro Almeida",
        "phone": "5511955443322",
        "service_id": "5511955443322@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Juliana Rocha",
        "phone": "5521944332211",
        "service_id": "5521944332211@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Ricardo Souza",
        "phone": "5511933221100",
        "service_id": "5511933221100@s.whatsapp.net",
        "category": "Contato",
    },
    {
        "name": "Banco do Brasil",
        "phone": "551130039030",
        "service_id": "",
        "category": "Servico",
    },
    {
        "name": "Nubank",
        "phone": "551140028922",
        "service_id": "",
        "category": "Servico",
    },
    {
        "name": "Mae - Teresa Silva",
        "phone": "5511987654321",
        "service_id": "5511987654321@s.whatsapp.net",
        "category": "Familia",
    },
    {
        "name": "Ivo - Irmao",
        "phone": "5511976543210",
        "service_id": "5511976543210@s.whatsapp.net",
        "category": "Familia",
    },
]

# ── Conversations ──────────────────────────────────────────────────────────
BASE_DATE = datetime(2026, 3, 15, 8, 0, 0, tzinfo=timezone.utc)

WHATSAPP_CHATS = [
    {
        "chat_id": f"{OWNER['phone']}_{CONTACTS[0]['phone']}",
        "chat_name": CONTACTS[0]["name"],
        "participants": [OWNER["service_id"], CONTACTS[0]["service_id"]],
        "source": "WhatsApp",
        "messages": [
            # Trade conversation — key evidence
            ("outgoing", "Oi, tudo bem? Preciso falar com vc sobre o assunto", 0),
            ("incoming", "Fala, to ouvindo", 1),
            ("outgoing", "O pacote ta pronto, quando posso entregar?", 2),
            ("incoming", "Amanha de manha, no ponto de sempre", 3),
            ("outgoing", "Beleza, 8h no parking do shopping", 4),
            ("incoming", "So que o valor mudou, agora e 5k", 5),
            ("outgoing", "5k? tava combinado 4k", 6),
            ("incoming", "Preco subiu, mercado ta dificil", 7),
            ("outgoing", "Ta, vou ter que arranjar a diferenca", 8),
            ("incoming", "Me manda pix quando tiver", 9),
            ("outgoing", "Vou mandar hoje a noite", 10),
            ("incoming", "Tranquilo, combina direitinho", 11),
        ],
    },
    {
        "chat_id": f"{OWNER['phone']}_{CONTACTS[1]['phone']}",
        "chat_name": CONTACTS[1]["name"],
        "participants": [OWNER["service_id"], CONTACTS[1]["service_id"]],
        "source": "WhatsApp",
        "messages": [
            ("outgoing", "Marcos, vc tem o contato do pessoal de BH?", 20),
            ("incoming", "Tenho sim, quer que eu passe?", 21),
            ("outgoing", "Sim, preciso de uma entrega grande", 22),
            ("incoming", "Vou mandar no privado, cuidado com o grupo", 23),
            ("outgoing", "Pode mandar, to sozinho", 24),
            ("incoming", "Numero: 3198877665, fala com o Joao", 25),
            ("outgoing", "Valeu, vou entrar em contato", 26),
            ("incoming", "Qualquer coisa me avisa", 27),
        ],
    },
    {
        "chat_id": f"{OWNER['phone']}_{CONTACTS[2]['phone']}",
        "chat_name": CONTACTS[2]["name"],
        "participants": [OWNER["service_id"], CONTACTS[2]["service_id"]],
        "source": "WhatsApp",
        "messages": [
            ("incoming", "Amor, voce vai jantar em casa hoje?", 50),
            ("outgoing", "Nao, vou sair com os caras do trabalho", 51),
            ("incoming", "Ta, cuidado por favor", 52),
            ("outgoing", "Sempre, te amo", 53),
            ("incoming", "Eu tambem, beijo", 54),
        ],
    },
    {
        "chat_id": f"{OWNER['phone']}_{CONTACTS[3]['phone']}",
        "chat_name": CONTACTS[3]["name"],
        "participants": [OWNER["service_id"], CONTACTS[3]["service_id"]],
        "source": "WhatsApp",
        "messages": [
            ("outgoing", "Pedro, vc ainda tem aquela capa do celular?", 60),
            ("incoming", "Tenho sim, quer que eu te mande?", 61),
            ("outgoing", "Sim, por favor", 62),
            ("incoming", "Te mando amanhã", 63),
            ("outgoing", "Obrigado", 64),
        ],
    },
    {
        "chat_id": f"{OWNER['phone']}_group_trafico",
        "chat_name": "G. Operacoes",
        "participants": [
            OWNER["service_id"],
            CONTACTS[0]["service_id"],
            CONTACTS[1]["service_id"],
            CONTACTS[4]["service_id"],
        ],
        "source": "WhatsApp",
        "messages": [
            ("outgoing", "Galera, reunião sexta as 20h no apartamento", 100),
            ("incoming", "Pode ser, vou levar os docs", 101),
            ("outgoing", "Juliana, vc confirma presenca?", 102),
            ("incoming", "Confirmado, estarei la", 103),
            ("outgoing", "Perfeito, trazer os valores tambem", 104),
            ("incoming", "Trago, combinado", 105),
            ("outgoing", "Vamos fechar tudo sexta", 106),
            ("incoming", "Fechado", 107),
        ],
    },
]

SMS_MESSAGES = [
    ("incoming", "Seu codigo de verificacao e 4829. Nao compartilhe.", 150),
    ("incoming", "Lembrete: consulta medica amanha 14h", 200),
    ("outgoing", "Cheguei, to na portaria", 250),
    ("incoming", "Ok, ja desci", 251),
    ("outgoing", "Mensagem automatica: Obrigado por entrar em contato", 300),
    ("incoming", "Proposta de emprestimo aprovada! Ligue 0800", 350),
    ("outgoing", "Mae, vou jantar la domingo", 400),
    ("incoming", "Otimo, vou fazer seu prato favorito", 401),
    ("outgoing", "Valeu, te amo", 402),
    ("incoming", "Feliz aniversario filho! Que Deus te abencoe", 500),
]

CALL_LOG = [
    ("outgoing", "00:05:23", CONTACTS[0]["phone"], " answered"),
    ("incoming", "00:12:45", CONTACTS[1]["phone"], " answered"),
    ("outgoing", "00:00:32", CONTACTS[2]["phone"], " no_answer"),
    ("incoming", "00:03:11", CONTACTS[0]["phone"], " answered"),
    ("outgoing", "00:08:56", CONTACTS[3]["phone"], " answered"),
    ("incoming", "00:01:07", "5511987654321", " answered"),  # Mae
    ("outgoing", "00:00:15", CONTACTS[4]["phone"], " busy"),
    ("incoming", "00:06:33", CONTACTS[5]["phone"], " answered"),
    ("outgoing", "00:02:44", CONTACTS[0]["phone"], " answered"),
    ("incoming", "00:04:12", "5511976543210", " answered"),  # Ivo
    ("outgoing", "00:00:48", CONTACTS[7]["phone"], " answered"),
    ("incoming", "00:07:22", CONTACTS[1]["phone"], " answered"),
    ("outgoing", "00:01:55", CONTACTS[0]["phone"], " answered"),
    ("incoming", "00:00:39", CONTACTS[6]["phone"], " answered"),
    ("outgoing", "00:03:08", CONTACTS[2]["phone"], " answered"),
]

# São Paulo coordinates (approximate)
LOCATIONS = [
    (-23.5505, -46.6333, "Avenida Paulista, 1000", 100),
    (-23.5489, -46.6388, "Rua Augusta, 500", 110),
    (-23.5537, -46.6365, "Rua Oscar Freire, 300", 120),
    (-23.5614, -46.6555, "Avenida Brigadeiro Faria Lima, 1500", 130),
    (-23.5445, -46.6384, "Rua Haddock Lobo, 200", 140),
    (-23.5571, -46.6347, "Rua Bela Cintra, 800", 150),
    (-23.5632, -46.6521, "Avenida Pres. Juscelino Kubitschek, 900", 160),
    (-23.5508, -46.6410, "Rua Frei Caneca, 400", 170),
    (-23.5478, -46.6349, "Rua Caio Prado, 150", 180),
    (-23.5555, -46.6398, "Rua Rui Barbosa, 600", 190),
    (-23.5612, -46.6503, "Avenida Carlos Bardi, 1200", 200),
    (-23.5491, -46.6372, "Rua Avanhandava, 100", 210),
    (-23.5530, -46.6355, "Rua 13 de Maio, 250", 220),
    (-23.5583, -46.6432, "Rua Padre Anchieta, 350", 230),
    (-23.5467, -46.6321, "Rua Major Sertorio, 180", 240),
    (-23.5541, -46.6378, "Rua Conselheiro Furtado, 420", 250),
    (-23.5605, -46.6487, "Avenida Europa, 700", 260),
    (-23.5485, -46.6356, "Rua Martins Fontes, 300", 270),
    (-23.5519, -46.6344, "Rua Liberdade, 550", 280),
    (-23.5568, -46.6415, "Rua Teodoro Sampaio, 800", 290),
]

WEB_HISTORY = [
    (
        "https://www.google.com/search?q=comprar+celular",
        "Comprar celular - Pesquisa Google",
        300,
    ),
    (
        "https://www.mercadolivre.com.br/celular-samsung",
        "Samsung Galaxy S23 - Mercado Livre",
        301,
    ),
    ("https://www.uol.com.br/", "UOL - Portal", 305),
    ("https://www.globo.com/", "Globo.com", 310),
    ("https://www.facebook.com/", "Facebook", 315),
    ("https://www.instagram.com/", "Instagram", 320),
    ("https://www.youtube.com/", "YouTube", 325),
    ("https://www.whatsapp.com/web", "WhatsApp Web", 330),
    (
        "https://www.google.com/search?q=ponto+de+encontro+seguro",
        "ponto de encontro seguro - Pesquisa Google",
        340,
    ),
    ("https://www.waze.com/pt-BR/live-map", "Waze - Mapa ao vivo", 345),
    (
        "https://www.google.com/maps/@-23.5505,-46.6333",
        "Google Maps - Avenida Paulista",
        350,
    ),
    ("https://www.linkedin.com/feed/", "LinkedIn Feed", 355),
    ("https://www.reddit.com/r/brasil/", "Reddit - r/brasil", 360),
    ("https://www.twitter.com/home", "X (Twitter)", 365),
    (
        "https://www.google.com/search?q=como+enviar+pix",
        "como enviar pix - Pesquisa Google",
        370,
    ),
    ("https://www.bb.com.br/site/app/", "Banco do Brasil - App", 375),
    ("https://www.nu.com.br/", "Nubank", 380),
    (
        "https://www.google.com/search?q=apartamento+alugar+sao+paulo",
        "apartamento alugar sao paulo - Pesquisa Google",
        385,
    ),
    ("https://www.zapimoveis.com.br/", "ZAP Imóveis", 390),
    ("https://www.vivareal.com.br/", "Viva Real", 395),
    (
        "https://www.google.com/search?q=receita+bolo+chocolate",
        "receita bolo chocolate - Pesquisa Google",
        400,
    ),
    ("https://www.tudogostoso.com.br/", "TudoGostoso", 405),
    (
        "https://www.google.com/search?q=horario+onibus+sp",
        "horario onibus sp - Pesquisa Google",
        410,
    ),
    ("https://www.sptrans.com.br/", "SPTrans", 415),
    (
        "https://www.google.com/search?q=filme+netflix",
        "filme netflix - Pesquisa Google",
        420,
    ),
    ("https://www.netflix.com/browse", "Netflix", 425),
    (
        "https://www.google.com/search?q=clima+sao+paulo",
        "clima sao paulo - Pesquisa Google",
        430,
    ),
    ("https://www.climatempo.com.br/", "Climatempo", 435),
    (
        "https://www.google.com/search?q=resultado+lotofacil",
        "resultado lotofacil - Pesquisa Google",
        440,
    ),
    (
        "https://www.google.com/search?q=calcada+regras+transito",
        "calcada regras transito - Pesquisa Google",
        445,
    ),
]


# ── File generation helpers ────────────────────────────────────────────────
def _make_image_bytes(seed: int, width: int = 1920, height: int = 1080) -> bytes:
    """Generate minimal valid JPEG bytes (stub)."""
    # Minimal JFIF header + solid color + EOI
    import io

    buf = io.BytesIO()
    # SOI
    buf.write(b"\xff\xd8")
    # APP0 JFIF
    buf.write(b"\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00")
    # DQT
    buf.write(b"\xff\xdb\x00\x43\x00")
    buf.write(bytes([8] * 64))
    # SOF0
    buf.write(b"\xff\xc0\x00\x11\x08")
    buf.write(struct.pack(">HH", height, width))
    buf.write(b"\x01\x11\x11\x00")
    # DHT DC
    buf.write(
        b"\xff\xc4\x00\x1f\x00\x00\x01\x05\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07\x08\x09\x0a\x0b"
    )
    # SOS
    buf.write(b"\xff\xda\x00\x0c\x03\x01\x00\x02\x11\x03\x11\x00\x3f\x00")
    # Dummy data
    buf.write(_rng.randbytes(256))
    # EOI
    buf.write(b"\xff\xd9")
    return buf.getvalue()


def _make_audio_stub(seed: int, duration_sec: float = 5.0) -> bytes:
    """Generate minimal valid OGG/Opus stub."""
    # OGG container header (minimal)
    header = b"OggS"  # capture pattern
    header += b"\x00"  # version
    header += b"\x02"  # header type
    header += b"\x00\x00\x00\x00\x00\x00\x00\x00"  # granule pos
    header += struct.pack("<I", _rng.randint(0, 2**32))  # serial
    header += struct.pack("<I", 0)  # page seq
    header += struct.pack("<I", 0)  # checksum (ignored)
    header += b"\x01"  # segments
    header += b"\x1e"  # segment table
    # Opus head
    header += b"OpusHead"
    header += b"\x01\x02\x00\x00"  # version, channels, pre-skip
    header += struct.pack("<I", 48000)  # sample rate
    header += b"\x00\x00\x00\x00"  # output gain
    header += b"\x00"  # mapping family
    # Padding
    header += _rng.randbytes(128)
    return header


def _make_video_stub(seed: int) -> bytes:
    """Generate minimal valid MP4 stub."""
    # ftyp box
    ftyp = (
        struct.pack(">I", 20)
        + b"ftyp"
        + b"isom"
        + struct.pack(">I", 0x200)
        + b"isom"
        + b"iso2"
        + b"mp41"
    )
    # moov box (empty placeholder)
    moov = struct.pack(">I", 8) + b"moov"
    return ftyp + moov


def _make_document_stub(ext: str) -> bytes:
    """Generate minimal document stub."""
    if ext == ".pdf":
        return b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\nxref\n0 0\ntrailer\n<< >>\nstartxref\n0\n%%EOF"
    elif ext == ".txt":
        return b"Synthetic document for SOKOL testing.\nThis is a stub file.\n"
    elif ext == ".csv":
        return b"Name,Value,Date\nItem1,100,2026-01-01\nItem2,200,2026-01-02\n"
    return b"\x00"


# ── XML generation ─────────────────────────────────────────────────────────
def _build_file_xml(
    file_id: str,
    fs: str,
    fsid: str,
    path: str,
    name: str,
    size: int,
    tag: str,
    local_path: str,
    sha256: str,
    md5: str,
    timestamps: dict[str, str],
    exif: dict | None = None,
) -> ET.Element:
    """Build a <file> element for taggedFiles."""
    f = ET.Element("file")
    f.set("fs", fs)
    f.set("fsid", fsid)
    f.set("path", path)
    f.set("name", name)
    f.set("size", str(size))
    f.set("id", file_id)
    f.set("extractionId", "0")
    f.set("deleted", "Intact")
    f.set("embedded", "false")
    f.set("isrelated", "False")
    f.set("isNative", "True")
    f.set("source_index", str(_rng.randint(1000, 99999)))

    # accessInfo
    ai = ET.SubElement(f, "accessInfo")
    for ts_name, ts_val in timestamps.items():
        t = ET.SubElement(ai, "timestamp")
        t.set("name", ts_name)
        t.set("format", "TimeStampKnown")
        t.set("formattedTimestamp", ts_val)
        t.text = ts_val

    # metadata section="File"
    m1 = ET.SubElement(f, "metadata")
    m1.set("section", "File")
    _meta_item(m1, "Local Path", local_path)
    _meta_item(m1, "SHA256", sha256)
    _meta_item(m1, "MD5", md5)
    _meta_item(m1, "Tags", tag)

    # metadata section="MetaData"
    m2 = ET.SubElement(f, "metadata")
    m2.set("section", "MetaData")
    for k, v in timestamps.items():
        _meta_item(m2, f"CoreFileSystemFileSystemNode{k}Time", v)

    # EXIF metadata if present
    if exif:
        m3 = ET.SubElement(f, "metadata")
        m3.set("section", "MetaData")
        m3.set("group", "EXIF")
        for k, v in exif.items():
            _meta_item(m3, k, v)

    return f


def _meta_item(parent: ET.Element, name: str, value: str) -> ET.Element:
    item = ET.SubElement(parent, "item")
    item.set("name", name)
    item.set("systemtype", "System.String")
    item.text = f"<![CDATA[{value}]]>"
    return item


def _build_chat_model(
    chat: dict, base: datetime, chat_files: list[dict]
) -> list[ET.Element]:
    """Build Chat model elements from a conversation."""
    models = []
    for i, (direction, text, offset) in enumerate(chat["messages"]):
        m = ET.Element("model")
        m.set("type", "Chat")
        m.set("id", _uuid())
        m.set("deleted_state", "Intact")
        m.set("decoding_confidence", "High")
        m.set("isrelated", "False")
        m.set("source_index", str(_rng.randint(100000, 999999)))
        m.set("extractionId", "0")

        _field(m, "Source", "String", chat["source"])
        _field(m, "Id", "String", chat["chat_id"])
        _field(m, "StartTime", "TimeStamp", _ts_short(base, offset))

        # Sender
        sender_id = (
            chat["participants"][0]
            if direction == "outgoing"
            else chat["participants"][1]
        )
        _field(m, "Sender", "String", sender_id)

        # Message body
        _field(m, "Body", "String", text)

        # Direction
        _field(
            m,
            "Direction",
            "String",
            "Outgoing" if direction == "outgoing" else "Incoming",
        )

        # Message ID
        _field(m, "MessageId", "String", _uuid())

        models.append(m)
    return models


def _build_call_model(call: tuple, base: datetime) -> ET.Element:
    direction, duration, phone, status = call
    m = ET.Element("model")
    m.set("type", "Call")
    m.set("id", _uuid())
    m.set("deleted_state", "Intact")
    m.set("decoding_confidence", "High")
    m.set("isrelated", "False")
    m.set("source_index", str(_rng.randint(100000, 999999)))
    m.set("extractionId", "0")

    _field(m, "Direction", "String", direction.capitalize())
    _field(m, "Duration", "TimeSpan", duration)
    _field(m, "Status", "String", status.strip())
    _field(m, "TimeStamp", "TimeStamp", _ts_short(base, _rng.randint(100, 500)))

    # Parties
    mmf = ET.SubElement(m, "multiModelField")
    mmf.set("name", "Parties")
    mmf.set("type", "Party")
    p = ET.SubElement(mmf, "model")
    p.set("type", "Party")
    p.set("id", _uuid())
    _field(p, "Identifier", "String", phone)
    _field(p, "Role", "PartyRole", "General")

    return m


def _build_contact_model(contact: dict) -> ET.Element:
    m = ET.Element("model")
    m.set("type", "Contact")
    m.set("id", _uuid())
    m.set("deleted_state", "Intact")
    m.set("decoding_confidence", "High")
    m.set("isrelated", "False")
    m.set("source_index", str(_rng.randint(100000, 999999)))
    m.set("extractionId", "0")

    _field(m, "Type", "String", contact["category"])
    _field(m, "Domain", "String", "Phone")
    _field(m, "Value", "String", contact["phone"])
    _field(m, "Category", "String", contact["category"])

    # Name as multiModelField
    mmf = ET.SubElement(m, "multiModelField")
    mmf.set("name", "Names")
    mmf.set("type", "Name")
    nm = ET.SubElement(mmf, "model")
    nm.set("type", "Name")
    nm.set("id", _uuid())
    _field(nm, "DisplayName", "String", contact["name"])
    _field(nm, "FirstName", "String", contact["name"].split()[0])
    _field(nm, "LastName", "String", " ".join(contact["name"].split()[1:]))

    return m


def _build_location_model(loc: tuple, base: datetime) -> ET.Element:
    lat, lon, addr, offset = loc
    m = ET.Element("model")
    m.set("type", "Location")
    m.set("id", _uuid())
    m.set("deleted_state", "Intact")
    m.set("decoding_confidence", "High")
    m.set("isrelated", "False")
    m.set("source_index", str(_rng.randint(100000, 999999)))
    m.set("extractionId", "0")

    _field(m, "Latitude", "Double", str(lat))
    _field(m, "Longitude", "Double", str(lon))
    _field(m, "Address", "String", addr)
    _field(m, "TimeStamp", "TimeStamp", _ts_short(base, offset))
    _field(m, "Confidence", "Int32", str(_rng.randint(70, 99)))

    return m


def _build_web_model(entry: tuple, base: datetime) -> ET.Element:
    url, title, offset = entry
    m = ET.Element("model")
    m.set("type", "WebBookmark")
    m.set("id", _uuid())
    m.set("deleted_state", "Intact")
    m.set("decoding_confidence", "High")
    m.set("isrelated", "False")
    m.set("source_index", str(_rng.randint(100000, 999999)))
    m.set("extractionId", "0")

    _field(m, "Title", "String", title)
    _field(m, "Url", "String", url)
    _field(m, "TimeStamp", "TimeStamp", _ts_short(base, offset))

    return m


def _field(parent: ET.Element, name: str, ftype: str, value: str) -> ET.Element:
    f = ET.SubElement(parent, "field")
    f.set("name", name)
    f.set("type", ftype)
    v = ET.SubElement(f, "value")
    v.set("type", ftype)
    if ftype == "TimeStamp":
        v.set("format", "TimeStampKnown")
        v.set("formattedTimestamp", value)
    v.text = f"<![CDATA[{value}]]>"
    return f


# ── Main generator ─────────────────────────────────────────────────────────
def generate(seed: int = 42, output_dir: str = "./synth/output") -> dict:
    global _rng
    _rng = random.Random(seed)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    ufdr_name = f"synthetic_{seed}_Relatorio"
    ufdr_dir = out / ufdr_name
    files_dir = ufdr_dir / "files"
    db_data_dir = ufdr_dir / "DbData"

    # Create directories
    for d in [
        files_dir / "Image",
        files_dir / "Audio",
        files_dir / "Text",
        files_dir / "Video",
        files_dir / "Document",
        files_dir / "Archives",
        files_dir / "Database",
        files_dir / "Uncategorized",
        db_data_dir,
    ]:
        d.mkdir(parents=True, exist_ok=True)

    # ── Generate file entries ──────────────────────────────────────────────
    fs_id = _uuid()
    fs_name = f"android_{OWNER['phone']}"
    all_files = []
    file_entries = []

    # Images
    for i in range(8):
        fname = f"IMG_{20260300 + i:08d}_{i:04d}.jpg"
        data = _make_image_bytes(seed + i)
        sha = _sha256(data)
        md = _md5(data)
        (files_dir / "Image" / fname).write_bytes(data)
        ts_base = _ts_short(BASE_DATE, i * 30)
        file_entries.append(
            {
                "id": _uuid(),
                "fs": fs_name,
                "fsid": fs_id,
                "path": f"/storage/emulated/0/DCIM/Camera/{fname}",
                "name": fname,
                "size": len(data),
                "tag": "Image",
                "local_path": f"files/Image/{fname}",
                "sha256": sha,
                "md5": md,
                "timestamps": {
                    "CreationTime": ts_base,
                    "ModifyTime": ts_base,
                    "AccessTime": ts_base,
                },
                "exif": {
                    "ExifEnumDateTimeOriginal": ts_base,
                    "ExifEnumMake": _rng.choice(["Samsung", "Apple", "Xiaomi"]),
                    "ExifEnumModel": _rng.choice(
                        ["Galaxy S23", "iPhone 14", "Redmi Note 12"]
                    ),
                    "ExifEnumPixelXDimension": str(_rng.choice([1920, 4032, 3024])),
                    "ExifEnumPixelYDimension": str(_rng.choice([1080, 3024, 4032])),
                },
            }
        )

    # Audio
    for i in range(4):
        fname = f"AUD_{20260300 + i:08d}_{i:04d}.opus"
        data = _make_audio_stub(seed + 100 + i)
        sha = _sha256(data)
        md = _md5(data)
        (files_dir / "Audio" / fname).write_bytes(data)
        ts_base = _ts_short(BASE_DATE, i * 60 + 500)
        file_entries.append(
            {
                "id": _uuid(),
                "fs": fs_name,
                "fsid": fs_id,
                "path": f"/storage/emulated/0/WhatsApp/Media/WhatsApp Audio/{fname}",
                "name": fname,
                "size": len(data),
                "tag": "Audio",
                "local_path": f"files/Audio/{fname}",
                "sha256": sha,
                "md5": md,
                "timestamps": {"CreationTime": ts_base, "ModifyTime": ts_base},
            }
        )

    # Video
    for i in range(2):
        fname = f"VID_{20260300 + i:08d}_{i:04d}.mp4"
        data = _make_video_stub(seed + 200 + i)
        sha = _sha256(data)
        md = _md5(data)
        (files_dir / "Video" / fname).write_bytes(data)
        ts_base = _ts_short(BASE_DATE, i * 120 + 600)
        file_entries.append(
            {
                "id": _uuid(),
                "fs": fs_name,
                "fsid": fs_id,
                "path": f"/storage/emulated/0/DCIM/Camera/{fname}",
                "name": fname,
                "size": len(data),
                "tag": "Video",
                "local_path": f"files/Video/{fname}",
                "sha256": sha,
                "md5": md,
                "timestamps": {"CreationTime": ts_base, "ModifyTime": ts_base},
            }
        )

    # Documents
    for ext, tag in [(".pdf", "Document"), (".txt", "Text"), (".csv", "Text")]:
        fname = f"doc_{_rng.randint(1000, 9999)}{ext}"
        data = _make_document_stub(ext)
        sha = _sha256(data)
        md = _md5(data)
        subdir = "Document" if ext == ".pdf" else "Text"
        (files_dir / subdir / fname).write_bytes(data)
        ts_base = _ts_short(BASE_DATE, _rng.randint(0, 500))
        file_entries.append(
            {
                "id": _uuid(),
                "fs": fs_name,
                "fsid": fs_id,
                "path": f"/storage/emulated/0/Download/{fname}",
                "name": fname,
                "size": len(data),
                "tag": tag,
                "local_path": f"files/{subdir}/{fname}",
                "sha256": sha,
                "md5": md,
                "timestamps": {"CreationTime": ts_base, "ModifyTime": ts_base},
            }
        )

    # ── Build report.xml ──────────────────────────────────────────────────
    project = ET.Element("project")
    project.set("xmlns", NS)
    project.set("id", _uuid())
    project.set("name", "synthetic")
    project.set("reportVersion", "8.5")
    project.set("licenseID", f"SYNTH-{seed:06d}")
    project.set("containsGarbage", "False")
    project.set("extractionType", "Legacy")
    project.set("NodeCount", str(len(file_entries)))
    project.set(
        "ModelCount",
        str(
            sum(len(c["messages"]) for c in WHATSAPP_CHATS)
            + len(SMS_MESSAGES)
            + len(CALL_LOG)
            + len(CONTACTS)
            + len(LOCATIONS)
            + len(WEB_HISTORY)
        ),
    )

    # sourceExtractions
    se = ET.SubElement(project, "sourceExtractions")
    ei = ET.SubElement(se, "extractionInfo")
    ei.set("id", "0")
    ei.set("name", "Legacy")
    ei.set("type", "Legacy")
    ei.set("deviceName", OWNER["name"])
    ei.set("fullName", f"Android - {OWNER['name']}")
    ei.set("index", "0")
    ei.set("IsPartialData", "False")
    ei.set("IsStoppedByUser", "False")
    ei.set("IsTriageExtraction", "False")
    ei.set("IsSelectiveExtraction", "False")

    # caseInformation
    ci = ET.SubElement(project, "caseInformation")
    for field_name, field_type in [
        ("Nome do examinador", "ExaminerName"),
        ("Nome do caso", "CaseName"),
        ("Numero do caso", "CaseNumber"),
        ("Numero de evidencia", "EvidenceNumber"),
        ("Departamento", "Department"),
        ("Organizacao", "Organization"),
        ("Investigador", "Investigator"),
        ("Tipo de crime", "CrimeType"),
        ("Anotacoes", "Notes"),
    ]:
        key = {
            "Nome do examinador": "examiner",
            "Nome do caso": "case_name",
            "Numero do caso": "case_number",
            "Numero de evidencia": "evidence_number",
            "Departamento": "department",
            "Organizacao": "organization",
            "Investigador": "investigator",
            "Tipo de crime": "crime_type",
            "Anotacoes": "notes",
        }[field_name]
        f = ET.SubElement(ci, "field")
        f.set("name", field_name)
        f.set("isSystem", "True")
        f.set("isRequired", "False")
        f.set("fieldType", field_type)
        f.set("multipleLines", "False" if field_type != "Notes" else "True")
        f.text = CASE[key]

    # metadata — use deterministic "now" from base date + seed offset
    synth_now = BASE_DATE + timedelta(minutes=seed * 100)
    md_section1 = ET.SubElement(project, "metadata")
    for name, value in [
        ("DeviceInfoCreationTime", synth_now.strftime("%m/%d/%Y %H:%M:%S")),
        ("UFED_PA_Version", "10.7.1.5013"),
        ("UfdrLanguage", "pt-BR"),
        ("SourceProjectId", project.get("id")),
    ]:
        item = ET.SubElement(md_section1, "item")
        item.set("name", name)
        item.set("systemtype", "System.String")
        item.text = value

    md_section2 = ET.SubElement(project, "metadata")
    for name, value in [
        (
            "DeviceInfoExtractionDecodingDateTime",
            synth_now.strftime("%m/%d/%Y %H:%M:%S"),
        ),
        ("DeviceInfoSelectedDeviceName", OWNER["name"]),
        ("DeviceInfoSelectedManufacturer", "Samsung"),
        ("Time zone settings (ID)", "_America/Sao_Paulo"),
    ]:
        item = ET.SubElement(md_section2, "item")
        item.set("name", name)
        item.set("systemtype", "System.String")
        item.text = value

    # images (source extraction reference)
    imgs = ET.SubElement(project, "images")
    img = ET.SubElement(imgs, "image")
    img.set("key", "Pasta")
    img.set("path", "Extraction")
    img.set("size", str(sum(f["size"] for f in file_entries)))
    img.set("type", "File")
    img.set("verify", "Verified")
    img.set("extractionId", "0")

    # MalwareScanner
    ms = ET.SubElement(project, "MalwareScanner")
    ms.set("ScanPerformed", "False")

    # taggedFiles
    tf = ET.SubElement(project, "taggedFiles")
    for fe in file_entries:
        file_el = _build_file_xml(
            fe["id"],
            fe["fs"],
            fe["fsid"],
            fe["path"],
            fe["name"],
            fe["size"],
            fe["tag"],
            fe["local_path"],
            fe["sha256"],
            fe["md5"],
            fe["timestamps"],
            fe.get("exif"),
        )
        tf.append(file_el)

    # decodedData
    dd = ET.SubElement(project, "decodedData")

    # Chat modelType
    chat_mt = ET.SubElement(dd, "modelType")
    chat_mt.set("type", "Chat")
    for chat in WHATSAPP_CHATS:
        for m in _build_chat_model(chat, BASE_DATE, file_entries):
            chat_mt.append(m)

    # Call modelType
    call_mt = ET.SubElement(dd, "modelType")
    call_mt.set("type", "Call")
    for call in CALL_LOG:
        call_mt.append(_build_call_model(call, BASE_DATE))

    # Contact modelType
    contact_mt = ET.SubElement(dd, "modelType")
    contact_mt.set("type", "Contact")
    for contact in CONTACTS:
        contact_mt.append(_build_contact_model(contact))

    # Location modelType
    loc_mt = ET.SubElement(dd, "modelType")
    loc_mt.set("type", "Location")
    for loc in LOCATIONS:
        loc_mt.append(_build_location_model(loc, BASE_DATE))

    # WebBookmark modelType
    web_mt = ET.SubElement(dd, "modelType")
    web_mt.set("type", "WebBookmark")
    for entry in WEB_HISTORY:
        web_mt.append(_build_web_model(entry, BASE_DATE))

    # extraInfos
    ei_section = ET.SubElement(project, "extraInfos")

    # Write report.xml
    rough = ET.tostring(project, encoding="unicode", xml_declaration=False)
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding=None)
    # Remove extra XML declaration from minidom
    lines = pretty.split("\n")
    if lines[0].startswith("<?xml"):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    report_xml = "\n".join(lines)
    (ufdr_dir / "report.xml").write_text(report_xml, encoding="utf-8")

    # ── settings.json ──────────────────────────────────────────────────────
    settings = {
        "Version": "1.0",
        "ShowAllItems": True,
        "MergeSingleProject": False,
        "SingleProjectRemoveDuplicates": False,
        "TimeStampCreated": True,
        "TimeStampCaptured": True,
        "TimeStampModified": True,
        "TimeStampAccessed": True,
        "TimeStampDeleted": True,
        "TimeStampChanged": True,
        "DataFileImage": True,
        "DataFileAudio": True,
        "DataFileVideo": True,
        "ShowActivitiesModel": True,
        "ShowAppGenieModels": True,
        "ShowDeviceEventsModel": True,
    }
    (ufdr_dir / "settings.json").write_text(json.dumps(settings, indent=2))

    # ── DbData/database.json ──────────────────────────────────────────────
    db_json = {
        "CaseId": project.get("id"),
        "DeviceId": fs_id,
        "SourceExtractionIds": [_uuid()],
        "DatabaseVersion": "10.7.1.5013",
        "ActiveWatchListIds": [],
    }
    (db_data_dir / "database.json").write_text(json.dumps(db_json, indent=2))

    # ── Ground truth (gabarito) ───────────────────────────────────────────
    gabarito = {
        "seed": seed,
        "case": CASE,
        "owner": OWNER,
        "contacts": CONTACTS,
        "whatsapp_chats": [],
        "sms_messages": [],
        "call_log": [],
        "locations": [],
        "web_history": [],
        "media_files": [],
        "key_facts": [],
    }

    # Chat facts
    for chat in WHATSAPP_CHATS:
        chat_data = {
            "chat_id": chat["chat_id"],
            "chat_name": chat["chat_name"],
            "source": chat["source"],
            "message_count": len(chat["messages"]),
            "participants": chat["participants"],
            "messages": [],
        }
        for direction, text, offset in chat["messages"]:
            chat_data["messages"].append(
                {
                    "direction": direction,
                    "text": text,
                    "timestamp_offset": offset,
                    "sender": chat["participants"][0]
                    if direction == "outgoing"
                    else chat["participants"][1],
                }
            )
        gabarito["whatsapp_chats"].append(chat_data)

    # SMS facts
    for direction, text, offset in SMS_MESSAGES:
        gabarito["sms_messages"].append(
            {
                "direction": direction,
                "text": text,
                "timestamp_offset": offset,
            }
        )

    # Call facts
    for direction, duration, phone, status in CALL_LOG:
        gabarito["call_log"].append(
            {
                "direction": direction,
                "duration": duration,
                "phone": phone,
                "status": status.strip(),
            }
        )

    # Location facts
    for lat, lon, addr, offset in LOCATIONS:
        gabarito["locations"].append(
            {
                "latitude": lat,
                "longitude": lon,
                "address": addr,
                "timestamp_offset": offset,
            }
        )

    # Web history facts
    for url, title, offset in WEB_HISTORY:
        gabarito["web_history"].append(
            {
                "url": url,
                "title": title,
                "timestamp_offset": offset,
            }
        )

    # Media file facts
    for fe in file_entries:
        gabarito["media_files"].append(
            {
                "name": fe["name"],
                "tag": fe["tag"],
                "sha256": fe["sha256"],
                "size": fe["size"],
            }
        )

    # Key facts (golden set ground truth)
    gabarito["key_facts"] = [
        {
            "id": "KF001",
            "fact": "Carlos comprou 5g de maconha por R$ 4000",
            "type": "drug_deal",
            "evidence": ["WhatsApp chat com Ana Paula, msg 'O pacote ta pronto'"],
        },
        {
            "id": "KF002",
            "fact": "Ana Paula aumentou o preco para R$ 5000",
            "type": "drug_deal",
            "evidence": ["WhatsApp chat com Ana Paula, msg 'agora e 5k'"],
        },
        {
            "id": "KF003",
            "fact": "Entrega combinada no parking do shopping as 8h",
            "type": "drug_deal",
            "evidence": [
                "WhatsApp chat com Ana Paula, msg '8h no parking do shopping'"
            ],
        },
        {
            "id": "KF004",
            "fact": "Marcos passou contato de BH: 3198877665 (Joao)",
            "type": "contact",
            "evidence": ["WhatsApp chat com Marcos, msg 'Numero: 3198877665'"],
        },
        {
            "id": "KF005",
            "fact": "Carlos pediu para enviar pix pela diferenca de preco",
            "type": "payment",
            "evidence": ["WhatsApp chat com Ana Paula, msg 'Vou mandar hoje a noite'"],
        },
        {
            "id": "KF006",
            "fact": "Reuniao sexta-feira as 20h no apartamento",
            "type": "meeting",
            "evidence": ["WhatsApp grupo G. Operacoes, msg 'reunião sexta as 20h'"],
        },
        {
            "id": "KF007",
            "fact": "Carlos visitou Avenida Paulista multiple times",
            "type": "location",
            "evidence": ["GPS coordinates at Avenida Paulista, 1000"],
        },
        {
            "id": "KF008",
            "fact": "Carlos buscou 'ponto de encontro seguro' no Google",
            "type": "web_search",
            "evidence": ["Web history: 'ponto de encontro seguro'"],
        },
        {
            "id": "KF009",
            "fact": "Carlos tem 10 contatos, incluindo familia e servicos",
            "type": "contact",
            "evidence": ["Contacts list"],
        },
        {
            "id": "KF010",
            "fact": "Mensagem da mae: 'Feliz aniversario filho!'",
            "type": "sms",
            "evidence": ["SMS from 5511987654321"],
        },
        {
            "id": "KF011",
            "fact": "Carlos recebeu proposta de emprestimo por SMS",
            "type": "sms",
            "evidence": ["SMS incoming: 'Proposta de emprestimo aprovada'"],
        },
        {
            "id": "KF012",
            "fact": "Carlos ligou para banco (Nubank) por 48 segundos",
            "type": "call",
            "evidence": ["Call to 551140028922, duration 00:00:48"],
        },
        {
            "id": "KF013",
            "fact": "Carlos visitou Netflix e pesquisou filme",
            "type": "web_search",
            "evidence": ["Web history: Netflix browse"],
        },
        {
            "id": "KF014",
            "fact": "Juliana confirmou presenca na reuniao",
            "type": "meeting",
            "evidence": ["WhatsApp grupo G. Operacoes, msg 'Confirmado, estarei la'"],
        },
        {
            "id": "KF015",
            "fact": "Carlos pediu capa de celular para Pedro",
            "type": "personal",
            "evidence": ["WhatsApp chat com Pedro, msg 'vc ainda tem aquela capa'"],
        },
        {
            "id": "KF016",
            "fact": "Carlos trabalha e tem reuniões fora de casa",
            "type": "personal",
            "evidence": [
                "WhatsApp chat com Fernanda, msg 'vou sair com os caras do trabalho'"
            ],
        },
        {
            "id": "KF017",
            "fact": "Carlos mora em Sao Paulo, zona da Paulista",
            "type": "location",
            "evidence": ["Multiple GPS locations near Avenida Paulista"],
        },
        {
            "id": "KF018",
            "fact": "Fernanda e namorada de Carlos",
            "type": "relationship",
            "evidence": ["WhatsApp chat with Fernanda, 'Amor', 'Eu tambem, beijo'"],
        },
        {
            "id": "KF019",
            "fact": "Carlos tem Irmao chamado Ivo",
            "type": "family",
            "evidence": ["Contact 'Ivo - Irmao', call from 5511976543210"],
        },
        {
            "id": "KF020",
            "fact": "Carlos buscou 'comprar celular' e 'ponto de encontro seguro'",
            "type": "web_search",
            "evidence": ["Web history entries"],
        },
    ]

    (out / "synthetic_data.json").write_text(
        json.dumps(gabarito, indent=2, ensure_ascii=False)
    )

    # ── Golden set ─────────────────────────────────────────────────────────
    golden = {
        "version": "1.0",
        "seed": seed,
        "questions": [
            # Recall - WhatsApp chats
            {
                "id": "Q001",
                "query": "Quem e Ana Paula Santos?",
                "expected_recall": ["KF002", "KF003"],
                "category": "person_lookup",
                "difficulty": "easy",
            },
            {
                "id": "Q002",
                "query": "Qual o endereco da entrega combinada?",
                "expected_recall": ["KF003"],
                "category": "fact_retrieval",
                "difficulty": "easy",
            },
            {
                "id": "Q003",
                "query": "Qual foi o valor final combinado para a entrega?",
                "expected_recall": ["KF002"],
                "category": "fact_retrieval",
                "difficulty": "easy",
            },
            {
                "id": "Q004",
                "query": "Carlos combinou entrega com quem?",
                "expected_recall": ["KF001", "KF002", "KF003"],
                "category": "person_lookup",
                "difficulty": "medium",
            },
            {
                "id": "Q005",
                "query": "Qual o numero de telefone do contato em BH?",
                "expected_recall": ["KF004"],
                "category": "fact_retrieval",
                "difficulty": "easy",
            },
            {
                "id": "Q006",
                "query": "Quem e Marcos Vieira para Carlos?",
                "expected_recall": ["KF004"],
                "category": "person_lookup",
                "difficulty": "medium",
            },
            # Recall - Locations
            {
                "id": "Q007",
                "query": "Carlos esteve na Avenida Paulista?",
                "expected_recall": ["KF007", "KF017"],
                "category": "location",
                "difficulty": "easy",
            },
            {
                "id": "Q008",
                "query": "Quais bairros Carlos visitou?",
                "expected_recall": ["KF007", "KF017"],
                "category": "location",
                "difficulty": "medium",
            },
            {
                "id": "Q009",
                "query": "Carlos esteve na Rua Augusta?",
                "expected_recall": [],
                "category": "location",
                "difficulty": "medium",
                "note": "Augusta is in the location data but not in key_facts directly",
            },
            {
                "id": "Q010",
                "query": "Quantas vezes Carlos esteve na Avenida Paulista?",
                "expected_recall": ["KF007"],
                "category": "location",
                "difficulty": "hard",
            },
            # Recall - Web
            {
                "id": "Q011",
                "query": "Carlos buscou algo sobre seguranca no Google?",
                "expected_recall": ["KF008", "KF020"],
                "category": "web_search",
                "difficulty": "medium",
            },
            {
                "id": "Q012",
                "query": "Carlos pesquisou sobre celular no Google?",
                "expected_recall": ["KF020"],
                "category": "web_search",
                "difficulty": "easy",
            },
            {
                "id": "Q013",
                "query": "Carlos acessou Netflix?",
                "expected_recall": ["KF013"],
                "category": "web_search",
                "difficulty": "easy",
            },
            # Recall - Calls
            {
                "id": "Q014",
                "query": "Carlos ligou para o banco? Qual?",
                "expected_recall": ["KF012"],
                "category": "call",
                "difficulty": "medium",
            },
            {
                "id": "Q015",
                "query": "Qual ligacao de Carlos durou mais tempo?",
                "expected_recall": ["KF012"],
                "category": "call",
                "difficulty": "hard",
            },
            {
                "id": "Q016",
                "query": "Carlos recebeu ligacao da mae?",
                "expected_recall": ["KF010"],
                "category": "call",
                "difficulty": "easy",
            },
            # Recall - SMS
            {
                "id": "Q017",
                "query": "Carlos recebeu SMS de emprestimo?",
                "expected_recall": ["KF011"],
                "category": "sms",
                "difficulty": "easy",
            },
            {
                "id": "Q018",
                "query": "A mae de Carlos mandou SMS?",
                "expected_recall": ["KF010"],
                "category": "sms",
                "difficulty": "easy",
            },
            # Recall - Contacts
            {
                "id": "Q019",
                "query": "Quantos contatos Carlos tem no WhatsApp?",
                "expected_recall": ["KF009"],
                "category": "contact",
                "difficulty": "medium",
            },
            {
                "id": "Q020",
                "query": "Carlos tem contato com servicos bancarios?",
                "expected_recall": ["KF009"],
                "category": "contact",
                "difficulty": "medium",
            },
            # Recall - Relationships
            {
                "id": "Q021",
                "query": "Carlos e casado ou namora?",
                "expected_recall": ["KF018"],
                "category": "relationship",
                "difficulty": "easy",
            },
            {
                "id": "Q022",
                "query": "Carlos tem irmao?",
                "expected_recall": ["KF019"],
                "category": "relationship",
                "difficulty": "easy",
            },
            # Recall - Meetings
            {
                "id": "Q023",
                "query": "Carlos marcou reuniao com quem?",
                "expected_recall": ["KF006", "KF014"],
                "category": "meeting",
                "difficulty": "medium",
            },
            {
                "id": "Q024",
                "query": "Quando e onde e a reuniao?",
                "expected_recall": ["KF006"],
                "category": "meeting",
                "difficulty": "easy",
            },
            # Multi-hop
            {
                "id": "Q025",
                "query": "Carlos combinou entrega com Ana Paula e depois marcou reuniao. Quem confirmou presenca?",
                "expected_recall": ["KF003", "KF006", "KF014"],
                "category": "multi_hop",
                "difficulty": "hard",
            },
            {
                "id": "Q026",
                "query": "Carlos buscou 'ponto de encontro seguro' e depois esteve na Avenida Paulista. Ha conexao?",
                "expected_recall": ["KF008", "KF007"],
                "category": "multi_hop",
                "difficulty": "hard",
            },
            {
                "id": "Q027",
                "query": "Carlos pediu pix para Ana Paula e depois ligou para o banco. Qual o nexo temporal?",
                "expected_recall": ["KF005", "KF012"],
                "category": "multi_hop",
                "difficulty": "hard",
            },
            # Negative (should NOT find)
            {
                "id": "Q028",
                "query": "Carlos vendeu armas de fogo?",
                "expected_recall": [],
                "category": "negative",
                "difficulty": "medium",
            },
            {
                "id": "Q029",
                "query": "Carlos viajou para o exterior?",
                "expected_recall": [],
                "category": "negative",
                "difficulty": "medium",
            },
            {
                "id": "Q030",
                "query": "Carlos tem Bitcoin?",
                "expected_recall": [],
                "category": "negative",
                "difficulty": "medium",
            },
            # Complex queries
            {
                "id": "Q031",
                "query": "Descreva a atividade suspeita de Carlos nas ultimas semanas",
                "expected_recall": ["KF001", "KF002", "KF003", "KF004", "KF006"],
                "category": "summary",
                "difficulty": "hard",
            },
            {
                "id": "Q032",
                "query": "Quais sao as pessoas envolvidas na rede de Carlos?",
                "expected_recall": ["KF002", "KF004", "KF006", "KF014"],
                "category": "network",
                "difficulty": "hard",
            },
            {
                "id": "Q033",
                "query": "Carlos usou GPS para planejar algo?",
                "expected_recall": ["KF007", "KF008", "KF017"],
                "category": "multi_hop",
                "difficulty": "hard",
            },
            {
                "id": "Q034",
                "query": "Quais aplicativos Carlos usa no celular?",
                "expected_recall": ["KF013", "KF016"],
                "category": "app_usage",
                "difficulty": "medium",
            },
            {
                "id": "Q035",
                "query": "Carlos recebeu ameacas por mensagem?",
                "expected_recall": [],
                "category": "negative",
                "difficulty": "medium",
            },
            {
                "id": "Q036",
                "query": "Qual o padrao de horario das mensagens de Carlos?",
                "expected_recall": ["KF001", "KF003", "KF006"],
                "category": "pattern",
                "difficulty": "hard",
            },
            {
                "id": "Q037",
                "query": "Carlos tem historico de compras online?",
                "expected_recall": ["KF020"],
                "category": "web_search",
                "difficulty": "medium",
            },
            {
                "id": "Q038",
                "query": "Ha evidencia de lavagem de dinheiro?",
                "expected_recall": [],
                "category": "negative",
                "difficulty": "hard",
            },
            {
                "id": "Q039",
                "query": "Carlos comunica com pessoas de outros estados?",
                "expected_recall": ["KF004"],
                "category": "contact",
                "difficulty": "medium",
            },
            {
                "id": "Q040",
                "query": "Qual a frequencia de encontros presenciais de Carlos?",
                "expected_recall": ["KF003", "KF006"],
                "category": "pattern",
                "difficulty": "hard",
            },
        ],
    }

    (out / "golden_set.json").write_text(
        json.dumps(golden, indent=2, ensure_ascii=False)
    )

    # ── Create .ufdr ZIP ──────────────────────────────────────────────────
    import zipfile

    ufdr_path = out / f"synthetic_{seed}.ufdr"
    # Deterministic ZIP: set all timestamps to epoch for reproducibility
    deterministic_ts = (1980, 1, 1, 0, 0, 0)
    with zipfile.ZipFile(ufdr_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ufdr_dir):
            for file in sorted(files):
                file_path = Path(root) / file
                arcname = file_path.relative_to(out)
                info = zipfile.ZipInfo(str(arcname), date_time=deterministic_ts)
                info.compress_type = zipfile.ZIP_DEFLATED
                data = file_path.read_bytes()
                zf.writestr(info, data)

    # ── Summary ────────────────────────────────────────────────────────────
    summary = {
        "seed": seed,
        "output_dir": str(out),
        "ufdr_path": str(ufdr_path),
        "report_xml": str(ufdr_dir / "report.xml"),
        "golden_set": str(out / "golden_set.json"),
        "gabarito": str(out / "synthetic_data.json"),
        "stats": {
            "files": len(file_entries),
            "whatsapp_chats": len(WHATSAPP_CHATS),
            "whatsapp_messages": sum(len(c["messages"]) for c in WHATSAPP_CHATS),
            "sms_messages": len(SMS_MESSAGES),
            "calls": len(CALL_LOG),
            "contacts": len(CONTACTS),
            "locations": len(LOCATIONS),
            "web_history": len(WEB_HISTORY),
            "images": sum(1 for f in file_entries if f["tag"] == "Image"),
            "audio": sum(1 for f in file_entries if f["tag"] == "Audio"),
            "video": sum(1 for f in file_entries if f["tag"] == "Video"),
            "golden_questions": len(golden["questions"]),
            "key_facts": len(gabarito["key_facts"]),
        },
    }

    (out / "summary.json").write_text(json.dumps(summary, indent=2))

    return summary


# ── CLI ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="SOKOL synthetic UFDR generator")
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed (default: 42)"
    )
    parser.add_argument(
        "--output", type=str, default="./synth/output", help="Output directory"
    )
    args = parser.parse_args()

    summary = generate(seed=args.seed, output_dir=args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
