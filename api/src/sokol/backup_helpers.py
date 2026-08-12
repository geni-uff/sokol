"""Pure helpers for backup schedule and integrity (v2-11)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse


def parse_database_url(url: str) -> dict[str, str]:
    """Parse DATABASE_URL into host/port/user/password/dbname."""
    parsed = urlparse(url)
    if parsed.scheme not in ("postgresql", "postgres"):
        raise ValueError(f"Unsupported database URL scheme: {parsed.scheme}")
    return {
        "user": parsed.username or "",
        "password": parsed.password or "",
        "host": parsed.hostname or "localhost",
        "port": str(parsed.port or 5432),
        "dbname": (parsed.path or "/").lstrip("/") or "sokol",
    }


def file_sha256(path: Path) -> str:
    """SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_sha256(path: Path, expected: str) -> bool:
    """Return True if file digest matches expected hex (case-insensitive)."""
    return file_sha256(path).lower() == expected.strip().lower()


def compute_next_run(frequency: str, from_dt: datetime | None = None) -> datetime:
    """Next run instant for daily/weekly/monthly schedule (UTC)."""
    now = from_dt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    freq = frequency.lower().strip()
    if freq == "daily":
        return now + timedelta(days=1)
    if freq == "weekly":
        return now + timedelta(weeks=1)
    if freq == "monthly":
        return now + timedelta(days=30)
    raise ValueError(f"Unsupported frequency: {frequency}")


def is_backup_due(
    *,
    enabled: bool,
    next_run_at: str | None,
    now: datetime | None = None,
) -> bool:
    """Whether a scheduled backup should run now."""
    if not enabled:
        return False
    if not next_run_at:
        return True
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    due = datetime.fromisoformat(next_run_at.replace("Z", "+00:00"))
    if due.tzinfo is None:
        due = due.replace(tzinfo=timezone.utc)
    return current >= due


def backup_archive_name(when: datetime | None = None) -> str:
    """Canonical archive basename: sokol_backup_YYYYMMDD_HHMMSS.tar.gz"""
    ts = when or datetime.now(timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return f"sokol_backup_{ts.astimezone(timezone.utc).strftime('%Y%m%d_%H%M%S')}.tar.gz"
