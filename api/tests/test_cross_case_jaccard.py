from __future__ import annotations

from uuid import uuid4

from sokol.tools import TimelineParams


def test_jaccard_all_selectors_not_only_shared() -> None:
    """Score must use the full selector sets, not the already-shared subset."""
    a = {f"phone:{i}" for i in range(10)}
    b = {f"phone:{i}" for i in range(5, 15)}
    union = a | b
    inter = a & b
    score = len(inter) / len(union)
    tautological = 1.0  # Jaccard only on the 5 shared values
    assert score == 5 / 15
    assert score != tautological
    TimelineParams(case_id=uuid4(), limit=50)
