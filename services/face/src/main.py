"""SOKOL Face Recognition Service — InsightFace detection + embeddings for cross-case search."""

from __future__ import annotations

import io
import os
import tempfile
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI(title="SOKOL Face Recognition Service", version="0.8.2")

# ── Configuration ───────────────────────────────────────────────────────────
MODEL_DIR = Path(os.getenv("SOKOL_MODEL_DIR", "/data/models/face"))
CONFIDENCE_THRESHOLD = float(os.getenv("SOKOL_FACE_CONF", "0.5"))
SIMILARITY_THRESHOLD = float(os.getenv("SOKOL_FACE_SIM", "0.4"))

# ── Models ──────────────────────────────────────────────────────────────────
FACE_APP = None


def load_models():
    """Load InsightFace models on startup."""
    global FACE_APP
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    print("[face] Loading InsightFace model...")
    from insightface.app import FaceAnalysis

    FACE_APP = FaceAnalysis(
        name="buffalo_l",
        root=str(MODEL_DIR),
        providers=["CPUExecutionProvider"],
    )
    FACE_APP.prepare(ctx_id=0, det_size=(640, 640))
    print("[face] InsightFace model loaded (buffalo_l)")


# ── Schemas ─────────────────────────────────────────────────────────────────
class FaceDetection(BaseModel):
    bbox: list[float]  # [x1, y1, x2, y2]
    confidence: float
    embedding: list[float]  # 512-dim vector
    age: Optional[int] = None
    gender: Optional[str] = None


class FaceDetectResult(BaseModel):
    image_id: Optional[str] = None
    faces: list[FaceDetection]
    face_count: int


class FaceSearchRequest(BaseModel):
    embedding: list[float]
    threshold: float = SIMILARITY_THRESHOLD
    limit: int = 20
    exclude_case_id: Optional[str] = None


class FaceMatch(BaseModel):
    face_id: str
    case_id: str
    media_hash: str
    bbox: list[float]
    confidence: float
    similarity: float
    label: Optional[str] = None


class FaceSearchResult(BaseModel):
    matches: list[FaceMatch]
    total: int
    threshold: float


class FaceRegisterRequest(BaseModel):
    label: str
    embedding: list[float]


# ── Endpoints ───────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    load_models()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": "buffalo_l" if FACE_APP else None,
        "loaded": FACE_APP is not None,
    }


@app.post("/detect", response_model=FaceDetectResult)
async def detect_faces(
    file: UploadFile = File(...),
    image_id: Optional[str] = None,
):
    """Detect faces and extract embeddings from an image."""
    if not FACE_APP:
        raise HTTPException(status_code=503, detail="Face model not loaded")

    content = await file.read()
    nparr = np.frombuffer(content, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        raise HTTPException(status_code=400, detail="Invalid image")

    faces = FACE_APP.get(img)
    detections = []
    for face in faces:
        if face.det_score < CONFIDENCE_THRESHOLD:
            continue
        bbox = face.bbox.tolist()
        embedding = face.normed_embedding.tolist()
        age = int(face.age) if hasattr(face, "age") else None
        gender = "M" if face.gender == 1 else "F" if hasattr(face, "gender") else None
        detections.append(
            FaceDetection(
                bbox=[round(v, 2) for v in bbox],
                confidence=round(float(face.det_score), 4),
                embedding=embedding,
                age=age,
                gender=gender,
            )
        )

    return FaceDetectResult(
        image_id=image_id,
        faces=detections,
        face_count=len(detections),
    )


@app.post("/detect/batch")
async def detect_faces_batch(
    files: list[UploadFile] = File(...),
):
    """Detect faces in multiple images."""
    if not FACE_APP:
        raise HTTPException(status_code=503, detail="Face model not loaded")

    results = []
    for file in files:
        content = await file.read()
        nparr = np.frombuffer(content, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            results.append(
                FaceDetectResult(image_id=file.filename, faces=[], face_count=0)
            )
            continue

        faces = FACE_APP.get(img)
        detections = []
        for face in faces:
            if face.det_score < CONFIDENCE_THRESHOLD:
                continue
            detections.append(
                FaceDetection(
                    bbox=[round(v, 2) for v in face.bbox.tolist()],
                    confidence=round(float(face.det_score), 4),
                    embedding=face.normed_embedding.tolist(),
                )
            )
        results.append(
            FaceDetectResult(
                image_id=file.filename,
                faces=detections,
                face_count=len(detections),
            )
        )
    return results


@app.post("/similarity")
async def compute_similarity(
    embedding1: list[float],
    embedding2: list[float],
):
    """Compute cosine similarity between two face embeddings."""
    a = np.array(embedding1, dtype=np.float32)
    b = np.array(embedding2, dtype=np.float32)
    similarity = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
    return {"similarity": round(similarity, 4)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8011)
