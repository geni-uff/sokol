from __future__ import annotations

from worker.parsers.whatsapp import extract_attachment_refs, parse_whatsapp
from worker.ufdr_parser import build_file_sha_lookup, resolve_message_media_hash


def _chat_with_messages(*instant_messages: dict) -> dict:
    return {
        "id": "chat-1",
        "fields": [
            {"name": "Source", "value": "WhatsApp"},
            {"name": "Id", "value": "5511999999999"},
            {"name": "ChatName", "value": "Grupo"},
        ],
        "multiModelFields": [
            {
                "name": "Messages",
                "models": list(instant_messages),
            }
        ],
        "modelFields": [],
    }


def test_media_only_instant_message_is_kept() -> None:
    msg = {
        "id": "im-1",
        "fields": [
            {"name": "Body", "value": ""},
            {"name": "TimeStamp", "value": "2024-03-01T12:00:00+00:00"},
            {"name": "From.Identifier", "value": "5511988887777"},
            {"name": "From.Name", "value": "Ana"},
        ],
        "modelFields": [
            {
                "name": "Attachment",
                "type": "Attachment",
                "model": {
                    "id": "file-42",
                    "type": "Attachment",
                    "fields": [
                        {"name": "Filename", "value": "IMG-2024.jpg"},
                        {"name": "FileId", "value": "file-42"},
                    ],
                    "modelFields": [],
                    "multiModelFields": [],
                },
            }
        ],
        "multiModelFields": [],
    }
    result = parse_whatsapp(_chat_with_messages(msg), device_id="dev")
    assert len(result.messages) == 1
    assert result.messages[0].text is None
    assert result.messages[0].meta["attachment_file_ids"] == ["file-42"]
    assert "IMG-2024.jpg" in result.messages[0].meta["attachment_names"]
    assert "[mídia]" in result.events[0].summary


def test_empty_stub_without_attachment_is_skipped() -> None:
    msg = {
        "id": "im-2",
        "fields": [{"name": "Body", "value": ""}],
        "modelFields": [],
        "multiModelFields": [],
    }
    result = parse_whatsapp(_chat_with_messages(msg), device_id="dev")
    assert result.messages == []


def test_text_plus_attachment_keeps_body() -> None:
    msg = {
        "id": "im-3",
        "fields": [
            {"name": "Body", "value": "olha isso"},
            {"name": "Attachment.Filename", "value": "foto.png"},
            {"name": "TimeStamp", "value": "2024-03-01T12:00:00+00:00"},
            {"name": "From.Identifier", "value": "5511988887777"},
        ],
        "modelFields": [],
        "multiModelFields": [],
    }
    ids, names = extract_attachment_refs(msg)
    assert names == ["foto.png"]
    result = parse_whatsapp(_chat_with_messages(msg), device_id="dev")
    assert result.messages[0].text == "olha isso"
    assert ids == result.messages[0].meta["attachment_file_ids"]


def test_resolve_attachment_by_file_id_then_filename() -> None:
    lookup = build_file_sha_lookup(
        [
            {
                "file_id": "file-42",
                "name": "IMG-2024.jpg",
                "sha256": "a" * 64,
                "local_path": r"files\Image\IMG-2024.jpg",
                "path": "",
            }
        ]
    )
    by_id = resolve_message_media_hash(
        None, {"attachment_file_ids": ["file-42"], "attachment_names": []}, lookup
    )
    by_name = resolve_message_media_hash(
        None, {"attachment_file_ids": ["missing"], "attachment_names": ["IMG-2024.jpg"]}, lookup
    )
    assert by_id == "a" * 64
    assert by_name == "a" * 64
