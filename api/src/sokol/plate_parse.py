"""Parse SOKOL plate-service responses."""

from __future__ import annotations

from typing import Any

PLATE_DETECT_PATH = "/api/plate/detect"


def parse_plate_service_payload(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Map the plate service JSON to rows ready for `plate_detections`."""
    if not payload:
        return []
    rows: list[dict[str, Any]] = []
    for item in payload.get("detections") or []:
        if not isinstance(item, dict):
            continue
        text = str(item.get("plate_text") or "").strip()
        if not text:
            continue
        try:
            confidence = float(item.get("confidence") or 0)
        except (TypeError, ValueError):
            confidence = 0.0
        bbox = item.get("bbox") or []
        if not isinstance(bbox, list):
            bbox = []
        rows.append({"plate_text": text, "confidence": confidence, "bbox": bbox})
    return rows
