"""SOKOL Vision Service — Object detection with multiple YOLO models."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel
from ultralytics import YOLO

app = FastAPI(title="SOKOL Vision Service", version="0.8.2")

# ── Configuration ───────────────────────────────────────────────────────────
MODEL_DIR = Path(os.getenv("SOKOL_MODEL_DIR", "/data/models/vision"))
CONFIDENCE_THRESHOLD = float(os.getenv("SOKOL_VISION_CONF", "0.25"))

# ── Models ──────────────────────────────────────────────────────────────────
MODELS: dict[str, YOLO] = {}


def load_models():
    """Load all YOLO models on startup."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    # 1. YOLOv8n standard COCO (80 classes)
    print("[vision] Loading YOLOv8n COCO...")
    MODELS["coco"] = YOLO("yolov8n.pt")

    # 2. Subh775 Firearm Detection (1 class: Gun)
    print("[vision] Loading Subh775 Firearm Detection...")
    firearm_path = MODEL_DIR / "firearm_detection_yolov8n.pt"
    if not firearm_path.exists():
        print("[vision] Downloading Subh775/Firearm_Detection_Yolov8n...")
        try:
            from huggingface_hub import hf_hub_download

            hf_hub_download(
                repo_id="Subh775/Firearm_Detection_Yolov8n",
                filename="weights/best.pt",
                local_dir=str(MODEL_DIR / "firearm"),
            )
            # Rename to standard name
            src = MODEL_DIR / "firearm" / "weights" / "best.pt"
            src.rename(firearm_path)
        except Exception as e:
            print(f"[vision] Warning: Could not download firearm model: {e}")
            print("[vision] Using COCO model only for gun detection")

    if firearm_path.exists():
        MODELS["firearm"] = YOLO(str(firearm_path))

    # 3. Subh775 Threat Detection (4 classes: Gun, Explosive, Grenade, Knife)
    print("[vision] Loading Subh775 Threat Detection...")
    threat_path = MODEL_DIR / "threat_detection_yolov8n.pt"
    if not threat_path.exists():
        print("[vision] Downloading Subh775/Threat-Detection-YOLOv8n...")
        try:
            from huggingface_hub import hf_hub_download

            hf_hub_download(
                repo_id="Subh775/Threat-Detection-YOLOv8n",
                filename="weights/best.pt",
                local_dir=str(MODEL_DIR / "threat"),
            )
            src = MODEL_DIR / "threat" / "weights" / "best.pt"
            src.rename(threat_path)
        except Exception as e:
            print(f"[vision] Warning: Could not download threat model: {e}")

    if threat_path.exists():
        MODELS["threat"] = YOLO(str(threat_path))

    print(f"[vision] Loaded {len(MODELS)} models: {list(MODELS.keys())}")


# ── Schemas ─────────────────────────────────────────────────────────────────
class Detection(BaseModel):
    model: str
    class_id: int
    class_name: str
    confidence: float
    bbox: list[float]  # [x1, y1, x2, y2]


class DetectionResult(BaseModel):
    image_id: Optional[str] = None
    detections: list[Detection]
    models_used: list[str]


class BatchDetectionRequest(BaseModel):
    image_ids: list[str]
    image_paths: list[str]
    models: list[str] = ["coco", "firearm", "threat"]


class BatchDetectionResult(BaseModel):
    results: list[DetectionResult]


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    load_models()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "models": list(MODELS.keys()),
        "model_count": len(MODELS),
    }


