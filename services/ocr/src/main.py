"""SOKOL OCR Service — Text extraction from images using PaddleOCR."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI(title="SOKOL OCR Service", version="0.1.0")

OCR_ENGINE = None
SUPPORTED_LANGS = ["pt", "en", "es", "fr", "de", "it"]


def load_engine():
    global OCR_ENGINE
    print("[ocr] Loading PaddleOCR...")
    from paddleocr import PaddleOCR

    OCR_ENGINE = PaddleOCR(use_angle_cls=True, lang="pt", show_log=False)
    print("[ocr] PaddleOCR loaded")


class OCRResponse(BaseModel):
    text: str
    confidence: float
    language: str
    lines: list[dict]


@app.on_event("startup")
async def startup():
    load_engine()


@app.get("/health")
async def health():
    return {"status": "ok", "engine": "PaddleOCR"}


@app.post("/api/ocr")
async def ocr_extract(
    file: UploadFile = File(...),
    language: str = "pt",
):
    if OCR_ENGINE is None:
        raise HTTPException(status_code=503, detail="OCR engine not loaded")

    suffix = Path(file.filename or "image.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = OCR_ENGINE.ocr(tmp_path, cls=True)
        all_lines = []
        full_text_parts = []
        total_conf = 0.0
        count = 0

        if result and result[0]:
            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                conf = float(line[1][1])
                full_text_parts.append(text)
                total_conf += conf
                count += 1
                all_lines.append(
                    {
                        "bbox": [[int(p[0]), int(p[1])] for p in bbox],
                        "text": text,
                        "confidence": round(conf, 4),
                    }
                )

        avg_conf = round(total_conf / count, 4) if count > 0 else 0.0
        return OCRResponse(
            text="\n".join(full_text_parts),
            confidence=avg_conf,
            language=language,
            lines=all_lines,
        )
    finally:
        os.unlink(tmp_path)


@app.post("/api/ocr/path")
async def ocr_extract_path(body: dict):
    if OCR_ENGINE is None:
        raise HTTPException(status_code=503, detail="OCR engine not loaded")

    image_path = body.get("image_path", "")
    if not image_path:
        raise HTTPException(status_code=400, detail="image_path required")

    p = Path(image_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {image_path}")

    try:
        result = OCR_ENGINE.ocr(str(p), cls=True)
        all_lines = []
        full_text_parts = []
        total_conf = 0.0
        count = 0

        if result and result[0]:
            for line in result[0]:
                bbox = line[0]
                text = line[1][0]
                conf = float(line[1][1])
                full_text_parts.append(text)
                total_conf += conf
                count += 1
                all_lines.append(
                    {
                        "bbox": [[int(p2[0]), int(p2[1])] for p2 in bbox],
                        "text": text,
                        "confidence": round(conf, 4),
                    }
                )

        avg_conf = round(total_conf / count, 4) if count > 0 else 0.0
        return OCRResponse(
            text="\n".join(full_text_parts),
            confidence=avg_conf,
            language=body.get("language", "pt"),
            lines=all_lines,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)
