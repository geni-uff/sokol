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

    # Create the contact entity
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

    # If we have a person name AND a phone/email, create a link
    person_name = names.get("display_name")
    if person_name and value and value != person_name:
        # Link person ↔ contact value
        person_kind = "person"
        result.entities.append(
            ParsedEntity(
                kind=person_kind,
                value=person_name,
                display_name=person_name,
                meta={"source": "Contact", "model_id": model_id},
            )
        )
        result.entity_links.append(
            ParsedEntityLink(
                src_value=person_name,
                src_kind=person_kind,
                dst_value=value,
                dst_kind=entity_kind,
                kind="contact_of",
                meta={"model_id": model_id},
            )
        )

    return result
