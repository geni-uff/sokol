"""Chronological sample batches skip hashes already seen."""

from __future__ import annotations

from datetime import datetime, timedelta

from sokol.pipeline_sample import next_unseen


def _item(h: str, ts: datetime) -> dict:
    return {"hash": h, "media_ts": ts, "mime_type": "image/jpeg", "storage_ref": {}}


def test_next_unseen_keeps_chronological_order() -> None:
    t0 = datetime(2024, 1, 1)
    items = [_item(f"h{i}", t0 + timedelta(minutes=i)) for i in range(5)]
    first = next_unseen(items, set(), 2)
    assert [i["hash"] for i in first] == ["h0", "h1"]

    second = next_unseen(items, {"h0", "h1"}, 2)
    assert [i["hash"] for i in second] == ["h2", "h3"]

    third = next_unseen(items, {"h0", "h1", "h2", "h3"}, 2)
    assert [i["hash"] for i in third] == ["h4"]


def test_next_unseen_skips_holes_in_seen_set() -> None:
    t0 = datetime(2024, 1, 1)
    items = [_item(f"h{i}", t0 + timedelta(minutes=i)) for i in range(4)]
    batch = next_unseen(items, {"h1"}, 2)
    assert [i["hash"] for i in batch] == ["h0", "h2"]


def test_next_unseen_empty_when_exhausted() -> None:
    items = [_item("h0", datetime(2024, 1, 1))]
    assert next_unseen(items, {"h0"}, 20) == []
    assert next_unseen(items, set(), 0) == []
