"""SOKOL WhatsApp parser — Chat/InstantMessage model → messages + events.

Cellebrite emits two shapes:
- Chat as a *container*: chat-level fields (Id, Source, Participants) plus a
  multiModelField "Messages" holding nested InstantMessage models.
- Flat Chat/InstantMessage with Body directly on the model (synth generator).
Both are handled here.
"""

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


def _chat_participants(model: dict) -> list[dict]:
    """Participants from the chat-level multiModelField, with owner flag."""
    parts = []
    for mmf in model.get("multiModelFields", []):
        if mmf.get("name") != "Participants":
            continue
        for sub in mmf.get("models", []):
            entry = {"identifier": None, "name": None, "is_owner": False}
            for f in sub.get("fields", []):
                if f["name"] == "Identifier":
                    entry["identifier"] = f["value"] or None
                elif f["name"] == "Name":
                    entry["name"] = f["value"] or None
                elif f["name"] == "IsPhoneOwner":
                    entry["is_owner"] = (f["value"] or "").lower() == "true"
            if entry["identifier"]:
                parts.append(entry)
    return parts


def _nested_messages(model: dict) -> list[dict]:
    """InstantMessage sub-models inside the Chat's Messages multiModelField."""
    out = []
    for mmf in model.get("multiModelFields", []):
        if mmf.get("name") == "Messages":
            out.extend(mmf.get("models", []))
    return out


_ATTACHMENT_CONTAINERS = {
    "attachment",
    "attachments",
    "embeddedfile",
    "embeddedfiles",
    "datafile",
    "datafiles",
    "file",
    "files",
    "sharedfile",
    "sharedfiles",
}

_FILE_ID_KEYS = {"fileid", "attachmentid", "datafileid"}
_PATH_KEYS = {
    "filename",
    "name",
    "url",
    "attachmentextractedpath",
    "extractedpath",
    "localpath",
    "local path",
    "path",
}


def _field_key(name: str) -> str:
    return (name or "").rsplit(".", 1)[-1].replace("_", "").replace(" ", "").lower()


def _is_attachment_container(name: str) -> bool:
    return (name or "").replace("_", "").replace(" ", "").lower() in _ATTACHMENT_CONTAINERS


def extract_attachment_refs(model: dict) -> tuple[list[str], list[str]]:
    """File ids and path/name hints from InstantMessage Attachment models."""
    file_ids: list[str] = []
    names: list[str] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()

    def _add_id(val: str) -> None:
        if val and val not in seen_ids:
            seen_ids.add(val)
            file_ids.append(val)

    def _add_name(val: str) -> None:
        if val and val not in seen_names:
            seen_names.add(val)
            names.append(val)

    def _walk(node: dict, *, in_attachment: bool) -> None:
        if in_attachment:
            _add_id((node.get("id") or "").strip())
        for f in node.get("fields") or []:
            key = _field_key(f.get("name") or "")
            val = (f.get("value") or "").strip()
            if not val:
                continue
            if key in _FILE_ID_KEYS or (in_attachment and key == "id"):
                _add_id(val)
            elif key in _PATH_KEYS and (in_attachment or key != "name"):
                _add_name(val)
            elif key == "attachment":
                _add_id(val)

        for mf in node.get("modelFields") or []:
            nested = mf.get("model") or {}
            child_att = in_attachment or _is_attachment_container(
                mf.get("name") or ""
            ) or _is_attachment_container(nested.get("type") or "")
            if child_att:
                _walk(nested, in_attachment=True)

        for mmf in node.get("multiModelFields") or []:
            child_att = in_attachment or _is_attachment_container(mmf.get("name") or "")
            if not child_att:
                continue
            for sub in mmf.get("models") or []:
                _walk(sub, in_attachment=True)

    _walk(model, in_attachment=False)
    return file_ids, names


