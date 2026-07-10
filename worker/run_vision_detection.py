"""Run vision detection on existing media in a case.

Usage:
    python run_vision_detection.py <case_id> [--models coco,firearm,threat] [--confidence 0.25]
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import httpx
from sqlalchemy import text

# Add parent dir to path for imports
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "api" / "src"))


async def detect_batch(
    image_paths: list[str],
    image_ids: list[str],
    models: list[str],
    base_url: str = "http://localhost:8007",
) -> list[dict]:
    """Call vision service batch detection."""
    async with httpx.AsyncClient(timeout=300.0) as client:
        response = await client.post(
            f"{base_url}/detect/batch",
            json={
                "image_ids": image_ids,
                "image_paths": image_paths,
                "models": models,
            },
        )
        response.raise_for_status()
        return response.json().get("results", [])


async def check_health(base_url: str = "http://localhost:8007") -> bool:
    """Check vision service health."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/health")
            return response.status_code == 200
    except Exception:
        return False


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Run vision detection on existing case media"
    )
    parser.add_argument("case_id", help="Case UUID")
    parser.add_argument(
        "--models",
        default="coco,firearm,threat",
        help="Models to use (comma-separated)",
    )
    parser.add_argument(
        "--confidence", type=float, default=0.25, help="Confidence threshold"
    )
    parser.add_argument(
        "--vision-url", default="http://localhost:8007", help="Vision service URL"
    )
    parser.add_argument(
        "--ufdr-extract-dir",
        default="/data/ufdr-extract",
        help="UFDR extract directory",
    )
    parser.add_argument(
        "--media-cache", default="/data/media-cache", help="Media cache directory"
    )
    args = parser.parse_args()

    case_id = args.case_id
    models = [m.strip() for m in args.models.split(",")]

    print(f"[vision] Running vision detection on case {case_id}")
    print(f"[vision] Models: {models}")
    print(f"[vision] Confidence: {args.confidence}")

    # Check vision service
    if not asyncio.get_event_loop().run_until_complete(check_health(args.vision_url)):
        print("[vision] ERROR: Vision service not available")
        sys.exit(1)

    print("[vision] Vision service is healthy")

    # Get database session
    from sokol.db import get_session_factory

    factory = get_session_factory()
    with factory() as db:
        # Get all image media for this case (linked via messages or artifacts)
        rows = db.execute(
            text("""
                SELECT DISTINCT m.hash, m.storage_ref, m.mime_type
                FROM media m
                LEFT JOIN (
                    SELECT media_hash FROM messages WHERE case_id = :case_id AND media_hash IS NOT NULL
                ) msg ON msg.media_hash = m.hash
                LEFT JOIN (
                    SELECT media_hash FROM artifacts WHERE case_id = :case_id AND media_hash IS NOT NULL
                ) art ON art.media_hash = m.hash
                WHERE (msg.media_hash IS NOT NULL OR art.media_hash IS NOT NULL)
                  AND m.mime_type LIKE 'image/%'
            """),
            {"case_id": case_id},
        ).fetchall()

        print(f"[vision] Found {len(rows)} images in case")

        # Find images on disk
        ufdr_extract_dir = Path(args.ufdr_extract_dir)
        image_paths = []
        image_hashes = []

        for row in rows:
            media_hash = row[0]
            storage_ref = row[1]

            # Get file path
            local_path = None
            if "path" in storage_ref:
                local_path = storage_ref["path"]
            elif "local_path" in storage_ref:
                local_path = storage_ref["local_path"]
            elif "source_member" in storage_ref:
                # Check media cache
                cache_path = Path(args.media_cache) / media_hash
                if cache_path.exists():
                    local_path = str(cache_path)

            if not local_path:
                continue

            # Find file on disk
            file_path = None
            basename = Path(local_path).name

            # Try direct path
            direct = ufdr_extract_dir / local_path
            if direct.exists():
                file_path = direct
            else:
                # Glob for basename
                for candidate in ufdr_extract_dir.rglob(basename):
                    if candidate.is_file():
                        file_path = candidate
                        break

            if file_path and file_path.exists():
                # Convert host path to container path for vision service
                host_path = str(file_path)
                if host_path.startswith(
                    "/home/mateuspestana/Documents/Sokol/data/media-cache/"
                ):
                    container_path = host_path.replace(
                        "/home/mateuspestana/Documents/Sokol/data/media-cache/",
                        "/data/media-cache/",
                    )
                else:
                    container_path = host_path
                image_paths.append(container_path)
                image_hashes.append(media_hash)

        print(f"[vision] Found {len(image_paths)} images on disk")

        if not image_paths:
            print("[vision] No images found on disk. Check UFDR_EXTRACT_DIR.")
            sys.exit(0)

        # Run detection in batches
        batch_size = 32
        total_detections = 0

        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i : i + batch_size]
            batch_hashes = image_hashes[i : i + batch_size]

            print(
                f"[vision] Processing batch {i // batch_size + 1}/{(len(image_paths) + batch_size - 1) // batch_size}..."
            )

            try:
                results = asyncio.get_event_loop().run_until_complete(
                    detect_batch(
                        image_paths=batch_paths,
                        image_ids=batch_hashes,
                        models=models,
                        base_url=args.vision_url,
                    )
                )

                # Insert detections
                for result in results:
                    image_id = result.get("image_id")
                    for det in result.get("detections", []):
                        if det["confidence"] < args.confidence:
                            continue

                        db.execute(
                            text("""
                                INSERT INTO image_detections 
                                (case_id, media_hash, model_name, class_name, class_id, confidence, bbox, pipeline_version)
                                VALUES (:case_id, :media_hash, :model, :class, :cls_id, :conf, :bbox, :version)
                            """),
                            {
                                "case_id": case_id,
                                "media_hash": image_id,
                                "model": det["model"],
                                "class": det["class_name"],
                                "cls_id": det["class_id"],
                                "conf": det["confidence"],
                                "bbox": json.dumps(det["bbox"]),
                                "version": "yolov8n-v1",
                            },
                        )
                        total_detections += 1

                db.commit()

            except Exception as e:
                print(f"[vision] Error processing batch: {e}")
                continue

        print(f"[vision] Done! Inserted {total_detections} detections")


if __name__ == "__main__":
    main()
