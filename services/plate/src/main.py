"""SOKOL Plate Service — License plate detection using YOLO + OCR."""

from __future__ import annotations

import os

# Paddle 3.3 CPU + oneDNN/PIR crashes predict() with ConvertPirAttribute2RuntimeAttribute.
os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_onednn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import re
import tempfile
from pathlib import Path

import cv2
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from paddleocr import PaddleOCR
from pydantic import BaseModel
from ultralytics import YOLO

app = FastAPI(title="SOKOL Plate Service", version="0.8.2")

PLATE_MODEL = None
OCR_ENGINE = None

PLATE_REGEXES = [
    re.compile(r"[A-Z]{3}\s?\d[A-Z0-9]\d{2}"),  # Mercosul: ABC1D23
    re.compile(r"[A-Z]{3}\s?\d{4}"),  # Antigo: ABC 1234
    re.compile(r"\d{4}\s?[A-Z]{3}"),  # Moto: 1234 ABC
]


def load_models():
    global PLATE_MODEL, OCR_ENGINE

    print("[plate] Loading YOLO plate model...")
    PLATE_MODEL = YOLO("yolov8n.pt")

    print("[plate] Loading PaddleOCR for plate reading...")
    OCR_ENGINE = PaddleOCR(
        lang="pt",
        use_textline_orientation=True,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
    )
    print("[plate] Models loaded")


class PlateDetection(BaseModel):
    bbox: list[float]
    plate_text: str
    confidence: float
    country: str | None = None


class PlateResponse(BaseModel):
    detections: list[PlateDetection]
    image_width: int = 0
    image_height: int = 0


@app.on_event("startup")
async def startup():
    load_models()


@app.get("/health")
async def health():
    return {"status": "ok", "models": ["yolov8n", "PaddleOCR"]}


@app.post("/api/plate", response_model=PlateResponse)
@app.post("/api/plate/detect", response_model=PlateResponse)
async def detect_plates_upload(file: UploadFile = File(...)):
    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return _detect_plates(tmp_path)
    finally:
        os.unlink(tmp_path)


@app.post("/api/plate/detect/path", response_model=PlateResponse)
async def detect_plates_path(body: dict):
    image_path = body.get("image_path", "")
    if not image_path:
        raise HTTPException(status_code=400, detail="image_path required")

    p = Path(image_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {image_path}")

    return _detect_plates(str(p))


def _detect_plates(image_path: str) -> PlateResponse:
    results = PLATE_MODEL(image_path, conf=0.3, verbose=False)

    img_w, img_h = 0, 0
    if results and results[0].orig_shape:
        img_h, img_w = results[0].orig_shape

    detections = []
    for result in results:
        if result.boxes is None:
            continue
        for i in range(len(result.boxes)):
            box = result.boxes[i]
            cls_id = int(box.cls[0])
            cls_name = result.names.get(cls_id, "")

            if cls_name.lower() not in ("car", "truck", "bus", "motorcycle", "vehicle"):
                continue

            xyxy = box.xyxy[0].tolist()
            x1, y1, x2, y2 = [int(v) for v in xyxy]

            pad_x = int((x2 - x1) * 0.1)
            pad_y = int((y2 - y1) * 0.3)
            crop_x1 = max(0, x1 - pad_x)
            crop_y1 = max(0, y1 + (y2 - y1) // 2 - pad_y)
            crop_x2 = min(img_w, x2 + pad_x)
            crop_y2 = min(img_h, y2 + pad_y)

            img = cv2.imread(image_path)
            if img is None:
                continue
            crop = img[crop_y1:crop_y2, crop_x1:crop_x2]

            if crop.size == 0:
                continue

            crop_path = tempfile.mktemp(suffix=".jpg")
            cv2.imwrite(crop_path, crop)

            try:
                ocr_result = OCR_ENGINE.predict(crop_path)
                texts: list[tuple[str, float]] = []
                if ocr_result:
                    items = ocr_result if isinstance(ocr_result, list) else [ocr_result]
                    for item in items:
                        rec_texts = None
                        rec_scores: list = []
                        if isinstance(item, dict):
                            rec_texts = item.get("rec_texts")
                            rec_scores = item.get("rec_scores") or []
                        elif hasattr(item, "get"):
                            rec_texts = item.get("rec_texts")
                            rec_scores = item.get("rec_scores") or []
                        elif hasattr(item, "rec_texts"):
                            rec_texts = item.rec_texts
                            rec_scores = getattr(item, "rec_scores", []) or []
                        elif isinstance(item, list):
                            for line in item:
                                try:
                                    texts.append(
                                        (str(line[1][0]).strip().upper(), float(line[1][1]))
                                    )
                                except (TypeError, IndexError, ValueError):
                                    continue
                        if rec_texts:
                            for i, raw in enumerate(rec_texts):
                                conf = float(rec_scores[i]) if i < len(rec_scores) else 0.0
                                texts.append((str(raw).strip().upper(), conf))

                for text, conf in texts:

                    for regex in PLATE_REGEXES:
                        match = regex.search(text)
                        if match:
                            detections.append(
                                PlateDetection(
                                    bbox=[x1, y1, x2, y2],
                                    plate_text=match.group().replace(" ", ""),
                                    confidence=round(conf, 4),
                                )
                            )
                            break
            finally:
                os.unlink(crop_path)

    return PlateResponse(
        detections=detections,
        image_width=img_w,
        image_height=img_h,
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8010)
