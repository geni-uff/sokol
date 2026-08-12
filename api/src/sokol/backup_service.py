"""Backup/restore service — pg_dump + media tar, schedule file, restore."""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
import tarfile
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .audit import append_audit
from .backup_helpers import (
    backup_archive_name,
    compute_next_run,
    file_sha256,
    is_backup_due,
    parse_database_url,
    verify_sha256,
)
from .db import get_session_factory

logger = logging.getLogger("sokol.backup")

BACKUP_DIR = Path(os.getenv("SOKOL_BACKUP_DIR", "/data/backups"))
MEDIA_CACHE_DIR = Path(os.getenv("SOKOL_MEDIA_CACHE_DIR", "/data/media-cache"))
STAGING_DIR = Path(os.getenv("SOKOL_STAGING_DIR", "/data/staging"))
INCLUDE_STAGING = os.getenv("SOKOL_BACKUP_INCLUDE_STAGING", "0").lower() in (
    "1",
    "true",
    "yes",
)
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol"
)
SCHEDULE_FILENAME = "schedule.json"


def backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    return BACKUP_DIR


def schedule_path() -> Path:
    return backup_dir() / SCHEDULE_FILENAME


def load_schedule() -> dict:
    path = schedule_path()
    if not path.exists():
        return {
            "frequency": "daily",
            "retention_days": 7,
            "enabled": False,
            "last_run_at": None,
            "next_run_at": None,
        }
    return json.loads(path.read_text())


def save_schedule(schedule: dict) -> dict:
    path = schedule_path()
    path.write_text(json.dumps(schedule, indent=2, sort_keys=True) + "\n")
    return schedule


