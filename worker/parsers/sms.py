"""SOKOL SMS parser — InstantMessage model → messages + events."""

from __future__ import annotations

from .contract import (
    ParseResult,
    ParsedMessage,
    ParsedEvent,
    ParseError,
    extract_field,
    parse_ts,
)


def parse_sms(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")
    body = extract_field(model, "Body") or extract_field(model, "Text") or ""
    direction = extract_field(model, "Direction") or ""
    sender = extract_field(model, "From") or extract_field(model, "Sender") or ""
    recipient = extract_field(model, "To") or ""
    raw_ts = extract_field(model, "TimeStamp") or extract_field(model, "StartTime")
    ts, tz_orig = parse_ts(raw_ts)

    if not body:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="SMS",
                error="Empty SMS body",
                recoverable=True,
            )
        )
        return result

    dir_normalized = (
        "outgoing" if direction.lower() in ("outgoing", "sent") else "incoming"
    )

    counterpart = recipient if dir_normalized == "outgoing" else sender

    msg = ParsedMessage(
        device_id=device_id,
        app="SMS",
        chat_id=f"sms_{counterpart}" if counterpart else None,
        sender=sender,
        counterpart=counterpart,
        ts=ts,
        direction=dir_normalized,
        text=body,
        meta={"model_id": model_id, "type": "sms"},
    )
    result.messages.append(msg)

    evt = ParsedEvent(
        device_id=device_id,
        ts=ts,
        tz_original=tz_orig,
        kind="message",
        actor=sender,
        counterpart=counterpart,
        app="SMS",
        ref_table="messages",
        summary=f"[SMS] {sender} → {counterpart}: {body[:100]}",
        meta={"direction": dir_normalized, "type": "sms"},
    )
    result.events.append(evt)

    return result
