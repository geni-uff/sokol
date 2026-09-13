"""SOKOL Vision Service — weapon cascade (YOLO26x + YOLO-World + Grounding DINO)."""

from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from .cascade import Backends, run_cascade
from .labels import PIPELINE_VERSION, WORLD_PROMPTS, resolve_stages
from .runtime import VisionRuntime

runtime = VisionRuntime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    runtime.load()
    yield


app = FastAPI(
    title="SOKOL Vision Service",
    version="0.8.2",
    lifespan=lifespan,
)


class Detection(BaseModel):
    model: str
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]


class DetectionResult(BaseModel):
    image_id: Optional[str] = None
    detections: list[Detection]
    models_used: list[str]
    pipeline_version: str = PIPELINE_VERSION


class BatchDetectionRequest(BaseModel):
    image_ids: list[str]
    image_paths: list[str]
    models: list[str] = ["cascade"]


class BatchDetectionResult(BaseModel):
    results: list[DetectionResult]


def _backends() -> Backends:
    return Backends(
        weapon=runtime.detect_weapon if runtime.weapon is not None else None,
        world=runtime.detect_world if runtime.world is not None else None,
        dino=runtime.detect_dino if runtime.dino_model is not None else None,
        clip_keep=runtime.clip_keep if runtime.clip_model is not None else None,
    )


def detect_image(
    image_path: str,
    model_names: list[str],
    image_id: Optional[str] = None,
) -> DetectionResult:
    stages = resolve_stages(model_names)
    clip_enabled = runtime.clip_model is not None
    dets, used = run_cascade(
        image_path,
        stages,
        _backends(),
        clip_enabled=clip_enabled,
    )
    return DetectionResult(
        image_id=image_id,
        detections=[
            Detection(
                model=d.model,
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                bbox=d.bbox,
            )
            for d in dets
        ],
        models_used=used,
        pipeline_version=PIPELINE_VERSION,
    )


def _path_with_suffix(path: Path) -> tuple[Path, Path | None]:
    """YOLO needs a file extension. Copy hash-named cache files to a temp .jpg."""
    if path.suffix:
        return path, None
    fd, tmp_name = tempfile.mkstemp(suffix=".jpg")
    os.close(fd)
    tmp = Path(tmp_name)
    shutil.copy2(path, tmp)
    return tmp, tmp


@app.get("/health")
async def health():
    status = "ok" if runtime.loaded else "loading"
    if not runtime.loaded:
        status = "degraded"
    if "weapon" not in runtime.loaded and "world" not in runtime.loaded:
        status = "degraded"
    return {
        "status": status,
        "models": runtime.loaded,
        "model_count": len(runtime.loaded),
        "pipeline_version": PIPELINE_VERSION,
        "device": runtime.torch_device,
        "cascade": "weapon -> world -> dino(on world hit)",
        "clip": runtime.clip_model is not None,
    }


@app.post("/detect", response_model=DetectionResult)
async def detect(
    file: UploadFile = File(...),
    models: str = Form("cascade"),
    confidence: float = Form(0.0),
    image_id: Optional[str] = Form(None),
):
    """Detect weapons/threats in a single image. `confidence` is ignored; env thresholds apply."""
    del confidence  # thresholds are per-stage via SOKOL_VISION_*_CONF
    if not runtime.loaded:
        raise HTTPException(status_code=503, detail="Models not loaded")

    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        names = [m.strip() for m in models.split(",") if m.strip()]
        return detect_image(tmp_path, names, image_id=image_id)
    finally:
        os.unlink(tmp_path)


@app.post("/detect/batch", response_model=BatchDetectionResult)
async def detect_batch(request: BatchDetectionRequest):
    """Detect weapons/threats in multiple images (paths inside the container)."""
    if not runtime.loaded:
        raise HTTPException(status_code=503, detail="Models not loaded")

    results: list[DetectionResult] = []
    for image_id, image_path in zip(request.image_ids, request.image_paths):
        path = Path(image_path)
        if not path.exists():
            results.append(
                DetectionResult(
                    image_id=image_id,
                    detections=[],
                    models_used=[],
                    pipeline_version=PIPELINE_VERSION,
                )
            )
            continue
        model_path, tmp_path = _path_with_suffix(path)
        try:
            results.append(
                detect_image(str(model_path), request.models, image_id=image_id)
            )
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink()
    return BatchDetectionResult(results=results)


@app.get("/models")
async def list_models():
    info: dict[str, dict] = {}
    if runtime.weapon is not None:
        names = getattr(runtime.weapon, "names", {}) or {}
        info["weapon"] = {
            "classes": ["gun", "knife", "blunt_weapon", "explosive"],
            "source": os.getenv(
                "SOKOL_VISION_WEAPON_REPO", "HaiderKhan6410/weapon-yolo26x"
            ),
            "raw_classes": list(names.values()) if isinstance(names, dict) else [],
            "imgsz": int(os.getenv("SOKOL_VISION_IMGSZ", "1024")),
        }
    if runtime.world is not None:
        info["world"] = {
            "classes": ["gun", "knife"],
            "source": os.getenv("SOKOL_VISION_WORLD_WEIGHTS", "yolov8s-worldv2.pt"),
            "prompts": list(WORLD_PROMPTS),
        }
    if runtime.dino_model is not None:
        info["dino"] = {
            "classes": ["gun", "knife"],
            "source": os.getenv(
                "SOKOL_VISION_DINO_MODEL", "IDEA-Research/grounding-dino-tiny"
            ),
            "runs_when": "YOLO-World produced at least one candidate",
        }
    if runtime.clip_model is not None:
        info["clip"] = {
            "role": "verify open-vocab boxes; reject phone/hair-dryer/toy",
            "source": os.getenv(
                "SOKOL_VISION_CLIP_MODEL", "openai/clip-vit-base-patch32"
            ),
        }
    return info


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
