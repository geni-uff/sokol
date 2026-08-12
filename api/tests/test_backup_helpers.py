"""Unit tests for backup helpers (v2-11)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from sokol.backup_helpers import (
    backup_archive_name,
    compute_next_run,
    file_sha256,
    is_backup_due,
    parse_database_url,
    verify_sha256,
)


def test_parse_database_url():
    parts = parse_database_url("postgresql://sokol:secret@localhost:5433/sokol")
    assert parts == {
        "user": "sokol",
        "password": "secret",
        "host": "localhost",
        "port": "5433",
        "dbname": "sokol",
    }


def test_compute_next_run_daily_weekly_monthly():
    base = datetime(2026, 8, 12, 12, 0, 0, tzinfo=timezone.utc)
    assert compute_next_run("daily", base).day == 13
    assert compute_next_run("weekly", base).day == 19
    assert compute_next_run("monthly", base).month == 9


def test_is_backup_due():
    now = datetime(2026, 8, 12, 15, 0, 0, tzinfo=timezone.utc)
    assert is_backup_due(enabled=False, next_run_at="2026-08-12T10:00:00+00:00", now=now) is False
    assert is_backup_due(enabled=True, next_run_at=None, now=now) is True
    assert is_backup_due(enabled=True, next_run_at="2026-08-12T14:00:00+00:00", now=now) is True
    assert is_backup_due(enabled=True, next_run_at="2026-08-12T16:00:00+00:00", now=now) is False


def test_backup_archive_name_format():
    name = backup_archive_name(datetime(2026, 8, 12, 21, 30, 5, tzinfo=timezone.utc))
    assert name == "sokol_backup_20260812_213005.tar.gz"


def test_sha256_roundtrip(tmp_path: Path):
    p = tmp_path / "blob.bin"
    p.write_bytes(b"sokol-backup-fixture")
    digest = file_sha256(p)
    assert len(digest) == 64
    assert verify_sha256(p, digest) is True
    assert verify_sha256(p, "0" * 64) is False
