"""SOKOL — License plate detection service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class PlateDetection:
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    plate_text: str
    confidence: float
    country: Optional[str] = None


@dataclass
class PlateResult:
    detections: list[PlateDetection]
    image_width: int = 0
    image_height: int = 0


class PlateService:
    """License plate detection and OCR service."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv(
            "SOKOL_PLATE_API_URL", "http://localhost:8010"
        )

    async def detect_plates(self, image_path: str) -> PlateResult:
        """Detect license plates in image."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/api/plate/detect",
                json={"image_path": image_path},
            )
            response.raise_for_status()
            data = response.json()

            detections = [
                PlateDetection(
                    bbox=tuple(d["bbox"]),
                    plate_text=d["plate_text"],
                    confidence=d["confidence"],
                    country=d.get("country"),
                )
                for d in data.get("detections", [])
            ]

            return PlateResult(
                detections=detections,
                image_width=data.get("image_width", 0),
                image_height=data.get("image_height", 0),
            )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"
