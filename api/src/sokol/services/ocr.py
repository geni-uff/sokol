"""SOKOL — OCR service for document analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class OCRResult:
    text: str
    confidence: float
    language: Optional[str] = None
    bounding_boxes: Optional[list[dict]] = None


class OCRService:
    """OCR service using local or remote models."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv(
            "SOKOL_OCR_API_URL", "http://localhost:8008"
        )

    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from an image."""
        import os as _os
        from pathlib import Path as _Path

        p = _Path(image_path)
        mime_map = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
            ".bmp": "image/bmp",
            ".tiff": "image/tiff",
        }
        content_type = mime_map.get(p.suffix.lower(), "image/jpeg")

        async with httpx.AsyncClient(timeout=60.0) as client:
            with open(image_path, "rb") as f:
                response = await client.post(
                    f"{self.api_url}/api/ocr",
                    files={"file": (p.name, f, content_type)},
                )
            response.raise_for_status()
            data = response.json()
            return OCRResult(
                text=data.get("text", ""),
                confidence=data.get("confidence", 0.0),
                language=data.get("language"),
                bounding_boxes=[line.get("bbox") for line in data.get("lines", [])],
            )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"