def _parse_instant_message(
    msg_model: dict,
    device_id: str,
    chat_id: str,
    chat_source: str,
    chat_name: str,
    participants: list[dict],
) -> ParseResult:
    result = ParseResult()
    model_id = msg_model.get("id", "")

    body = extract_field(msg_model, "Body") or ""
    file_ids, attach_names = extract_attachment_refs(msg_model)
    if not body and not file_ids and not attach_names:
        return result

    source = extract_field(msg_model, "Source") or chat_source or "WhatsApp"
    raw_ts = extract_field(msg_model, "TimeStamp")
    ts, tz_orig = parse_ts(raw_ts)

    # From party is flattened by the extractor as From.<field>
    sender_id = extract_field(msg_model, "From.Identifier")
    sender_name = extract_field(msg_model, "From.Name") or sender_id
    sender_is_owner = (extract_field(msg_model, "From.IsPhoneOwner") or "").lower() == "true"

    direction = "outgoing" if sender_is_owner else "incoming"

    counterpart = None
    other = [p["identifier"] for p in participants if p["identifier"] != sender_id]
    if other:
        counterpart = other[0]

    result.messages.append(
        ParsedMessage(
            device_id=device_id,
            app=source,
            chat_id=chat_id,
            sender=sender_id,
            counterpart=counterpart,
            ts=ts,
            direction=direction,
            text=body or None,
            meta={
                "model_id": model_id,
                "chat_name": chat_name,
                "sender_name": sender_name,
                "status": extract_field(msg_model, "Status"),
                "attachment_file_ids": file_ids,
                "attachment_names": attach_names,
            },
        )
    )

    preview = body[:120] if body else "[mídia]"
    summary = f"[{source}] {sender_name}: {preview}"
    if body and len(body) > 120:
        summary += "..."
    result.events.append(
        ParsedEvent(
            device_id=device_id,
            ts=ts,
            tz_original=tz_orig,
            kind="message",
            actor=sender_name or sender_id,
            counterpart=counterpart,
            app=source,
            ref_table="messages",
            ref_id=None,
            summary=summary,
            meta={"chat_id": chat_id, "direction": direction},
        )
    )
    return result


def _parse_flat(model: dict, device_id: str) -> ParseResult:
    """Legacy/synth shape: Body directly on the Chat/InstantMessage model."""
    result = ParseResult()

    model_id = model.get("id", "")
    source = extract_field(model, "Source") or "WhatsApp"
    chat_id = extract_field(model, "Id") or ""
    raw_ts = extract_field(model, "StartTime") or extract_field(model, "TimeStamp")
    start_time, tz_orig = parse_ts(raw_ts)
    sender_id = extract_field(model, "Sender") or extract_field(model, "From")
    body = extract_field(model, "Body") or extract_field(model, "Text") or ""
    direction = extract_field(model, "Direction") or ""
    file_ids, attach_names = extract_attachment_refs(model)

    if not body and not file_ids and not attach_names:
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

    result.messages.append(
        ParsedMessage(
            device_id=device_id,
            app=source,
            chat_id=chat_id,
            sender=sender_id,
            counterpart=counterpart,
            ts=start_time,
            direction=dir_normalized,
            text=body or None,
            meta={
                "model_id": model_id,
                "chat_name": chat_name,
                "participants": [p.get("identifier") for p in participants],
                "attachment_file_ids": file_ids,
                "attachment_names": attach_names,
            },
        )
    )

    actor_name = next(
        (
            p.get("name") or p.get("identifier")
            for p in participants
            if p.get("identifier") == sender_id
        ),
        sender_id,
    )
    preview = body[:120] if body else "[mídia]"
    summary = f"[{source}] {actor_name}: {preview}"
    if body and len(body) > 120:
        summary += "..."

    result.events.append(
        ParsedEvent(
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
    )

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


def parse_whatsapp(model: dict, device_id: str = "") -> ParseResult:
    nested = _nested_messages(model)
    if not nested:
        return _parse_flat(model, device_id)

    # Chat container: parse every nested InstantMessage with chat context
    result = ParseResult()
    source = extract_field(model, "Source") or "WhatsApp"
    chat_id = extract_field(model, "Id") or model.get("id", "")
    chat_name = extract_field(model, "ChatName") or chat_id
    participants = _chat_participants(model)

    for msg_model in nested:
        sub = _parse_instant_message(
            msg_model, device_id, chat_id, source, chat_name, participants
        )
        result.messages.extend(sub.messages)
        result.events.extend(sub.events)
        result.errors.extend(sub.errors)

    # Entities from chat participants (deduped downstream by kind+value)
    for p in participants:
        identifier = p["identifier"]
        clean = identifier.split("@")[0] if identifier else ""
        kind = "phone" if clean.replace("+", "").isdigit() else "email"
        result.entities.append(
            {
                "kind": kind,
                "value": identifier,
                "display_name": p.get("name"),
                "meta": {"source": source, "chat_id": chat_id},
            }
        )

    return result
