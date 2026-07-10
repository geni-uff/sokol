"""SOKOL Call parser — Call model → messages (call log) + events."""

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


def _parse_duration(raw: str | None) -> int | None:
    if not raw:
        return None
    parts = raw.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(float(parts[2]))
        elif len(parts) == 2:
            return int(parts[0]) * 60 + int(float(parts[1]))
        return int(float(raw))
    except (ValueError, TypeError):
        return None


def parse_call(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")
    direction = extract_field(model, "Direction") or ""
    duration_str = extract_field(model, "Duration")
    status = extract_field(model, "Status") or ""
    raw_ts = extract_field(model, "TimeStamp") or extract_field(model, "StartTime")
    ts, tz_orig = parse_ts(raw_ts)
    duration = _parse_duration(duration_str)

    parties = extract_participants(model, "Parties")
    phone = parties[0]["identifier"] if parties else ""
    contact_name = parties[0].get("name") if parties else None

    dir_normalized = (
        "outgoing" if direction.lower() in ("outgoing", "dial") else "incoming"
    )

    summary_text = f"Chamada {dir_normalized} {duration_str or ''} ({status})"
    msg = ParsedMessage(
        device_id=device_id,
        app="Phone",
        chat_id=f"call_{phone}" if phone else None,
        sender=phone if dir_normalized == "incoming" else device_id,
        counterpart=phone,
        ts=ts,
        direction=dir_normalized,
        text=summary_text,
        meta={
            "model_id": model_id,
            "type": "call",
            "duration_seconds": duration,
            "duration_raw": duration_str,
            "status": status,
            "contact_name": contact_name,
        },
    )
    result.messages.append(msg)

    evt = ParsedEvent(
        device_id=device_id,
        ts=ts,
        tz_original=tz_orig,
        kind="call",
        actor=phone if dir_normalized == "incoming" else (contact_name or phone),
        counterpart=device_id
        if dir_normalized == "incoming"
        else (contact_name or phone),
        app="Phone",
        ref_table="messages",
        summary=f"[Chamada] {dir_normalized} {contact_name or phone} ({duration_str or '?'})",
        meta={"duration_seconds": duration, "status": status},
    )
    result.events.append(evt)

    # Emit entity for phone
    if phone:
        result.entities.append(
            {
                "kind": "phone",
                "value": phone,
                "display_name": contact_name,
                "meta": {"source": "Phone", "type": "call"},
            }
        )

    return result
