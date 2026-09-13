"""Load YOLO26x, YOLO-World, Grounding DINO and optional CLIP."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any

import torch
from huggingface_hub import hf_hub_download
from PIL import Image
from transformers import (
    AutoModelForZeroShotObjectDetection,
    AutoProcessor,
    CLIPModel,
    CLIPProcessor,
)
from ultralytics import YOLO

from .labels import (
    DINO_TEXT,
    WORLD_PROMPTS,
    Det,
    box_fills_frame,
    map_open_vocab_class,
    map_weapon_class,
)

MODEL_DIR = Path(os.getenv("SOKOL_MODEL_DIR", "/data/models/vision"))
WEAPON_REPO = os.getenv("SOKOL_VISION_WEAPON_REPO", "HaiderKhan6410/weapon-yolo26x")
WEAPON_FILE = os.getenv("SOKOL_VISION_WEAPON_FILE", "model/best.pt")
WORLD_WEIGHTS = os.getenv("SOKOL_VISION_WORLD_WEIGHTS", "yolov8s-worldv2.pt")
DINO_MODEL_ID = os.getenv(
    "SOKOL_VISION_DINO_MODEL", "IDEA-Research/grounding-dino-tiny"
)
CLIP_MODEL_ID = os.getenv("SOKOL_VISION_CLIP_MODEL", "openai/clip-vit-base-patch32")

WEAPON_CONF = float(os.getenv("SOKOL_VISION_CONF", "0.20"))
WORLD_CONF = float(os.getenv("SOKOL_VISION_WORLD_CONF", "0.15"))
DINO_BOX_THRESHOLD = float(os.getenv("SOKOL_VISION_DINO_CONF", "0.25"))
DINO_TEXT_THRESHOLD = float(os.getenv("SOKOL_VISION_DINO_TEXT_CONF", "0.20"))
WEAPON_IMGSZ = int(os.getenv("SOKOL_VISION_IMGSZ", "1024"))
WORLD_IMGSZ = int(os.getenv("SOKOL_VISION_WORLD_IMGSZ", "640"))
CLIP_MARGIN = float(os.getenv("SOKOL_VISION_CLIP_MARGIN", "0.02"))

CLIP_WEAPON_PROMPTS = (
    "a photo of a firearm",
    "a photo of a handgun",
    "a photo of a rifle",
    "a photo of a knife",
    "a photo of a machete",
    "a photo of an explosive",
)
CLIP_DISTRACTORS = (
    "a photo of a mobile phone",
    "a photo of a hair dryer",
    "a photo of a toy",
    "a photo of a remote control",
    # Long thin objects observed confusing the cascade for a knife/gun
    "a photo of a broom",
    "a photo of a flagpole",
    "a photo of a walking stick or cane",
    "a photo of a mop",
    "a photo of a selfie stick",
    "a photo of an umbrella",
    "a cartoon or sticker illustration of a person",
    "a photo of a flag or banner",
    "a photo of fabric or cloth",
)


def resolve_device() -> tuple[str, str]:
    """Return (yolo_device, torch_device). YOLO wants '0' or 'cpu'."""
    forced = os.getenv("SOKOL_VISION_DEVICE", "auto").strip().lower()
    if forced in {"cpu"}:
        return "cpu", "cpu"
    if forced not in {"", "auto"}:
        return forced, ("cuda" if forced not in {"cpu"} else "cpu")
    if torch.cuda.is_available():
        return "0", "cuda"
    return "cpu", "cpu"


def _hf_download(repo_id: str, filename: str, dest_dir: Path) -> Path:
    dest_dir.mkdir(parents=True, exist_ok=True)
    downloaded = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        cache_dir=str(MODEL_DIR / "hf-cache"),
    )
    dest = dest_dir / Path(filename).name
    if Path(downloaded).resolve() != dest.resolve():
        shutil.copy2(downloaded, dest)
    return dest


class VisionRuntime:
    """Holds loaded models. Missing backends stay None (cascade skips them)."""

    def __init__(self) -> None:
        self.yolo_device, self.torch_device = resolve_device()
        self.weapon = None
        self.world = None
        self.dino_processor = None
        self.dino_model = None
        self.clip_processor = None
        self.clip_model = None
        self.loaded: list[str] = []

    def load(self) -> None:
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("YOLO_CONFIG_DIR", str(MODEL_DIR))
        os.environ.setdefault("HF_HOME", str(MODEL_DIR / "hf-home"))
        self._load_weapon()
        self._load_world()
        if os.getenv("SOKOL_VISION_DINO", "1") not in {"0", "false", "False"}:
            self._load_dino()
        if os.getenv("SOKOL_VISION_CLIP", "1") not in {"0", "false", "False"}:
            self._load_clip()
        print(
            f"[vision] loaded={self.loaded} yolo_device={self.yolo_device} "
            f"torch_device={self.torch_device}",
            flush=True,
        )

    def _load_weapon(self) -> None:
        print("[vision] Loading weapon-yolo26x...", flush=True)
        try:
            dest = MODEL_DIR / "weapon_yolo26x.pt"
            if not dest.exists():
                downloaded = _hf_download(WEAPON_REPO, WEAPON_FILE, MODEL_DIR / "weapon")
                shutil.copy2(downloaded, dest)
            self.weapon = YOLO(str(dest))
            self.loaded.append("weapon")
        except Exception as exc:
            print(f"[vision] weapon-yolo26x unavailable: {exc}", flush=True)
            self.weapon = None

    def _load_world(self) -> None:
        print("[vision] Loading YOLO-World...", flush=True)
        try:
            cwd = Path.cwd()
            os.chdir(MODEL_DIR)
            try:
                self.world = YOLO(WORLD_WEIGHTS)
            finally:
                os.chdir(cwd)
            self.world.set_classes(list(WORLD_PROMPTS))
            self.loaded.append("world")
        except Exception as exc:
            print(f"[vision] YOLO-World unavailable: {exc}", flush=True)
            self.world = None

    def _load_dino(self) -> None:
        print("[vision] Loading Grounding DINO...", flush=True)
        try:
            self.dino_processor = AutoProcessor.from_pretrained(DINO_MODEL_ID)
            self.dino_model = AutoModelForZeroShotObjectDetection.from_pretrained(
                DINO_MODEL_ID
            )
            self.dino_model.to(self.torch_device)
            self.dino_model.eval()
            self.loaded.append("dino")
        except Exception as exc:
            print(f"[vision] Grounding DINO unavailable: {exc}", flush=True)
            self.dino_processor = None
            self.dino_model = None

    def _load_clip(self) -> None:
        print("[vision] Loading CLIP verifier...", flush=True)
        try:
            self.clip_processor = CLIPProcessor.from_pretrained(CLIP_MODEL_ID)
            self.clip_model = CLIPModel.from_pretrained(CLIP_MODEL_ID)
            self.clip_model.to(self.torch_device)
            self.clip_model.eval()
            self.loaded.append("clip")
        except Exception as exc:
            print(f"[vision] CLIP unavailable: {exc}", flush=True)
            self.clip_processor = None
            self.clip_model = None

    def detect_weapon(self, image_path: str) -> list[Det]:
        if self.weapon is None:
            return []
        results = self.weapon.predict(
            image_path,
            conf=WEAPON_CONF,
            imgsz=WEAPON_IMGSZ,
            device=self.yolo_device,
            verbose=False,
        )
        return _yolo_dets(results, model_name="weapon", mapper=map_weapon_class)

    def detect_world(self, image_path: str) -> list[Det]:
        if self.world is None:
            return []
        results = self.world.predict(
            image_path,
            conf=WORLD_CONF,
            imgsz=WORLD_IMGSZ,
            device=self.yolo_device,
            verbose=False,
        )
        return _yolo_dets(results, model_name="world", mapper=map_open_vocab_class)

    def detect_dino(self, image_path: str) -> list[Det]:
        if self.dino_model is None or self.dino_processor is None:
            return []
        image = Image.open(image_path).convert("RGB")
        inputs = self.dino_processor(
            images=image, text=DINO_TEXT, return_tensors="pt"
        )
        inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.dino_model(**inputs)

        result = _post_process_dino(
            self.dino_processor,
            outputs,
            inputs.get("input_ids"),
            image.size,
        )
        dets: list[Det] = []
        boxes = result.get("boxes", [])
        scores = result.get("scores", [])
        labels = result.get("text_labels") or result.get("labels") or []
        for i, box in enumerate(boxes):
            raw = labels[i] if i < len(labels) else ""
            if hasattr(raw, "item"):
                raw = str(raw.item()) if not isinstance(raw, str) else raw
            raw_name = str(raw)
            canon = map_open_vocab_class(raw_name)
            if not canon:
                continue
            conf = float(scores[i]) if i < len(scores) else 0.0
            xyxy = box.tolist() if hasattr(box, "tolist") else list(box)
            xyxy = [round(float(v), 2) for v in xyxy[:4]]
            if box_fills_frame(xyxy, image.size[0], image.size[1]):
                continue
            dets.append(
                Det(
                    model="dino",
                    class_id=i,
                    class_name=canon,
                    confidence=round(conf, 4),
                    bbox=xyxy,
                )
            )
        return dets

    def clip_keep(self, image_path: str, det: Det) -> bool:
        if self.clip_model is None or self.clip_processor is None:
            return True
        image = Image.open(image_path).convert("RGB")
        crop = _crop_bbox(image, det.bbox)
        prompts = list(CLIP_WEAPON_PROMPTS) + list(CLIP_DISTRACTORS)
        inputs = self.clip_processor(
            text=prompts, images=crop, return_tensors="pt", padding=True
        )
        inputs = {k: v.to(self.torch_device) for k, v in inputs.items()}
        with torch.no_grad():
            out = self.clip_model(**inputs)
            probs = out.logits_per_image.softmax(dim=1)[0]
        n_weapon = len(CLIP_WEAPON_PROMPTS)
        weapon_score = float(probs[:n_weapon].max())
        distractor_score = float(probs[n_weapon:].max())
        return weapon_score >= distractor_score + CLIP_MARGIN


def _yolo_dets(results: Any, *, model_name: str, mapper) -> list[Det]:
    dets: list[Det] = []
    for result in results:
        boxes = result.boxes
        if boxes is None:
            continue
        names = getattr(result, "names", {}) or {}
        for i in range(len(boxes)):
            box = boxes[i]
            cls_id = int(box.cls[0])
            conf = float(box.conf[0])
            xyxy = box.xyxy[0].tolist()
            raw = names.get(cls_id, f"class_{cls_id}")
            canon = mapper(str(raw))
            if not canon:
                continue
            xyxy = [round(float(v), 2) for v in xyxy]
            dets.append(
                Det(
                    model=model_name,
                    class_id=cls_id,
                    class_name=canon,
                    confidence=round(conf, 4),
                    bbox=xyxy,
                )
            )
    return dets


def _post_process_dino(processor, outputs, input_ids, image_size: tuple[int, int]):
    target_sizes = [(image_size[1], image_size[0])]
    attempts = [
        dict(
            outputs=outputs,
            input_ids=input_ids,
            box_threshold=DINO_BOX_THRESHOLD,
            text_threshold=DINO_TEXT_THRESHOLD,
            target_sizes=target_sizes,
        ),
        dict(
            outputs=outputs,
            input_ids=input_ids,
            threshold=DINO_BOX_THRESHOLD,
            text_threshold=DINO_TEXT_THRESHOLD,
            target_sizes=target_sizes,
        ),
        dict(
            outputs=outputs,
            threshold=DINO_BOX_THRESHOLD,
            target_sizes=target_sizes,
        ),
    ]
    last_error: Exception | None = None
    for kwargs in attempts:
        kwargs = {k: v for k, v in kwargs.items() if v is not None or k == "outputs"}
        try:
            results = processor.post_process_grounded_object_detection(**kwargs)
            return results[0]
        except TypeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return {"boxes": [], "scores": [], "labels": []}


def _crop_bbox(image, bbox: list[float], pad: float = 0.08):
    w, h = image.size
    if len(bbox) < 4:
        return image
    x1, y1, x2, y2 = bbox[:4]
    bw, bh = max(x2 - x1, 1.0), max(y2 - y1, 1.0)
    x1 = max(0, int(x1 - bw * pad))
    y1 = max(0, int(y1 - bh * pad))
    x2 = min(w, int(x2 + bw * pad))
    y2 = min(h, int(y2 + bh * pad))
    if x2 <= x1 or y2 <= y1:
        return image
    return image.crop((x1, y1, x2, y2))
