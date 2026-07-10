"""SOKOL — Face detection service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class FaceDetection:
    bbox: tuple[int, int, int, int]  # x1, y1, x2, y2
    confidence: float
    embedding: Optional[list[float]] = None
    label: Optional[str] = None


@dataclass
class FaceResult:
    detections: list[FaceDetection]
    image_width: int = 0
    image_height: int = 0


class FaceService:
    """Face detection and recognition service."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv(
            "SOKOL_FACE_API_URL", "http://localhost:11434"
        )

    async def detect_faces(self, image_path: str) -> FaceResult:
        """Detect faces in image."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.api_url}/api/face/detect",
                json={"image_path": image_path},
            )
            response.raise_for_status()
            data = response.json()

            detections = [
                FaceDetection(
                    bbox=tuple(d["bbox"]),
                    confidence=d["confidence"],
                    embedding=d.get("embedding"),
                    label=d.get("label"),
                )
                for d in data.get("detections", [])
            ]

            return FaceResult(
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
