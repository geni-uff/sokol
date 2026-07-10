"""SOKOL API — Vision detection endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import text

from .db import get_session_factory

router = APIRouter(prefix="/vision", tags=["vision"])


class DetectionItem(BaseModel):
    id: str
    media_hash: str
    model_name: str
    class_name: str
    class_id: int
    confidence: float
    bbox: list[float]
    pipeline_version: Optional[str]
    created_at: str


class DetectionStats(BaseModel):
    class_name: str
    count: int
    avg_confidence: float
    max_confidence: float


class MediaWithDetections(BaseModel):
    hash: str
    mime_type: Optional[str]
    size_bytes: Optional[int]
    detections: list[DetectionItem]
    max_confidence: float
    detection_count: int


# ── Endpoints ──────────────────────────────────────────────────────────────
@router.get("/{case_id}/detections", response_model=list[DetectionItem])
def list_detections(
    case_id: str,
    class_name: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    model_name: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
):
    """List vision detections for a case with optional filters."""
    factory = get_session_factory()
    with factory() as db:
        query = """
            SELECT id, media_hash, model_name, class_name, class_id, 
                   confidence, bbox, pipeline_version, created_at
            FROM image_detections
            WHERE case_id = :case_id
              AND confidence >= :min_confidence
        """
        params = {"case_id": case_id, "min_confidence": min_confidence}

        if class_name:
            query += " AND class_name = :class_name"
            params["class_name"] = class_name

        if model_name:
            query += " AND model_name = :model_name"
            params["model_name"] = model_name

        query += " ORDER BY confidence DESC LIMIT :limit"
        params["limit"] = limit

        rows = db.execute(text(query), params).fetchall()
        return [
            DetectionItem(
                id=r[0],
                media_hash=r[1],
                model_name=r[2],
                class_name=r[3],
                class_id=r[4],
                confidence=r[5],
                bbox=r[6] if isinstance(r[6], list) else [],
                pipeline_version=r[7],
                created_at=str(r[8]),
            )
            for r in rows
        ]


@router.get("/{case_id}/detections/stats", response_model=list[DetectionStats])
def detection_stats(
    case_id: str,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
):
    """Get detection statistics by class for a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT class_name, 
                       COUNT(*) as count,
                       AVG(confidence) as avg_confidence,
                       MAX(confidence) as max_confidence
                FROM image_detections
                WHERE case_id = :case_id
                  AND confidence >= :min_confidence
                GROUP BY class_name
                ORDER BY count DESC
            """),
            {"case_id": case_id, "min_confidence": min_confidence},
        ).fetchall()
        return [
            DetectionStats(
                class_name=r[0],
                count=r[1],
                avg_confidence=round(r[2], 4),
                max_confidence=round(r[3], 4),
            )
            for r in rows
        ]


@router.get("/{case_id}/media/detections", response_model=list[MediaWithDetections])
def media_with_detections(
    case_id: str,
    class_name: Optional[str] = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(100, ge=1, le=500),
):
    """List media items that have detections, with their detection details."""
    factory = get_session_factory()
    with factory() as db:
        query = """
            SELECT DISTINCT
                m.hash,
                m.mime_type,
                m.size_bytes,
                COUNT(d.id) OVER (PARTITION BY m.hash) as detection_count,
                MAX(d.confidence) OVER (PARTITION BY m.hash) as max_confidence
            FROM media m
            INNER JOIN image_detections d ON d.media_hash = m.hash
            WHERE d.case_id = :case_id
              AND d.confidence >= :min_confidence
        """
        params = {"case_id": case_id, "min_confidence": min_confidence}

        if class_name:
            query += " AND d.class_name = :class_name"
            params["class_name"] = class_name

        query += " ORDER BY max_confidence DESC LIMIT :limit"
        params["limit"] = limit

        media_rows = db.execute(text(query), params).fetchall()

        results = []
        for media_row in media_rows:
            media_hash = media_row[0]

            # Get detections for this media
            det_rows = db.execute(
                text("""
                    SELECT id, media_hash, model_name, class_name, class_id,
                           confidence, bbox, pipeline_version, created_at
                    FROM image_detections
                    WHERE media_hash = :media_hash
                      AND case_id = :case_id
                      AND confidence >= :min_confidence
                    ORDER BY confidence DESC
                """),
                {
                    "media_hash": media_hash,
                    "case_id": case_id,
                    "min_confidence": min_confidence,
                },
            ).fetchall()

            detections = [
                DetectionItem(
                    id=r[0],
                    media_hash=r[1],
                    model_name=r[2],
                    class_name=r[3],
                    class_id=r[4],
                    confidence=r[5],
                    bbox=r[6] if isinstance(r[6], list) else [],
                    pipeline_version=r[7],
                    created_at=str(r[8]),
                )
                for r in det_rows
            ]

            results.append(
                MediaWithDetections(
                    hash=media_hash,
                    mime_type=media_row[1],
                    size_bytes=media_row[2],
                    detections=detections,
                    max_confidence=round(media_row[4], 4) if media_row[4] else 0,
                    detection_count=media_row[3],
                )
            )

        return results


@router.get("/{case_id}/detections/classes")
def list_classes(case_id: str):
    """List all detected classes in a case."""
    factory = get_session_factory()
    with factory() as db:
        rows = db.execute(
            text("""
                SELECT DISTINCT class_name, COUNT(*) as count
                FROM image_detections
                WHERE case_id = :case_id
                GROUP BY class_name
                ORDER BY count DESC
            """),
            {"case_id": case_id},
        ).fetchall()
        return [{"class_name": r[0], "count": r[1]} for r in rows]
