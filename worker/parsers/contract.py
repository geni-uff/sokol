"""SOKOL parser contract — common interface for all structured parsers.

Every parser receives a model dict (from report.xml decodedData) and returns
a ParseResult with messages, events, entities, and recoverable errors.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass
class ParsedMessage:
    device_id: str | None = None
    app: str | None = None
    chat_id: str | None = None
    sender: str | None = None
    counterpart: str | None = None
    ts: datetime | None = None
    direction: str | None = None  # "incoming" | "outgoing"
    text: str | None = None
    media_hash: str | None = None
    is_forwarded: bool = False
    meta: dict = field(default_factory=dict)


@dataclass
class ParsedEvent:
    device_id: str | None = None
    ts: datetime | None = None
    tz_original: str | None = None
    kind: str = ""  # "message", "call", "location", "web_visit", etc.
    actor: str | None = None
    counterpart: str | None = None
    app: str | None = None
    ref_table: str = ""  # "messages", "media", etc.
    ref_id: UUID | None = None
    summary: str = ""
    geo_lat: float | None = None
    geo_lon: float | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class ParsedEntity:
    kind: str = ""  # "person", "phone", "email", "contact"
    value: str = ""  # normalized value (phone number, email, etc.)
    display_name: str | None = None
    meta: dict = field(default_factory=dict)


@dataclass
class ParsedEntityLink:
    src_value: str = ""  # value of source entity (matched later)
    src_kind: str = ""  # kind of source entity
    dst_value: str = ""  # value of destination entity
    dst_kind: str = ""  # kind of destination entity
    kind: str = ""  # relationship type: "contact_of", "participant", etc.
    weight: float = 1.0
    meta: dict = field(default_factory=dict)


@dataclass
class ParseError:
    model_id: str
    model_type: str
    error: str
    recoverable: bool = True


@dataclass
class ParseResult:
    messages: list[ParsedMessage] = field(default_factory=list)
    events: list[ParsedEvent] = field(default_factory=list)
    errors: list[ParseError] = field(default_factory=list)
    artifact_hashes: list[dict] = field(
        default_factory=list
    )  # [{sha256, mime_type, size, local_path}]
    entities: list[ParsedEntity] = field(default_factory=list)
    entity_links: list[ParsedEntityLink] = field(default_factory=list)


# ── Shared helpers ──────────────────────────────────────────────────────────


def extract_field(model: dict, name: str) -> str | None:
    """Extract a scalar field value from a model dict."""
    for f in model.get("fields", []):
        if f.get("name") == name:
            return f.get("value")
    return None


def extract_participants(model: dict, field_name: str = "Participants") -> list[dict]:
    """Extract participants/parties from multiModelFields."""
    items = []
    for mmf in model.get("multiModelFields", []):
        if mmf.get("name") == field_name:
            for sub in mmf.get("models", []):
                items.append(
                    {
                        "identifier": extract_field(sub, "Identifier"),
                        "role": extract_field(sub, "Role"),
                        "name": extract_field(sub, "Name"),
                    }
                )
    return items


def parse_ts(raw: str | None) -> tuple[datetime | None, str | None]:
    """Parse ISO 8601 timestamp, returning (datetime, tz_original_string).

    Preserves timezone offset info. Returns tz_original as "+00:00" etc.
    """
    if not raw:
        return None, None
    try:
        from datetime import timezone as tz

        clean = raw.strip()
        tz_original = None

        # Extract timezone offset if present
        for suffix in (
            "+00:00",
            "+05:30",
            "-03:00",
            "+01:00",
            "+02:00",
            "+03:00",
            "+04:00",
            "+05:00",
            "+06:00",
            "+07:00",
            "+08:00",
            "+09:00",
            "+10:00",
            "+11:00",
            "+12:00",
            "-01:00",
            "-02:00",
            "-04:00",
            "-05:00",
            "-06:00",
            "-07:00",
            "-08:00",
            "-09:00",
            "-10:00",
            "-11:00",
            "-12:00",
        ):
            if clean.endswith(suffix):
                tz_original = suffix
                break

        if clean.endswith("Z"):
            tz_original = "+00:00"
            clean = clean[:-1] + "+00:00"

        # Strip milliseconds
        clean = clean.replace(".000", "").replace(".000+00:00", "+00:00")

        dt = datetime.fromisoformat(clean)

        # If datetime has tzinfo, convert to UTC and strip it for storage
        if dt.tzinfo is not None:
            dt_utc = dt.astimezone(tz.utc).replace(tzinfo=None)
            return dt_utc, tz_original or dt.strftime("%z")
        else:
            return dt, tz_original
    except (ValueError, TypeError):
        return None, None
