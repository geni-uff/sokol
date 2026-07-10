"""SOKOL Vision Client — HTTP client for sokol-vision service."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx


class VisionClient:
    """Client for sokol-vision service."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or os.getenv(
            "SOKOL_VISION_API_URL", "http://localhost:8007"
        )

    async def detect(
        self,
        image_path: str | Path,
        models: list[str] | None = None,
        confidence: float = 0.25,
        image_id: str | None = None,
    ) -> dict:
        """Detect objects in a single image."""
        if models is None:
            models = ["coco", "firearm", "threat"]

        async with httpx.AsyncClient(timeout=120.0) as client:
            with open(image_path, "rb") as f:
                files = {"file": (str(image_path), f, "image/jpeg")}
                data = {
                    "models": ",".join(models),
                    "confidence": str(confidence),
                }
                if image_id:
                    data["image_id"] = image_id

                response = await client.post(
                    f"{self.base_url}/detect",
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return response.json()

    async def detect_batch(
        self,
        image_paths: list[str | Path],
        image_ids: list[str] | None = None,
        models: list[str] | None = None,
    ) -> list[dict]:
        """Detect objects in multiple images."""
        if models is None:
            models = ["coco", "firearm", "threat"]

        if image_ids is None:
            image_ids = [str(p) for p in image_paths]

        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.base_url}/detect/batch",
                json={
                    "image_ids": image_ids,
                    "image_paths": [str(p) for p in image_paths],
                    "models": models,
                },
            )
            response.raise_for_status()
            return response.json().get("results", [])

    async def health(self) -> str:
        """Check vision service health."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"

    async def list_models(self) -> dict:
        """List available models."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/models")
            response.raise_for_status()
            return response.json()
