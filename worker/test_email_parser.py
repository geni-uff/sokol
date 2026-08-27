from __future__ import annotations

from worker.parsers.email import parse_email


def test_parse_email_model_to_message_and_event() -> None:
    model = {
        "id": "e1",
        "fields": [
            {"name": "Subject", "value": "Reunião"},
            {"name": "Body", "value": "Amanhã às 10"},
            {"name": "From", "value": "ana@example.com"},
            {"name": "To", "value": "bob@example.com"},
            {"name": "TimeStamp", "value": "2024-01-02T15:00:00+00:00"},
        ],
    }
    result = parse_email(model, device_id="dev")
    assert len(result.messages) == 1
    assert result.messages[0].app == "email"
    assert "Reunião" in (result.messages[0].text or "")
    assert result.events[0].kind == "message"
    assert result.events[0].app == "email"
    emails = {e.value for e in result.entities}
    assert "ana@example.com" in emails
    assert "bob@example.com" in emails
