"""SOKOL ML Services — OCR, ASR, Vision, Face, Plate detection."""

from __future__ import annotations

from .ocr import OCRService
from .asr import ASRService
from .vision import VisionService
from .plate import PlateService

__all__ = ["OCRService", "ASRService", "VisionService", "PlateService"]
