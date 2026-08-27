"""Pipeline status must not leak jobs across cases."""

from __future__ import annotations

from sokol.jobs import _job_events, emit_progress
from sokol.pipeline import _collect_pipeline_jobs


def test_pipeline_status_filters_by_case_id() -> None:
    _job_events.clear()
    emit_progress("job-a", "yolo", "completed", 1.0, "Done A", case_id="case-a")
    emit_progress("job-b", "asr", "completed", 1.0, "Done B", case_id="case-b")

    only_a = _collect_pipeline_jobs("case-a")
    only_b = _collect_pipeline_jobs("case-b")
    assert [j["job_id"] for j in only_a] == ["job-a"]
    assert [j["job_id"] for j in only_b] == ["job-b"]
    assert _collect_pipeline_jobs("case-z") == []
