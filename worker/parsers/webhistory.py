"""SOKOL WebHistory parser — WebBookmark model → events."""

from __future__ import annotations

from .contract import ParseResult, ParsedEvent, ParseError, extract_field, parse_ts


def parse_webhistory(model: dict, device_id: str = "") -> ParseResult:
    result = ParseResult()

    model_id = model.get("id", "")
    title = extract_field(model, "Title") or ""
    url = extract_field(model, "Url") or extract_field(model, "URL") or ""
    raw_ts = extract_field(model, "TimeStamp") or extract_field(model, "StartTime")
    ts, tz_orig = parse_ts(raw_ts)
    visit_count = extract_field(model, "VisitCount")

    if not url:
        result.errors.append(
            ParseError(
                model_id=model_id,
                model_type="WebBookmark",
                error="Missing URL",
                recoverable=True,
            )
        )
        return result

    summary = f"[Web] {title or url}"
    if len(summary) > 200:
        summary = summary[:197] + "..."

    evt = ParsedEvent(
        device_id=device_id,
        ts=ts,
        tz_original=tz_orig,
        kind="web_visit",
        actor=device_id,
        app="Browser",
        ref_table="events",
        summary=summary,
        meta={
            "model_id": model_id,
            "url": url,
            "title": title,
            "visit_count": visit_count,
        },
    )
    result.events.append(evt)

    return result
