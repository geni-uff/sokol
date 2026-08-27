"""Materialize agenda Contacts from phone/email observables.

WhatsApp/iCloud often land as `phone` entities with a display_name (push name)
and no Cellebrite Contact model. This module upserts `person` + `contact_of`.

Author: Matheus C. Pestana
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

_JUNK_TOKENS = {
    "claro",
    "ifood",
    "unknown",
    "desconhecido",
    "sem nome",
}

_JID_SUFFIX = re.compile(
    r"@(s\.whatsapp\.net|g\.us|lid|broadcast|whatsapp\.net)$",
    re.IGNORECASE,
)
_DIGITS = re.compile(r"\D+")


def normalize_jid(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    raw = _JID_SUFFIX.sub("", raw)
    return raw.strip()


def _digit_count(value: str) -> int:
    return sum(ch.isdigit() for ch in value)


def is_junk_observable(kind: str, value: str, display_name: str | None) -> bool:
    """Skip tokens that are not a real phone/email (claro, ifood, status@br)."""
    val = (value or "").strip()
    name = (display_name or "").strip().lower()
    if name in _JUNK_TOKENS:
        return True
    lowered = val.lower()
    if lowered in _JUNK_TOKENS:
        return True
    if kind == "email":
        if "@" not in val:
            return True
        local, _, domain = val.partition("@")
        if domain in ("br", "com") and len(local) < 8:
            return True
        if len(val) < 8:
            return True
        return False
    if kind == "phone":
        return _digit_count(normalize_jid(val)) < 8
    return True


def person_key(display_name: str | None, normalized_value: str) -> str:
    name = (display_name or "").strip()
    if (
        name
        and name.lower() not in _JUNK_TOKENS
        and len(name) >= 2
        and any(ch.isalnum() for ch in name)
    ):
        return name
    return normalized_value


def materialize_agenda_contacts(db: Session, case_id: UUID | str) -> dict[str, int]:
    """Create person entities + contact_of links from phone/email observables."""
    rows = db.execute(
        text("""
            SELECT id, kind, value, display_name
            FROM entities
            WHERE case_id = :cid AND kind IN ('phone', 'email')
        """),
        {"cid": case_id},
    ).mappings().all()

    existing_people = db.execute(
        text("""
            SELECT id, value, display_name
            FROM entities
            WHERE case_id = :cid AND kind = 'person'
        """),
        {"cid": case_id},
    ).mappings().all()

    people_by_value: dict[str, UUID] = {}
    people_by_name: dict[str, UUID] = {}
    for p in existing_people:
        pid = p["id"] if isinstance(p["id"], UUID) else UUID(str(p["id"]))
        val = (p["value"] or "").strip()
        dn = (p["display_name"] or "").strip()
        if val:
            people_by_value[val.lower()] = pid
        if dn:
            people_by_name[dn.lower()] = pid

    existing_links = db.execute(
        text("""
            SELECT src_id, dst_id
            FROM entity_links
            WHERE case_id = :cid AND kind = 'contact_of'
        """),
        {"cid": case_id},
    ).fetchall()
    linked = {(str(r[0]), str(r[1])) for r in existing_links}

    now = datetime.now(timezone.utc)
    persons_created = 0
    links_created = 0

    for row in rows:
        kind = row["kind"]
        value = row["value"] or ""
        display = row["display_name"]
        if is_junk_observable(kind, value, display):
            continue

        normalized = normalize_jid(value) if kind == "phone" else value.strip().lower()
        if not normalized:
            continue

        key = person_key(display, normalized)
        key_l = key.lower()
        person_id = people_by_name.get(key_l) or people_by_value.get(key_l)

        if person_id is None:
            person_id = uuid4()
            db.execute(
                text("""
                    INSERT INTO entities (id, case_id, kind, value, display_name, meta, created_at)
                    VALUES (:id, :cid, 'person', :value, :name, CAST(:meta AS jsonb), :now)
                """),
                {
                    "id": person_id,
                    "cid": case_id,
                    "value": key,
                    "name": key,
                    "meta": json.dumps({"source": "agenda_backfill"}),
                    "now": now,
                },
            )
            people_by_value[key_l] = person_id
            people_by_name[key_l] = person_id
            persons_created += 1

        dst_id = row["id"]
        pair = (str(person_id), str(dst_id))
        if pair in linked:
            continue
        db.execute(
            text("""
                INSERT INTO entity_links (id, case_id, src_id, dst_id, kind, weight, confidence, meta, created_at)
                VALUES (:id, :cid, :src, :dst, 'contact_of', 1.0, 1.0, CAST(:meta AS jsonb), :now)
            """),
            {
                "id": uuid4(),
                "cid": case_id,
                "src": person_id,
                "dst": dst_id,
                "meta": json.dumps({"source": "agenda_backfill"}),
                "now": now,
            },
        )
        linked.add(pair)
        links_created += 1

    db.commit()
    return {"persons_created": persons_created, "links_created": links_created}


def list_agenda_contacts(db: Session, case_id: UUID | str) -> list[dict]:
    """Person + linked phones/emails for UI and export."""
    people = db.execute(
        text("""
            SELECT p.id, COALESCE(NULLIF(p.display_name, ''), p.value) AS name
            FROM entities p
            WHERE p.case_id = :cid AND p.kind = 'person'
            ORDER BY name NULLS LAST, p.id
        """),
        {"cid": case_id},
    ).mappings().all()

    linked = db.execute(
        text("""
            SELECT el.src_id AS person_id, d.kind, d.value, d.display_name
            FROM entity_links el
            JOIN entities d ON d.id = el.dst_id
            WHERE el.case_id = :cid
              AND el.kind = 'contact_of'
              AND d.kind IN ('phone', 'email')
              AND d.value IS NOT NULL
        """),
        {"cid": case_id},
    ).mappings().all()

    by_person: dict[str, dict] = {}
    for p in people:
        pid = str(p["id"])
        by_person[pid] = {
            "id": pid,
            "name": p["name"] or "Unknown",
            "phones": [],
            "emails": [],
        }

    for row in linked:
        pid = str(row["person_id"])
        if pid not in by_person:
            continue
        val = row["value"]
        if row["kind"] == "phone":
            label = normalize_jid(val) or val
            if label not in by_person[pid]["phones"]:
                by_person[pid]["phones"].append(label)
        else:
            if val not in by_person[pid]["emails"]:
                by_person[pid]["emails"].append(val)

    return list(by_person.values())
