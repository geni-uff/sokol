"""SOKOL ASR Service — Speech-to-text transcription using faster-whisper."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel

app = FastAPI(title="SOKOL ASR Service", version="0.8.2")

ASR_MODEL = None


def load_model():
    global ASR_MODEL
    model_size = os.getenv("SOKOL_ASR_MODEL", "base")
    device = os.getenv("SOKOL_ASR_DEVICE", "cpu")
    print(f"[asr] Loading faster-whisper model: {model_size} on {device}...")

    from faster_whisper import WhisperModel

    compute_type = "float16" if device == "cuda" else "int8"
    ASR_MODEL = WhisperModel(model_size, device=device, compute_type=compute_type)
    print(f"[asr] Model loaded: {model_size}")


class Segment(BaseModel):
    start_ms: float
    end_ms: float
    text: str
    confidence: float
    speaker: str | None = None


class TranscriptionResponse(BaseModel):
    segments: list[Segment]
    language: str | None = None
    duration_ms: float = 0
    text: str = ""


@app.on_event("startup")
async def startup():
    load_model()


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "engine": "faster-whisper",
        "model": os.getenv("SOKOL_ASR_MODEL", "base"),
    }


@app.post("/api/transcribe", response_model=TranscriptionResponse)
async def transcribe_upload(
    file: UploadFile = File(...),
    language: str | None = None,
):
    if ASR_MODEL is None:
        raise HTTPException(status_code=503, detail="ASR model not loaded")

    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        return _transcribe(tmp_path, language)
    finally:
        os.unlink(tmp_path)


@app.post("/api/transcribe/path", response_model=TranscriptionResponse)
async def transcribe_path(body: dict):
    if ASR_MODEL is None:
        raise HTTPException(status_code=503, detail="ASR model not loaded")

    media_path = body.get("media_path", "")
    if not media_path:
        raise HTTPException(status_code=400, detail="media_path required")

    p = Path(media_path)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {media_path}")

    return _transcribe(str(p), body.get("language"))


def _transcribe(path: str, language: str | None) -> TranscriptionResponse:
    segments_gen, info = ASR_MODEL.transcribe(
        path,
        language=language,
        beam_size=5,
        vad_filter=True,
    )

    segments = []
    total_text = []
    for seg in segments_gen:
        segments.append(
            Segment(
                start_ms=round(seg.start * 1000, 1),
                end_ms=round(seg.end * 1000, 1),
                text=seg.text.strip(),
                confidence=round(float(seg.avg_logprob), 4) if seg.avg_logprob else 0.0,
            )
        )
        total_text.append(seg.text.strip())

    duration_ms = segments[-1].end_ms if segments else 0

    return TranscriptionResponse(
        segments=segments,
        language=info.language,
        duration_ms=duration_ms,
        text="\n".join(total_text),
    )


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8009)
