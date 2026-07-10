"""SOKOL WhatsApp parser — Chat/InstantMessage model → messages + events."""

from __future__ import annotations

from .contract import (
    ParseResult,
    ParsedMessage,
    ParsedEvent,
    ParseError,
    extract_field,
    extract_participants,
    parse_ts,
)


def parse_whatsapp(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")
    source = extract_field(model, "Source") or "WhatsApp"
    chat_id = extract_field(model, "Id") or ""
    raw_ts = extract_field(model, "StartTime")
    start_time, tz_orig = parse_ts(raw_ts)
    sender_id = extract_field(model, "Sender") or extract_field(model, "From")
    body = extract_field(model, "Body") or extract_field(model, "Text") or ""
    direction = extract_field(model, "Direction") or ""
    message_id = extract_field(model, "MessageId") or extract_field(model, "Id")

    if not body:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="Chat",
                error="Empty message body",
                recoverable=True,
            )
        )
        return result

    dir_normalized = (
        "outgoing" if direction.lower() in ("outgoing", "sent") else "incoming"
    )

    participants = extract_participants(model)
    chat_name = extract_field(model, "ChatName") or chat_id

    counterpart = None
    if participants:
        ids = [p["identifier"] for p in participants if p.get("identifier")]
        if sender_id and sender_id in ids:
            other = [i for i in ids if i != sender_id]
            counterpart = other[0] if other else None
        elif ids:
            counterpart = ids[-1]

    msg = ParsedMessage(
        device_id=device_id,
        app=source,
        chat_id=chat_id,
        sender=sender_id,
        counterpart=counterpart,
        ts=start_time,
        direction=dir_normalized,
        text=body,
        meta={
            "model_id": model_id,
            "chat_name": chat_name,
            "participants": [p.get("identifier") for p in participants],
        },
    )
    result.messages.append(msg)

    actor_name = next(
        (
            p.get("name") or p.get("identifier")
            for p in participants
            if p.get("identifier") == sender_id
        ),
        sender_id,
    )
    summary = f"[{source}] {actor_name}: {body[:120]}"
    if len(body) > 120:
        summary += "..."

    evt = ParsedEvent(
        device_id=device_id,
        ts=start_time,
        tz_original=tz_orig,
        kind="message",
        actor=actor_name or sender_id,
        counterpart=counterpart,
        app=source,
        ref_table="messages",
        ref_id=None,
        summary=summary,
        meta={"chat_id": chat_id, "direction": dir_normalized},
    )
    result.events.append(evt)

    # Emit entities for participants
    for p in participants:
        identifier = p.get("identifier")
        name = p.get("name")
        if identifier:
            kind = "phone" if identifier.replace("+", "").isdigit() else "email"
            result.entities.append(
                {
                    "kind": kind,
                    "value": identifier,
                    "display_name": name,
                    "meta": {"source": source, "chat_id": chat_id},
                }
            )

    return result
