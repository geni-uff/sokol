"""SOKOL Contact parser — Contact model → entities + entity_links."""

from __future__ import annotations

from .contract import (
    ParseResult,
    ParseError,
    ParsedEntity,
    ParsedEntityLink,
    extract_field,
)


def _extract_names(model: dict) -> dict:
    for mmf in model.get("multiModelFields", []):
        if mmf.get("name") == "Names":
            for sub in mmf.get("models", []):
                return {
                    "display_name": extract_field(sub, "DisplayName"),
                    "first_name": extract_field(sub, "FirstName"),
                    "last_name": extract_field(sub, "LastName"),
                }
    return {}


def parse_contact(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")
    contact_type = extract_field(model, "Type") or ""
    domain = extract_field(model, "Domain") or ""
    value = extract_field(model, "Value") or ""
    category = extract_field(model, "Category") or ""
    names = _extract_names(model)

    display_name = names.get("display_name") or value

    if not value and not display_name:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="Contact",
                error="Contact has no value or name",
                recoverable=True,
            )
        )
        return result

    # Determine entity kind from domain
    if domain.lower() == "phone" or (value and value.replace("+", "").isdigit()):
        entity_kind = "phone"
    elif domain.lower() == "email" or (value and "@" in value):
        entity_kind = "email"
    else:
        entity_kind = "person"

    result.entities.append(
        ParsedEntity(
            kind=entity_kind,
            value=value or display_name,
            display_name=display_name,
            meta={
                "model_id": model_id,
                "contact_type": contact_type,
                "category": category,
                "first_name": names.get("first_name"),
                "last_name": names.get("last_name"),
                "domain": domain,
            },
        )
    )

    # Agenda contact: person + phone/email even when Cellebrite has no Names block
    # (WhatsApp push name, iCloud handle, or the number itself as the name).
    if entity_kind in ("phone", "email"):
        person_name = (names.get("display_name") or display_name or value or "").strip()
        if person_name:
            result.entities.append(
                ParsedEntity(
                    kind="person",
                    value=person_name,
                    display_name=person_name,
                    meta={"source": "Contact", "model_id": model_id},
                )
            )
            result.entity_links.append(
                ParsedEntityLink(
                    src_value=person_name,
                    src_kind="person",
                    dst_value=value or display_name,
                    dst_kind=entity_kind,
                    kind="contact_of",
                    meta={"model_id": model_id},
                )
            )

    return result
