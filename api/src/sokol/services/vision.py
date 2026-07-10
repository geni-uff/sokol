"""SOKOL — Vision service for keyframe extraction and analysis."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class Keyframe:
    timestamp_ms: float
    image_path: str
    description: Optional[str] = None
    scene_change_score: float = 0.0


@dataclass
class VisionResult:
    keyframes: list[Keyframe]
    total_frames: int = 0
    duration_ms: float = 0


class VisionService:
    """Vision service for video keyframe extraction."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv(
            "SOKOL_VISION_API_URL", "http://localhost:11434"
        )

    async def extract_keyframes(
        self, video_path: str, interval_ms: float = 5000
    ) -> VisionResult:
        """Extract keyframes from video."""
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self.api_url}/api/keyframes",
                json={"video_path": video_path, "interval_ms": interval_ms},
            )
            response.raise_for_status()
            data = response.json()

            keyframes = [
                Keyframe(
                    timestamp_ms=k["timestamp_ms"],
                    image_path=k["image_path"],
                    description=k.get("description"),
                    scene_change_score=k.get("scene_change_score", 0.0),
                )
                for k in data.get("keyframes", [])
            ]

            return VisionResult(
                keyframes=keyframes,
                total_frames=data.get("total_frames", 0),
                duration_ms=data.get("duration_ms", 0),
            )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"
