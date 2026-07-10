#!/usr/bin/env python3
"""SOKOL — Backup, restore, and export utilities."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import psycopg2
from psycopg2.extras import RealDictCursor


# ── Config ─────────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol"
)
BACKUP_DIR = Path(os.getenv("SOKOL_BACKUP_DIR", "/data/backups"))
EXPORT_DIR = Path(os.getenv("SOKOL_EXPORT_DIR", "/data/exports"))


# ── Backup ─────────────────────────────────────────────────────────────────
def backup_database(backup_name: Optional[str] = None) -> Path:
    """Full database backup using pg_dump."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    if backup_name is None:
        backup_name = (
            f"sokol_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        )

    backup_path = BACKUP_DIR / f"{backup_name}.sql.gz"

    # Parse DATABASE_URL
    url = DATABASE_URL.replace("postgresql://", "")
    auth, rest = url.split("@", 1)
    user, password = auth.split(":", 1)
    host_port, dbname = rest.split("/", 1)
    host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "5432")

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    cmd = [
        "pg_dump",
        f"--host={host}",
        f"--port={port}",
        f"--username={user}",
        f"--dbname={dbname}",
        "--format=custom",
        "--compress=9",
        f"--file={backup_path}",
    ]

    subprocess.run(cmd, env=env, check=True)

    # Generate checksum
    checksum = _file_checksum(backup_path)
    checksum_path = backup_path.with_suffix(".sql.gz.sha256")
    checksum_path.write_text(f"{checksum}  {backup_path.name}\n")

    print(f"Backup created: {backup_path}")
    print(f"Checksum: {checksum}")

    return backup_path


def list_backups() -> list[dict]:
    """List available backups."""
    if not BACKUP_DIR.exists():
        return []

    backups = []
    for f in sorted(BACKUP_DIR.glob("sokol_backup_*.sql.gz"), reverse=True):
        checksum_file = f.with_suffix(".sql.gz.sha256")
        backups.append(
            {
                "name": f.stem.replace(".sql", ""),
                "path": str(f),
                "size_bytes": f.stat().st_size,
                "created_at": datetime.fromtimestamp(
                    f.stat().st_mtime, tz=timezone.utc
                ).isoformat(),
                "checksum": checksum_file.read_text().strip().split()[0]
                if checksum_file.exists()
                else None,
            }
        )
    return backups


# ── Restore ────────────────────────────────────────────────────────────────
def restore_database(backup_path: str, target_db: Optional[str] = None) -> dict:
    """Restore database to a target (default: same database)."""
    backup_file = Path(backup_path)
    if not backup_file.exists():
        raise FileNotFoundError(f"Backup not found: {backup_path}")

    # Verify checksum
    checksum_file = backup_file.with_suffix(".sql.gz.sha256")
    if checksum_file.exists():
        expected = checksum_file.read_text().strip().split()[0]
        actual = _file_checksum(backup_file)
        if expected != actual:
            raise ValueError(f"Checksum mismatch: expected {expected}, got {actual}")

    url = DATABASE_URL.replace("postgresql://", "")
    auth, rest = url.split("@", 1)
    user, password = auth.split(":", 1)
    host_port, dbname = rest.split("/", 1)
    host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "5432")

    restore_db = target_db or dbname

    env = os.environ.copy()
    env["PGPASSWORD"] = password

    # Drop and recreate if restoring to same DB
    if restore_db == dbname:
        subprocess.run(
            [
                "psql",
                f"--host={host}",
                f"--port={port}",
                f"--username={user}",
                "--command",
                f"DROP DATABASE IF EXISTS {dbname};",
            ],
            env=env,
            check=True,
        )
        subprocess.run(
            [
                "psql",
                f"--host={host}",
                f"--port={port}",
                f"--username={user}",
                "--command",
                f"CREATE DATABASE {dbname};",
            ],
            env=env,
            check=True,
        )

    cmd = [
        "pg_restore",
        f"--host={host}",
        f"--port={port}",
        f"--username={user}",
        f"--dbname={restore_db}",
        "--no-owner",
        "--no-acl",
        str(backup_file),
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)

    # Run sanity queries
    sanity = _run_sanity_queries(host, port, user, password, restore_db)

    return {
        "status": "restored",
        "backup": str(backup_file),
        "target_db": restore_db,
        "sanity": sanity,
        "warnings": result.stderr.split("\n") if result.returncode != 0 else [],
    }


