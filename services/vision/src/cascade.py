"""Weapon detection cascade: YOLO26x → YOLO-World → Grounding DINO.

Grounding DINO only runs when YOLO-World produced at least one candidate.
CLIP (optional) verifies EVERY detection — including YOLO26x's, despite it
being closed-vocab — against a weapon-vs-distractor prompt set. Manual review
of real UFDR stickers found YOLO26x itself false-positives on long thin
objects (a flagpole, a broom handle) at confidence levels well above the
default threshold, so closed-vocab boxes get the same cross-check as
open-vocab ones rather than a free pass.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from .labels import Det

ClipFn = Callable[[str, Det], bool]
DetectFn = Callable[[str], list[Det]]

# Same canonical class + overlapping box across models is one real-world
# object, not N separate Indicators. Collapse to the highest-confidence hit.
DEDUPE_IOU_THRESHOLD = 0.5


@dataclass
class Backends:
    weapon: DetectFn | None = None
    world: DetectFn | None = None
    dino: DetectFn | None = None
    clip_keep: ClipFn | None = None


def _box_iou(a: list[float], b: list[float]) -> float:
    if len(a) < 4 or len(b) < 4:
        return 0.0
    ax1, ay1, ax2, ay2 = a[:4]
    bx1, by1, bx2, by2 = b[:4]
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def dedupe_detections(
    dets: list[Det], iou_threshold: float = DEDUPE_IOU_THRESHOLD
) -> list[Det]:
    """Collapse same-class overlapping boxes from different models into one.

    Keeps the highest-confidence detection per overlapping cluster; models
    that agree on the same object no longer produce duplicate Indicator rows.
    """
    by_class: dict[str, list[Det]] = {}
    for det in dets:
        by_class.setdefault(det.class_name, []).append(det)

    kept: list[Det] = []
    for class_dets in by_class.values():
        remaining = sorted(class_dets, key=lambda d: d.confidence, reverse=True)
        while remaining:
            best = remaining.pop(0)
            kept.append(best)
            remaining = [
                d for d in remaining if _box_iou(best.bbox, d.bbox) < iou_threshold
            ]
    return kept


def run_cascade(
    image_path: str,
    stages: frozenset[str],
    backends: Backends,
    *,
    clip_enabled: bool = False,
) -> tuple[list[Det], list[str]]:
    """Run requested stages. Returns (detections, models_used)."""
    dets: list[Det] = []
    used: list[str] = []
    world_hits: list[Det] = []

    if "weapon" in stages and backends.weapon is not None:
        dets.extend(backends.weapon(image_path))
        used.append("weapon")

    if "world" in stages and backends.world is not None:
        world_hits = backends.world(image_path)
        dets.extend(world_hits)
        used.append("world")

    if "dino" in stages and backends.dino is not None:
        if "world" in stages:
            should_run = bool(world_hits)
        else:
            should_run = True
        if should_run:
            dets.extend(backends.dino(image_path))
            used.append("dino")

    if clip_enabled and backends.clip_keep is not None and dets:
        dets = [det for det in dets if backends.clip_keep(image_path, det)]
        used.append("clip")

    dets = dedupe_detections(dets)

    return dets, used
