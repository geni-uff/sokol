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
            "SOKOL_OCR_API_URL", "http://localhost:11434"
        )

    async def extract_text(self, image_path: str) -> OCRResult:
        """Extract text from an image."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.api_url}/api/ocr",
                json={"image_path": image_path},
            )
            response.raise_for_status()
            data = response.json()
            return OCRResult(
                text=data.get("text", ""),
                confidence=data.get("confidence", 0.0),
                language=data.get("language"),
                bounding_boxes=data.get("bounding_boxes"),
            )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"
