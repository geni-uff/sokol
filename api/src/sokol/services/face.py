"""SOKOL API — Face recognition client (InsightFace service)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import httpx

FACE_URL = os.getenv("SOKOL_FACE_URL", "http://localhost:8011")


async def detect_faces(file_path: str, image_id: Optional[str] = None) -> dict:
    """Detect faces and extract embeddings from an image file."""
    path = Path(file_path)
    if not path.exists():
        return {"faces": [], "face_count": 0}

    async with httpx.AsyncClient(timeout=60) as client:
        with open(path, "rb") as f:
            files = {"file": (path.name, f, "image/jpeg")}
            data = {}
            if image_id:
                data["image_id"] = image_id
            resp = await client.post(f"{FACE_URL}/detect", files=files, data=data)
            resp.raise_for_status()
            return resp.json()


async def detect_faces_bytes(content: bytes, filename: str = "image.jpg") -> dict:
    """Detect faces from image bytes."""
    async with httpx.AsyncClient(timeout=60) as client:
        files = {"file": (filename, content, "image/jpeg")}
        resp = await client.post(f"{FACE_URL}/detect", files=files)
        resp.raise_for_status()
        return resp.json()


async def compute_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """Compute cosine similarity between two embeddings."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{FACE_URL}/similarity",
            params={"embedding1": str(embedding1), "embedding2": str(embedding2)},
        )
        resp.raise_for_status()
        return resp.json()["similarity"]


async def health_check() -> dict:
    """Check face service health."""
    async with httpx.AsyncClient(timeout=5) as client:
        resp = await client.get(f"{FACE_URL}/health")
        resp.raise_for_status()
        return resp.json()
