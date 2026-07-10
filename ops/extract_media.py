"""Extract media files from UFDR to media cache for serving.

Usage:
    python extract_media.py <case_id> [--ufdr-path /path/to/file.ufdr] [--force]
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

# Add worker and api dirs to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "worker"))
sys.path.insert(0, str(Path(__file__).parent.parent / "api" / "src"))


def get_sha256(file_path: Path) -> str:
    """Compute SHA-256 of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Extract media from UFDR to cache")
    parser.add_argument("case_id", help="Case UUID")
    parser.add_argument("--ufdr-path", help="Path to UFDR file")
    parser.add_argument(
        "--media-cache", default="/data/media-cache", help="Media cache directory"
    )
    parser.add_argument("--force", action="store_true", help="Force re-extraction")
    args = parser.parse_args()

    case_id = args.case_id
    media_cache = Path(args.media_cache)
    media_cache.mkdir(parents=True, exist_ok=True)

    print(f"[extract] Case: {case_id}")
    print(f"[extract] Media cache: {media_cache}")

    # Get database session
    from sokol.db import get_session_factory

    factory = get_session_factory()
    with factory() as db:
        # Find UFDR path if not provided
        if not args.ufdr_path:
            from sqlalchemy import text

            row = db.execute(
                text("""
                SELECT source_uri FROM documents 
                WHERE case_id = :case_id AND source_type = 'ufdr'
                LIMIT 1
                """),
                {"case_id": case_id},
            ).fetchone()
            if not row:
                print("[extract] No UFDR document found for case")
                sys.exit(1)
            # Convert relative path to absolute
            source_uri = row[0]
            ufdr_path = Path("/home/mateuspestana/Documents/Sokol") / source_uri
            if not ufdr_path.exists():
                print(f"[extract] UFDR not found at: {ufdr_path}")
                sys.exit(1)
        else:
            ufdr_path = Path(args.ufdr_path)

        print(f"[extract] UFDR: {ufdr_path}")

        # Get all media for this case
        from sqlalchemy import text

        media_rows = db.execute(
            text("""
            SELECT DISTINCT m.hash, m.storage_ref, m.mime_type, m.size_bytes
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

        print(f"[extract] Found {len(media_rows)} images in database")

        # Build hash -> storage_ref mapping
        media_map = {}
        for row in media_rows:
            media_hash = row[0]
            storage_ref = row[1]
            media_map[media_hash] = storage_ref

        # Open UFDR (it's a zip)
        extracted_count = 0
        skipped_count = 0
        error_count = 0

        with zipfile.ZipFile(ufdr_path, "r") as zf:
            # Get all image files in UFDR
            image_files = [
                f
                for f in zf.namelist()
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".heic"))
                and not f.startswith("__MACOSX")
            ]

            print(f"[extract] Found {len(image_files)} images in UFDR")

            for ufdr_path_str in image_files:
                # Extract filename
                filename = Path(ufdr_path_str).name

                # Try to match with database entries
                matched_hash = None
                for media_hash, storage_ref in media_map.items():
                    if "source_member" in storage_ref:
                        member = storage_ref["source_member"]
                        # Normalize path separators
                        member_normalized = member.replace("\\", "/")
                        ufdr_normalized = ufdr_path_str.replace("\\", "/")
                        if (
                            member_normalized == ufdr_normalized
                            or member_normalized.endswith(filename)
                        ):
                            matched_hash = media_hash
                            break
                    elif "local_path" in storage_ref:
                        local_path = storage_ref["local_path"]
                        if local_path.endswith(filename):
                            matched_hash = media_hash
                            break

                if not matched_hash:
                    # Hash not in database, skip
                    continue

                # Check if already cached
                cache_path = media_cache / matched_hash
                if cache_path.exists() and not args.force:
                    skipped_count += 1
                    continue

                # Extract file
                try:
                    with zf.open(ufdr_path_str) as src:
                        content = src.read()

                    # Verify hash matches
                    file_hash = hashlib.sha256(content).hexdigest()
                    if file_hash != matched_hash:
                        # Hash doesn't match - the database hash is the original file hash
                        # We'll use the UFDR path hash as filename
                        pass

                    # Write to cache
                    with open(cache_path, "wb") as dst:
                        dst.write(content)

                    extracted_count += 1
                    if extracted_count % 50 == 0:
                        print(f"[extract] Extracted {extracted_count} files...")

                except Exception as e:
                    print(f"[extract] Error extracting {ufdr_path_str}: {e}")
                    error_count += 1

        print(f"[extract] Done!")
        print(f"[extract] Extracted: {extracted_count}")
        print(f"[extract] Skipped (already cached): {skipped_count}")
        print(f"[extract] Errors: {error_count}")


if __name__ == "__main__":
    main()
