"""Unit tests for vision class mapping and cascade gating."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.cascade import Backends, dedupe_detections, run_cascade
from src.labels import (
    Det,
    box_fills_frame,
    map_open_vocab_class,
    map_weapon_class,
    resolve_stages,
)


class MapWeaponTests(unittest.TestCase):
    def test_firearm_becomes_gun(self) -> None:
        self.assertEqual(map_weapon_class("Firearm"), "gun")

    def test_melee_becomes_knife(self) -> None:
        self.assertEqual(map_weapon_class("Melee_Weapon"), "knife")

    def test_blunt_weapon_kept(self) -> None:
        self.assertEqual(map_weapon_class("Blunt Weapon"), "blunt_weapon")

    def test_person_and_tool_dropped(self) -> None:
        self.assertIsNone(map_weapon_class("Person"))
        self.assertIsNone(map_weapon_class("Tool"))
        self.assertIsNone(map_weapon_class("Fire Smoke"))


class MapOpenVocabTests(unittest.TestCase):
    def test_en_and_pt_knives(self) -> None:
        self.assertEqual(map_open_vocab_class("machete"), "knife")
        self.assertEqual(map_open_vocab_class("faca"), "knife")
        self.assertEqual(map_open_vocab_class("facão"), "knife")

    def test_guns(self) -> None:
        self.assertEqual(map_open_vocab_class("a pistol."), "gun")
        self.assertEqual(map_open_vocab_class("rifle"), "gun")

    def test_unknown_dropped(self) -> None:
        self.assertIsNone(map_open_vocab_class("banana"))


class BoxFilterTests(unittest.TestCase):
    def test_full_frame_dropped(self) -> None:
        self.assertTrue(box_fills_frame([0, 0, 640, 480], 640, 480))
        self.assertFalse(box_fills_frame([10, 10, 80, 80], 640, 480))


class ResolveStagesTests(unittest.TestCase):
    def test_legacy_names_become_cascade(self) -> None:
        self.assertEqual(
            resolve_stages(["coco", "firearm", "threat"]),
            frozenset({"weapon", "world", "dino"}),
        )

    def test_empty_and_cascade_alias(self) -> None:
        self.assertEqual(resolve_stages(None), frozenset({"weapon", "world", "dino"}))
        self.assertEqual(
            resolve_stages(["cascade"]), frozenset({"weapon", "world", "dino"})
        )

    def test_weapon_only(self) -> None:
        self.assertEqual(resolve_stages(["weapon"]), frozenset({"weapon"}))


class CascadeGatingTests(unittest.TestCase):
    def test_dino_skipped_when_world_has_no_hits(self) -> None:
        dino_called = []

        def world(_path: str) -> list[Det]:
            return []

        def dino(_path: str) -> list[Det]:
            dino_called.append(True)
            return [
                Det(
                    model="dino",
                    class_id=0,
                    class_name="gun",
                    confidence=0.9,
                    bbox=[1, 2, 3, 4],
                )
            ]

        dets, used = run_cascade(
            "img.jpg",
            frozenset({"weapon", "world", "dino"}),
            Backends(world=world, dino=dino),
        )
        self.assertEqual(dets, [])
        self.assertEqual(used, ["world"])
        self.assertEqual(dino_called, [])

    def test_dino_runs_after_world_hit(self) -> None:
        # Same class + overlapping box across stages is deduped to the
        # highest-confidence hit (see DedupeTests) — this test only asserts
        # both stages actually ran.
        world_det = Det(
            model="world", class_id=0, class_name="gun", confidence=0.4, bbox=[0, 0, 10, 10]
        )
        dino_det = Det(
            model="dino", class_id=0, class_name="gun", confidence=0.8, bbox=[0, 0, 10, 10]
        )

        dets, used = run_cascade(
            "img.jpg",
            frozenset({"world", "dino"}),
            Backends(
                world=lambda _p: [world_det],
                dino=lambda _p: [dino_det],
            ),
        )
        self.assertEqual(dets, [dino_det])
        self.assertEqual(used, ["world", "dino"])

    def test_dino_skipped_when_world_backend_missing(self) -> None:
        dino_called: list[bool] = []

        def dino(_path: str) -> list[Det]:
            dino_called.append(True)
            return []

        dets, used = run_cascade(
            "img.jpg",
            frozenset({"weapon", "world", "dino"}),
            Backends(dino=dino),
        )
        self.assertEqual(dets, [])
        self.assertEqual(used, [])
        self.assertEqual(dino_called, [])

    def test_clip_also_verifies_weapon_hits(self) -> None:
        """Manual review of real UFDR stickers found YOLO26x false-positives
        on long thin objects (flagpole, broom handle) at high confidence, so
        CLIP must be able to reject weapon-stage boxes too, not just
        open-vocab ones."""
        weapon = Det(
            model="weapon",
            class_id=0,
            class_name="gun",
            confidence=0.9,
            bbox=[0, 0, 10, 10],
        )
        dets, used = run_cascade(
            "img.jpg",
            frozenset({"weapon", "world"}),
            Backends(
                weapon=lambda _p: [weapon],
                clip_keep=lambda _p, _d: False,
            ),
            clip_enabled=True,
        )
        self.assertEqual(dets, [])
        self.assertIn("clip", used)

    def test_clip_keeps_weapon_hit_when_confirmed(self) -> None:
        weapon = Det(
            model="weapon",
            class_id=0,
            class_name="gun",
            confidence=0.9,
            bbox=[0, 0, 10, 10],
        )
        world = Det(
            model="world",
            class_id=0,
            class_name="knife",
            confidence=0.3,
            bbox=[50, 50, 60, 60],
        )
        dets, used = run_cascade(
            "img.jpg",
            frozenset({"weapon", "world"}),
            Backends(
                weapon=lambda _p: [weapon],
                world=lambda _p: [world],
                clip_keep=lambda _p, det: det.model == "weapon",
            ),
            clip_enabled=True,
        )
        self.assertEqual(dets, [weapon])
        self.assertIn("clip", used)

    def test_clip_skipped_when_no_detections(self) -> None:
        dets, used = run_cascade(
            "img.jpg",
            frozenset({"weapon", "world"}),
            Backends(
                weapon=lambda _p: [],
                clip_keep=lambda _p, _d: False,
            ),
            clip_enabled=True,
        )
        self.assertEqual(dets, [])
        self.assertNotIn("clip", used)


class DedupeTests(unittest.TestCase):
    def test_overlapping_same_class_collapses_to_highest_confidence(self) -> None:
        low = Det(model="dino", class_id=0, class_name="gun", confidence=0.3, bbox=[10, 10, 100, 100])
        high = Det(model="world", class_id=0, class_name="gun", confidence=0.6, bbox=[12, 12, 98, 98])
        self.assertEqual(dedupe_detections([low, high]), [high])

    def test_non_overlapping_boxes_both_kept(self) -> None:
        a = Det(model="weapon", class_id=0, class_name="knife", confidence=0.5, bbox=[0, 0, 10, 10])
        b = Det(model="dino", class_id=0, class_name="knife", confidence=0.4, bbox=[200, 200, 210, 210])
        result = dedupe_detections([a, b])
        self.assertEqual(len(result), 2)

    def test_different_classes_not_merged_even_if_overlapping(self) -> None:
        gun = Det(model="weapon", class_id=0, class_name="gun", confidence=0.5, bbox=[0, 0, 10, 10])
        knife = Det(model="dino", class_id=0, class_name="knife", confidence=0.4, bbox=[0, 0, 10, 10])
        result = dedupe_detections([gun, knife])
        self.assertEqual(len(result), 2)


if __name__ == "__main__":
    unittest.main()
