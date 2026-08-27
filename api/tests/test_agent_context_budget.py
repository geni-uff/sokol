from __future__ import annotations

from uuid import uuid4

from sokol.chat import _compact_tool_payload, _estimate_tokens
from sokol.tools import TimelineParams, execute_tool, ToolResult


def test_timeline_limit_clamped_to_50() -> None:
    params = {"limit": 2000}
    result = execute_tool(None, "unknown_tool_xyz", params, uuid4())
    assert result.error

    validated = TimelineParams(case_id=uuid4(), limit=50)
    assert validated.limit == 50


def test_compact_tool_payload_truncates_text_and_rows() -> None:
    result = ToolResult(
        tool_name="query_timeline",
        data=[{"summary": "x" * 2000, "id": str(i)} for i in range(80)],
        sources=[{"ref_table": "events", "ref_id": str(i), "summary": "x" * 200} for i in range(80)],
        count=80,
    )
    payload = _compact_tool_payload(result)
    assert payload["truncated"] is True
    assert len(payload["data"]) == 50
    assert len(payload["data"][0]["summary"]) <= 401
    assert "sources" in payload
    assert "summary" not in payload["sources"][0]


def test_estimate_tokens_grows_with_payload() -> None:
    small = _estimate_tokens([{"role": "user", "content": "oi"}])
    big = _estimate_tokens([{"role": "tool", "content": "a" * 4000}])
    assert big > small
