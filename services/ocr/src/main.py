"""SOKOL OCR Service — Text extraction from images using PaddleOCR."""

from __future__ import annotations

import os

os.environ.setdefault("FLAGS_use_mkldnn", "0")
os.environ.setdefault("FLAGS_onednn", "0")
os.environ.setdefault("FLAGS_enable_pir_api", "0")
os.environ.setdefault("PADDLE_PDX_ENABLE_MKLDNN_BYDEFAULT", "0")

import tempfile
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from paddleocr import PaddleOCR
from pydantic import BaseModel

app = FastAPI(title="SOKOL OCR Service", version="0.8.2")

OCR_ENGINE = None
SUPPORTED_LANGS = ["pt", "en", "es", "fr", "de", "it"]


def _make_paddle_ocr():
    return PaddleOCR(
        lang="pt",
        use_textline_orientation=True,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        enable_mkldnn=False,
    )


def _as_mapping(item: Any) -> dict[str, Any] | None:
    if isinstance(item, dict):
        return item
    if hasattr(item, "keys") and hasattr(item, "get"):
        try:
            return dict(item)
        except Exception:
            rec_texts = getattr(item, "rec_texts", None)
            if rec_texts is None:
                return None
            return {
                "rec_texts": rec_texts,
                "rec_scores": getattr(item, "rec_scores", []) or [],
                "rec_polys": getattr(item, "rec_polys", None)
                or getattr(item, "dt_polys", [])
                or [],
            }
    return None


def parse_paddle_lines(result: Any) -> list[dict]:
    """Normalize PaddleOCR 2.x nested lists and 3.x predict dicts."""
    lines: list[dict] = []
    if not result:
        return lines

    items = result if isinstance(result, list) else [result]
    for item in items:
        if item is None:
            continue
        mapping = _as_mapping(item)
        if mapping and mapping.get("rec_texts") is not None:
            texts = mapping.get("rec_texts") or []
            scores = mapping.get("rec_scores") or []
            polys = mapping.get("rec_polys") or mapping.get("dt_polys") or []
            for i, text in enumerate(texts):
                conf = float(scores[i]) if i < len(scores) else 0.0
                poly = polys[i] if i < len(polys) else []
                bbox = []
                for pt in poly:
                    try:
                        bbox.append([int(pt[0]), int(pt[1])])
                    except (TypeError, IndexError, ValueError):
                        continue
                lines.append(
                    {
                        "bbox": bbox,
                        "text": str(text),
                        "confidence": round(conf, 4),
                    }
                )
            continue

        nested = item if isinstance(item, list) else None
        if not nested:
            continue
        for line in nested:
            try:
                bbox_raw, rec = line[0], line[1]
                text, conf = rec[0], float(rec[1])
                bbox = [[int(p[0]), int(p[1])] for p in bbox_raw]
            except (TypeError, IndexError, ValueError):
                continue
            lines.append(
                {
                    "bbox": bbox,
                    "text": str(text),
                    "confidence": round(conf, 4),
                }
            )
    return lines


def run_ocr(image_path: str, language: str) -> OCRResponse:
    result = OCR_ENGINE.predict(image_path)
    all_lines = parse_paddle_lines(result)
    avg_conf = (
        round(sum(line["confidence"] for line in all_lines) / len(all_lines), 4)
        if all_lines
        else 0.0
    )
    return OCRResponse(
        text="\n".join(line["text"] for line in all_lines),
        confidence=avg_conf,
        language=language,
        lines=all_lines,
    )


def load_engine():
    global OCR_ENGINE
    print("[ocr] Loading PaddleOCR...")
    OCR_ENGINE = _make_paddle_ocr()
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
        return run_ocr(tmp_path, language)
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
        return run_ocr(str(p), body.get("language", "pt"))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8008)