def list_backup_archives() -> list[dict]:
    """List real sokol_backup_*.tar.gz files with size, sha256, created_at."""
    root = backup_dir()
    items: list[dict] = []
    for archive in sorted(root.glob("sokol_backup_*.tar.gz"), reverse=True):
        sha_path = Path(str(archive) + ".sha256")
        checksum = None
        if sha_path.exists():
            checksum = sha_path.read_text().strip().split()[0]
        else:
            checksum = file_sha256(archive)
        items.append(
            {
                "name": archive.name,
                "path": str(archive),
                "size_bytes": archive.stat().st_size,
                "size_mb": round(archive.stat().st_size / (1024 * 1024), 2),
                "sha256": checksum,
                "created_at": datetime.fromtimestamp(
                    archive.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
            }
        )
    return items


def _pg_env(parts: dict[str, str]) -> dict[str, str]:
    env = os.environ.copy()
    env["PGPASSWORD"] = parts["password"]
    return env


def create_backup(*, include_media: bool = True) -> dict:
    """Create sokol_backup_YYYYMMDD_HHMMSS.tar.gz with DB dump (+ media; staging opt-in)."""
    root = backup_dir()
    when = datetime.now(timezone.utc)
    archive_name = backup_archive_name(when)
    archive_path = root / archive_name
    sha_path = Path(str(archive_path) + ".sha256")
    parts = parse_database_url(DATABASE_URL)

    with tempfile.TemporaryDirectory(prefix="sokol-backup-") as tmp:
        tmp_path = Path(tmp)
        dump_path = tmp_path / "database.dump"
        manifest = {
            "created_at": when.isoformat(),
            "database": parts["dbname"],
            "include_media": include_media,
            "include_staging": INCLUDE_STAGING,
            "format": "pg_dump_custom+tar",
        }
        (tmp_path / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        cmd = [
            "pg_dump",
            f"--host={parts['host']}",
            f"--port={parts['port']}",
            f"--username={parts['user']}",
            f"--dbname={parts['dbname']}",
            "--format=custom",
            "--compress=9",
            f"--file={dump_path}",
        ]
        subprocess.run(cmd, env=_pg_env(parts), check=True, capture_output=True)

        with tarfile.open(archive_path, "w:gz") as tar:
            tar.add(dump_path, arcname="database.dump")
            tar.add(tmp_path / "manifest.json", arcname="manifest.json")
            if include_media and MEDIA_CACHE_DIR.exists():
                tar.add(MEDIA_CACHE_DIR, arcname="media-cache")
            if INCLUDE_STAGING and STAGING_DIR.exists():
                tar.add(STAGING_DIR, arcname="staging")

    digest = file_sha256(archive_path)
    sha_path.write_text(f"{digest}  {archive_name}\n")

    # Apply retention if schedule known
    schedule = load_schedule()
    _apply_retention(int(schedule.get("retention_days") or 7))

    return {
        "name": archive_name,
        "path": str(archive_path),
        "sha256": digest,
        "size_bytes": archive_path.stat().st_size,
        "size_mb": round(archive_path.stat().st_size / (1024 * 1024), 2),
        "created_at": when.isoformat(),
    }


def _apply_retention(retention_days: int) -> None:
    if retention_days <= 0:
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
    for archive in backup_dir().glob("sokol_backup_*.tar.gz"):
        mtime = datetime.fromtimestamp(archive.stat().st_mtime, tz=timezone.utc)
        if mtime < cutoff:
            archive.unlink(missing_ok=True)
            Path(str(archive) + ".sha256").unlink(missing_ok=True)


def resolve_backup_file(backup_file: str) -> Path:
    """Resolve a backup filename to a path inside SOKOL_BACKUP_DIR (no path escape)."""
    name = Path(backup_file).name
    if not name.startswith("sokol_backup_") or not name.endswith(".tar.gz"):
        raise FileNotFoundError(f"Invalid backup file name: {backup_file}")
    path = backup_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Backup not found: {name}")
    return path


def restore_backup(backup_file: str, *, target_db: str | None = None) -> dict:
    """
    Restore from a .tar.gz backup.

    WARNING: when target_db is None (or equals the live DATABASE_URL dbname),
    the live database is dropped and recreated.
    """
    archive = resolve_backup_file(backup_file)
    sha_path = Path(str(archive) + ".sha256")
    if not sha_path.exists():
        raise ValueError(f"Missing SHA-256 sidecar for {archive.name}")
    expected = sha_path.read_text().strip().split()[0]
    if not verify_sha256(archive, expected):
        raise ValueError("Checksum mismatch — refusing restore")

    parts = parse_database_url(DATABASE_URL)
    restore_db = target_db or parts["dbname"]
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", restore_db):
        raise ValueError(f"Invalid target database name: {restore_db}")
    env = _pg_env(parts)

    with tempfile.TemporaryDirectory(prefix="sokol-restore-") as tmp:
        tmp_path = Path(tmp)
        with tarfile.open(archive, "r:gz") as tar:
            tar.extractall(tmp_path, filter="data")
        dump_path = tmp_path / "database.dump"
        if not dump_path.exists():
            raise ValueError("Archive missing database.dump")

        # Drop/recreate target DB via maintenance connection to 'postgres'
        admin_cmds = [
            ["psql", f"--host={parts['host']}", f"--port={parts['port']}",
             f"--username={parts['user']}", "--dbname=postgres",
             "-v", "ON_ERROR_STOP=1",
             "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{restore_db}' AND pid <> pg_backend_pid();"],
            ["psql", f"--host={parts['host']}", f"--port={parts['port']}",
             f"--username={parts['user']}", "--dbname=postgres",
             "-v", "ON_ERROR_STOP=1",
             "-c", f'DROP DATABASE IF EXISTS "{restore_db}";'],
            ["psql", f"--host={parts['host']}", f"--port={parts['port']}",
             f"--username={parts['user']}", "--dbname=postgres",
             "-v", "ON_ERROR_STOP=1",
             "-c", f'CREATE DATABASE "{restore_db}";'],
        ]
        for cmd in admin_cmds:
            subprocess.run(cmd, env=env, check=True, capture_output=True)

        # Enable extensions commonly required
        for ext in ("vector", "postgis"):
            subprocess.run(
                [
                    "psql",
                    f"--host={parts['host']}",
                    f"--port={parts['port']}",
                    f"--username={parts['user']}",
                    f"--dbname={restore_db}",
                    "-c",
                    f'CREATE EXTENSION IF NOT EXISTS "{ext}";',
                ],
                env=env,
                capture_output=True,
            )

        result = subprocess.run(
            [
                "pg_restore",
                f"--host={parts['host']}",
                f"--port={parts['port']}",
                f"--username={parts['user']}",
                f"--dbname={restore_db}",
                "--no-owner",
                "--no-acl",
                str(dump_path),
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        # pg_restore returns non-zero on some benign warnings; check cases table
        sanity = _sanity_counts(parts, restore_db, env)

    return {
        "status": "restored",
        "backup": archive.name,
        "target_db": restore_db,
        "sha256_ok": True,
        "sanity": sanity,
        "pg_restore_returncode": result.returncode,
        "warnings": [
            line for line in (result.stderr or "").splitlines() if line.strip()
        ][:50],
    }


def _sanity_counts(parts: dict[str, str], dbname: str, env: dict[str, str]) -> dict:
    out: dict = {}
    for table in ("cases", "events", "users", "audit_log"):
        proc = subprocess.run(
            [
                "psql",
                f"--host={parts['host']}",
                f"--port={parts['port']}",
                f"--username={parts['user']}",
                f"--dbname={dbname}",
                "-tAc",
                f"SELECT COUNT(*) FROM {table};",
            ],
            env=env,
            capture_output=True,
            text=True,
        )
        out[f"{table}_count"] = (
            int(proc.stdout.strip()) if proc.returncode == 0 and proc.stdout.strip().isdigit() else "error"
        )
    return out


def run_scheduled_backup_if_due() -> dict | None:
    """Worker entry: run backup when schedule says due; update schedule timestamps."""
    schedule = load_schedule()
    if not is_backup_due(
        enabled=bool(schedule.get("enabled")),
        next_run_at=schedule.get("next_run_at"),
    ):
        return None

    logger.info("Scheduled backup due — starting")
    result = create_backup()
    now = datetime.now(timezone.utc)
    schedule["last_run_at"] = now.isoformat()
    schedule["next_run_at"] = compute_next_run(
        schedule.get("frequency") or "daily", now
    ).isoformat()
    save_schedule(schedule)
    logger.info("Scheduled backup complete: %s", result["name"])

    # Audit with null actor (system/worker)
    try:
        factory = get_session_factory()
        with factory() as db:
            append_audit(
                db,
                case_id=None,
                actor_user_id=None,
                action="backup.scheduled_run",
                payload={
                    "name": result["name"],
                    "sha256": result["sha256"],
                    "size_bytes": result["size_bytes"],
                },
            )
            db.commit()
    except Exception as e:
        logger.warning("Could not audit scheduled backup: %s", e)

    return result