def _run_sanity_queries(host, port, user, password, dbname) -> dict:
    """Run sanity checks after restore."""
    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname
    )
    conn.autocommit = True

    checks = {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Check core tables exist
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        checks["tables"] = [r["table_name"] for r in cur.fetchall()]

        # Check row counts
        for table in ["cases", "events", "messages", "chunks", "users"]:
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM {table}")
                checks[f"{table}_count"] = cur.fetchone()["cnt"]
            except Exception:
                checks[f"{table}_count"] = "error"

        # Check audit chain integrity
        try:
            cur.execute("SELECT COUNT(*) as cnt FROM audit_log")
            checks["audit_log_count"] = cur.fetchone()["cnt"]
        except Exception:
            checks["audit_log_count"] = "error"

    conn.close()
    return checks


# ── Export ─────────────────────────────────────────────────────────────────
def export_case(case_id: str) -> Path:
    """Export a case with manifest SHA-256."""
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    url = DATABASE_URL.replace("postgresql://", "")
    auth, rest = url.split("@", 1)
    user, password = auth.split(":", 1)
    host_port, dbname = rest.split("/", 1)
    host, port = host_port.split(":", 1) if ":" in host_port else (host_port, "5432")

    conn = psycopg2.connect(
        host=host, port=port, user=user, password=password, dbname=dbname
    )
    conn.autocommit = True

    export_data = {
        "case_id": case_id,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
    }

    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        # Export case metadata
        cur.execute("SELECT * FROM cases WHERE id = %s", (case_id,))
        case_row = cur.fetchone()
        if not case_row:
            conn.close()
            raise ValueError(f"Case not found: {case_id}")
        export_data["case"] = dict(case_row)

        # Export events
        cur.execute("SELECT * FROM events WHERE case_id = %s ORDER BY ts", (case_id,))
        export_data["events"] = [dict(r) for r in cur.fetchall()]

        # Export messages
        cur.execute("SELECT * FROM messages WHERE case_id = %s ORDER BY ts", (case_id,))
        export_data["messages"] = [dict(r) for r in cur.fetchall()]

        # Export chunks
        cur.execute(
            "SELECT id, document_id, source_type, text, meta FROM chunks WHERE case_id = %s",
            (case_id,),
        )
        export_data["chunks"] = [dict(r) for r in cur.fetchall()]

        # Export audit log for this case
        cur.execute(
            """
            SELECT * FROM audit_log
            WHERE case_id = %s
            ORDER BY created_at
        """,
            (case_id,),
        )
        export_data["audit_log"] = [dict(r) for r in cur.fetchall()]

        # Export media references
        cur.execute(
            """
            SELECT DISTINCT media_hash FROM messages
            WHERE case_id = %s AND media_hash IS NOT NULL
        """,
            (case_id,),
        )
        export_data["media_hashes"] = [r["media_hash"] for r in cur.fetchall()]

    conn.close()

    # Generate manifest
    export_json = json.dumps(export_data, default=str, sort_keys=True)
    manifest_hash = hashlib.sha256(export_json.encode()).hexdigest()

    export_data["manifest"] = {
        "sha256": manifest_hash,
        "size_bytes": len(export_json),
        "event_count": len(export_data["events"]),
        "message_count": len(export_data["messages"]),
        "chunk_count": len(export_data["chunks"]),
        "audit_entries": len(export_data["audit_log"]),
    }

    # Write export
    export_path = (
        EXPORT_DIR
        / f"case_{case_id}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    )
    export_path.write_text(json.dumps(export_data, default=str, indent=2))

    # Write manifest separately
    manifest_path = export_path.with_suffix(".json.manifest")
    manifest_path.write_text(json.dumps(export_data["manifest"], indent=2))

    print(f"Case exported: {export_path}")
    print(f"Manifest SHA-256: {manifest_hash}")

    return export_path


def verify_export(export_path: str) -> dict:
    """Verify export manifest integrity."""
    path = Path(export_path)
    data = json.loads(path.read_text())

    manifest = data.get("manifest", {})
    export_copy = {k: v for k, v in data.items() if k != "manifest"}
    calculated_hash = hashlib.sha256(
        json.dumps(export_copy, default=str, sort_keys=True).encode()
    ).hexdigest()

    return {
        "valid": manifest.get("sha256") == calculated_hash,
        "expected": manifest.get("sha256"),
        "calculated": calculated_hash,
        "stats": {
            "events": manifest.get("event_count", 0),
            "messages": manifest.get("message_count", 0),
            "chunks": manifest.get("chunk_count", 0),
            "audit_entries": manifest.get("audit_entries", 0),
        },
    }


# ── Helpers ────────────────────────────────────────────────────────────────
def _file_checksum(path: Path) -> str:
    """SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


# ── CLI ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SOKOL Backup/Restore/Export")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("backup", help="Backup database")
    sub.add_parser("list", help="List backups")

    restore_p = sub.add_parser("restore", help="Restore database")
    restore_p.add_argument("backup_path", help="Path to backup file")
    restore_p.add_argument("--target-db", help="Target database name")

    export_p = sub.add_parser("export", help="Export case")
    export_p.add_argument("case_id", help="Case ID to export")

    verify_p = sub.add_parser("verify", help="Verify export")
    verify_p.add_argument("export_path", help="Path to export file")

    args = parser.parse_args()

    if args.command == "backup":
        backup_database()
    elif args.command == "list":
        for b in list_backups():
            print(f"{b['name']} ({b['size_bytes']} bytes) - {b['created_at']}")
    elif args.command == "restore":
        result = restore_database(args.backup_path, args.target_db)
        print(json.dumps(result, indent=2))
    elif args.command == "export":
        export_case(args.case_id)
    elif args.command == "verify":
        result = verify_export(args.export_path)
        print(json.dumps(result, indent=2))
    else:
        parser.print_help()
