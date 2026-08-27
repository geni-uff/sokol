"""Cellebrite <model type="Email"> → Message + Event."""

from __future__ import annotations

from .contract import (
    ParseResult,
    ParsedMessage,
    ParsedEvent,
    ParsedEntity,
    ParseError,
    extract_field,
    parse_ts,
)


def parse_email(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()
    model_id = model.get("id", "")

    body = (
        extract_field(model, "Body")
        or extract_field(model, "Snippet")
        or extract_field(model, "Subject")
        or ""
    )
    subject = extract_field(model, "Subject") or ""
    sender = (
        extract_field(model, "From.Identifier")
        or extract_field(model, "From")
        or extract_field(model, "Sender")
        or ""
    )
    recipient = (
        extract_field(model, "To.Identifier")
        or extract_field(model, "To")
        or extract_field(model, "Recipient")
        or ""
    )
    raw_ts = extract_field(model, "TimeStamp") or extract_field(model, "Date")
    ts, tz_orig = parse_ts(raw_ts)

    if not body and not subject:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="Email",
                error="Empty email body and subject",
                recoverable=True,
            )
        )
        return result

    text = subject
    if body and body != subject:
        text = f"{subject}\n{body}" if subject else body

    msg = ParsedMessage(
        device_id=device_id,
        app="email",
        chat_id=f"email_{sender}_{recipient}" if sender or recipient else None,
        sender=sender or None,
        counterpart=recipient or None,
        ts=ts,
        direction="outgoing" if (extract_field(model, "Status") or "").lower() in (
            "sent",
            "outgoing",
        ) else "incoming",
        text=text[:20000],
        meta={"model_id": model_id, "type": "email", "subject": subject},
    )
    result.messages.append(msg)

    summary = f"[Email] {sender or '?'} → {recipient or '?'}: {subject or body[:80]}"
    result.events.append(
        ParsedEvent(
            device_id=device_id,
            ts=ts,
            tz_original=tz_orig,
            kind="message",
            actor=sender or None,
            counterpart=recipient or None,
            app="email",
            ref_table="messages",
            summary=summary[:200],
            meta={"model_id": model_id, "type": "email"},
        )
    )

    if sender and "@" in sender:
        result.entities.append(
            ParsedEntity(kind="email", value=sender.lower().strip(), display_name=sender)
        )
    if recipient and "@" in recipient:
        result.entities.append(
            ParsedEntity(kind="email", value=recipient.lower().strip(), display_name=recipient)
        )

    return result