@app.post("/detect", response_model=DetectionResult)
async def detect(
    file: UploadFile = File(...),
    models: str = "coco,firearm,threat",
    confidence: float = CONFIDENCE_THRESHOLD,
    image_id: Optional[str] = None,
):
    """Detect objects in a single image."""
    if not MODELS:
        raise HTTPException(status_code=503, detail="Models not loaded")

    model_names = [m.strip() for m in models.split(",") if m.strip() in MODELS]
    if not model_names:
        model_names = list(MODELS.keys())

    # Save uploaded file temporarily
    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        all_detections = []
        for model_name in model_names:
            model = MODELS[model_name]
            results = model(tmp_path, conf=confidence, verbose=False)

            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        box = boxes[i]
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].tolist()

                        # Get class name
                        if model_name == "firearm":
                            cls_name = "gun"
                        elif model_name == "threat":
                            # Subh775 Threat Detection: Gun, Explosive, Grenade, Knife
                            threat_classes = {
                                0: "gun",
                                1: "explosive",
                                2: "grenade",
                                3: "knife",
                            }
                            cls_name = threat_classes.get(cls_id, f"class_{cls_id}")
                        else:
                            cls_name = result.names.get(cls_id, f"class_{cls_id}")

                        all_detections.append(
                            Detection(
                                model=model_name,
                                class_id=cls_id,
                                class_name=cls_name,
                                confidence=round(conf, 4),
                                bbox=[round(v, 2) for v in xyxy],
                            )
                        )

        return DetectionResult(
            image_id=image_id,
            detections=all_detections,
            models_used=model_names,
        )
    finally:
        os.unlink(tmp_path)


@app.post("/detect/batch", response_model=BatchDetectionResult)
async def detect_batch(request: BatchDetectionRequest):
    """Detect objects in multiple images."""
    if not MODELS:
        raise HTTPException(status_code=503, detail="Models not loaded")

    results = []
    for image_id, image_path in zip(request.image_ids, request.image_paths):
        path = Path(image_path)
        if not path.exists():
            results.append(
                DetectionResult(image_id=image_id, detections=[], models_used=[])
            )
            continue

        # YOLO requires file extension - add .jpg if missing
        import tempfile
        import shutil

        tmp_path = None
        if not path.suffix:
            # Copy file to temp with .jpg extension for YOLO
            with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
                tmp_path = Path(tmp.name)
            shutil.copy2(path, tmp_path)
            model_path = tmp_path
        else:
            model_path = path

        all_detections = []
        for model_name in request.models:
            if model_name not in MODELS:
                continue

            model = MODELS[model_name]
            model_results = model(
                str(model_path), conf=CONFIDENCE_THRESHOLD, verbose=False
            )

        # Clean up temp file if we created one
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()

            for result in model_results:
                boxes = result.boxes
                if boxes is not None:
                    for i in range(len(boxes)):
                        box = boxes[i]
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        xyxy = box.xyxy[0].tolist()

                        if model_name == "firearm":
                            cls_name = "gun"
                        elif model_name == "threat":
                            threat_classes = {
                                0: "gun",
                                1: "explosive",
                                2: "grenade",
                                3: "knife",
                            }
                            cls_name = threat_classes.get(cls_id, f"class_{cls_id}")
                        else:
                            cls_name = result.names.get(cls_id, f"class_{cls_id}")

                        all_detections.append(
                            Detection(
                                model=model_name,
                                class_id=cls_id,
                                class_name=cls_name,
                                confidence=round(conf, 4),
                                bbox=[round(v, 2) for v in xyxy],
                            )
                        )

        results.append(
            DetectionResult(
                image_id=image_id,
                detections=all_detections,
                models_used=request.models,
            )
        )

    return BatchDetectionResult(results=results)


@app.get("/models")
async def list_models():
    """List available models and their classes."""
    model_info = {}
    for name, model in MODELS.items():
        if name == "firearm":
            model_info[name] = {
                "classes": ["gun"],
                "source": "Subh775/Firearm_Detection_Yolov8n",
            }
        elif name == "threat":
            model_info[name] = {
                "classes": ["gun", "explosive", "grenade", "knife"],
                "source": "Subh775/Threat-Detection-YOLOv8n",
            }
        else:
            model_info[name] = {
                "classes": list(model.names.values())
                if hasattr(model, "names")
                else [],
                "source": "COCO (yolov8n.pt)",
            }
    return model_info


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8007)
