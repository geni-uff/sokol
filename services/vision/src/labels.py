"""Canonical class names and cascade stage resolution.

Detections stored by the pipeline are Indicators (ADR-0004), never Facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PIPELINE_VERSION = "weapon-cascade-v1"

LEGACY_MODEL_NAMES = frozenset({"coco", "firearm", "threat"})
CASCADE_STAGES = frozenset({"weapon", "world", "dino"})

# YOLO-World / Grounding DINO text. English first (CLIP-backed encoders);
# Portuguese terms are extra recall for UFDR/WhatsApp screenshots.
WORLD_PROMPTS: tuple[str, ...] = (
    "handgun",
    "pistol",
    "rifle",
    "shotgun",
    "revolver",
    "firearm",
    "knife",
    "machete",
    "dagger",
    "faca",
    "facao",
)

DINO_TEXT = (
    "handgun. pistol. rifle. shotgun. revolver. firearm. "
    "knife. machete. dagger. faca. facao."
)

# Closed-vocab YOLO26x classes we do not keep as threat Indicators.
SKIP_WEAPON_CLASSES = frozenset(
    {
        "person",
        "tool",
        "fire smoke",
        "fire_smoke",
        "firesmoke",
    }
)

_WEAPON_CANON = {
    "firearm": "gun",
    "gun": "gun",
    "melee_weapon": "knife",
    "melee weapon": "knife",
    "blunt weapon": "blunt_weapon",
    "blunt_weapon": "blunt_weapon",
    "explosive": "explosive",
    "grenade": "grenade",
}

_OPEN_VOCAB_CANON = {
    "handgun": "gun",
    "pistol": "gun",
    "rifle": "gun",
    "shotgun": "gun",
    "revolver": "gun",
    "firearm": "gun",
    "gun": "gun",
    "weapon": "gun",
    "knife": "knife",
    "machete": "knife",
    "dagger": "knife",
    "faca": "knife",
    "facao": "knife",
    "facão": "knife",
    "grenade": "grenade",
    "explosive": "explosive",
}


@dataclass
class Det:
    model: str
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float] = field(default_factory=list)


def _norm_class(name: str) -> str:
    return " ".join(name.strip().lower().replace("-", " ").replace("_", " ").split())


def map_weapon_class(raw_name: str) -> str | None:
    """Map YOLO26x class → canonical Indicator name, or None to drop."""
    key = _norm_class(raw_name)
    if key in SKIP_WEAPON_CLASSES:
        return None
    return _WEAPON_CANON.get(key, key.replace(" ", "_") or None)


def map_open_vocab_class(raw_name: str) -> str | None:
    """Map YOLO-World / Grounding DINO label → canonical Indicator name."""
    key = _norm_class(raw_name)
    # DINO sometimes returns "a pistol" / "pistol."
    key = key.removeprefix("a ").removeprefix("an ").rstrip(".")
    mapped = _OPEN_VOCAB_CANON.get(key)
    if mapped:
        return mapped
    for token, canon in _OPEN_VOCAB_CANON.items():
        if token in key.split() or key in token:
            return canon
    return None


def box_fills_frame(
    bbox: list[float], width: int, height: int, frac: float = 0.80
) -> bool:
    """True when a box covers most of the image (typical open-vocab junk)."""
    if len(bbox) < 4 or width <= 0 or height <= 0:
        return False
    area = max(0.0, bbox[2] - bbox[0]) * max(0.0, bbox[3] - bbox[1])
    return area >= frac * float(width) * float(height)


def resolve_stages(requested: list[str] | None) -> frozenset[str]:
    """Map API model list to cascade stages.

    Legacy names (coco/firearm/threat) and 'cascade' run the full pipeline.
    """
    names = {n.strip().lower() for n in (requested or []) if n and n.strip()}
    if not names or "cascade" in names or names <= LEGACY_MODEL_NAMES:
        return CASCADE_STAGES
    if names & LEGACY_MODEL_NAMES:
        names = (names - LEGACY_MODEL_NAMES) | set(CASCADE_STAGES)
    out = {n for n in names if n in CASCADE_STAGES}
    return frozenset(out) if out else CASCADE_STAGES
