"""Shared extension -> (kind, mime) classification used across UFDR ingestion.

Single source of truth so artifact creation, media population, and the
filesystem-walk media inventory agree on how a given extension is typed —
previously `ufdr_parser.py` and `fs_walk.py` each kept their own partial
tables, so files recognized by one path fell back to `application/octet-stream`
in another.
"""

from __future__ import annotations

EXTENSION_MAP: dict[str, tuple[str, str]] = {
    # image
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),
    ".gif": ("image", "image/gif"),
    ".webp": ("image", "image/webp"),
    ".heic": ("image", "image/heic"),
    ".heif": ("image", "image/heic"),
    ".bmp": ("image", "image/bmp"),
    ".tiff": ("image", "image/tiff"),
    ".tif": ("image", "image/tiff"),
    # audio
    ".mp3": ("audio", "audio/mpeg"),
    ".m4a": ("audio", "audio/mp4"),
    ".opus": ("audio", "audio/opus"),
    ".aac": ("audio", "audio/aac"),
    ".wav": ("audio", "audio/wav"),
    ".ogg": ("audio", "audio/ogg"),
    ".flac": ("audio", "audio/flac"),
    # video
    ".mp4": ("video", "video/mp4"),
    ".mov": ("video", "video/quicktime"),
    ".m4v": ("video", "video/mp4"),
    ".3gp": ("video", "video/3gpp"),
    ".3gpp": ("video", "video/3gpp"),
    ".avi": ("video", "video/x-msvideo"),
    ".webm": ("video", "video/webm"),
    # document
    ".pdf": ("document", "application/pdf"),
    ".doc": ("document", "application/msword"),
    ".docx": (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".xls": ("document", "application/vnd.ms-excel"),
    ".xlsx": (
        "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    ".ppt": ("document", "application/vnd.ms-powerpoint"),
    ".pptx": (
        "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    ".txt": ("document", "text/plain"),
    ".csv": ("document", "text/csv"),
    ".html": ("document", "text/html"),
    ".json": ("document", "application/json"),
    ".vcf": ("document", "text/vcard"),
    ".eml": ("document", "message/rfc822"),
}

KIND_TAG = {
    "image": "Image",
    "audio": "Audio",
    "video": "Video",
    "document": "Document",
}


def classify_extension(ext: str) -> tuple[str, str] | None:
    """Return (kind, mime) for a lowercase-normalized file extension, or None."""
    return EXTENSION_MAP.get(ext.lower())
