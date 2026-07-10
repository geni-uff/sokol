"""SOKOL Location parser — Location model → events with geo coordinates."""

from __future__ import annotations

from datetime import datetime

from .contract import ParseResult, ParsedEvent, ParseError


def _parse_ts(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        # Handle timezone offsets: +00:00, +05:30, etc.
        # Strip milliseconds if present
        clean = raw
        if "+" in clean[10:]:
            # Has timezone offset, parse as-is
            return datetime.fromisoformat(clean)
        elif clean.endswith("Z"):
            return datetime.fromisoformat(clean.replace("Z", "+00:00"))
        else:
            # No timezone, assume UTC
            clean = clean.replace("+00:00", "")
            return datetime.fromisoformat(clean).replace(tzinfo=None)
    except (ValueError, TypeError):
        return None


def _parse_float(raw: str | None) -> float | None:
    if not raw:
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _extract_field(model: dict, name: str) -> str | None:
    for f in model.get("fields", []):
        if f.get("name") == name:
            return f.get("value")
    return None


def parse_location(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")

    # Try direct fields first (Cellebrite UFED standard)
    lat = _parse_float(_extract_field(model, "Latitude"))
    lon = _parse_float(_extract_field(model, "Longitude"))

    # Fallback: try flattened nested fields (Google Warrant Return format)
    # e.g., "Position.Latitude" from <modelField name="Position"><model><field name="Latitude"
    if lat is None:
        lat = _parse_float(_extract_field(model, "Position.Latitude"))
    if lon is None:
        lon = _parse_float(_extract_field(model, "Position.Longitude"))

    address = (
        _extract_field(model, "Address")
        or _extract_field(model, "Name")
        or _extract_field(model, "Position.Name")
        or ""
    )
    ts = _parse_ts(
        _extract_field(model, "TimeStamp")
        or _extract_field(model, "Position.TimeStamp")
    )
    confidence = _extract_field(model, "Confidence") or _extract_field(
        model, "Position.Confidence"
    )

    if lat is None or lon is None:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="Location",
                error="Missing latitude or longitude",
                recoverable=True,
            )
        )
        return result

    summary = f"Localização: {address or f'{lat:.6f}, {lon:.6f}'}"

    evt = ParsedEvent(
        device_id=device_id,
        ts=ts,
        kind="location",
        actor=device_id,
        app="GPS",
        ref_table="events",
        summary=summary,
        geo_lat=lat,
        geo_lon=lon,
        meta={
            "model_id": model_id,
            "address": address,
            "confidence": confidence,
        },
    )
    result.events.append(evt)

    return result
