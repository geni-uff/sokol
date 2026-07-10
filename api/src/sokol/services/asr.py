"""SOKOL — ASR (Automatic Speech Recognition) service."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class TranscriptionSegment:
    start_ms: float
    end_ms: float
    text: str
    confidence: float
    speaker: Optional[str] = None


@dataclass
class TranscriptionResult:
    segments: list[TranscriptionSegment]
    language: Optional[str] = None
    duration_ms: float = 0


class ASRService:
    """ASR service for audio/video transcription."""

    def __init__(self, api_url: Optional[str] = None):
        self.api_url = api_url or os.getenv(
            "SOKOL_ASR_API_URL", "http://localhost:11434"
        )

    async def transcribe(
        self, media_path: str, language: Optional[str] = None
    ) -> TranscriptionResult:
        """Transcribe audio/video file."""
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{self.api_url}/api/transcribe",
                json={"media_path": media_path, "language": language},
            )
            response.raise_for_status()
            data = response.json()

            segments = [
                TranscriptionSegment(
                    start_ms=s["start_ms"],
                    end_ms=s["end_ms"],
                    text=s["text"],
                    confidence=s.get("confidence", 0.0),
                    speaker=s.get("speaker"),
                )
                for s in data.get("segments", [])
            ]

            return TranscriptionResult(
                segments=segments,
                language=data.get("language"),
                duration_ms=data.get("duration_ms", 0),
            )

    async def health(self) -> str:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.api_url}/health")
                return "ok" if response.status_code == 200 else "error"
        except Exception:
            return "down"
