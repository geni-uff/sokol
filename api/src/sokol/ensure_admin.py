"""Ensure the bootstrap admin user exists (and optionally reset its password).

Author: Matheus C. Pestana
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from uuid import uuid4

from argon2 import PasswordHasher
from sqlalchemy import create_engine, text

# Match docs / E2E / INSTRUCOES when creating or resetting.
DEFAULT_PASSWORD = "admin123"


def main() -> int:
    url = os.getenv("DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol")
    password = os.getenv("SOKOL_BOOTSTRAP_ADMIN_PASSWORD", "").strip() or DEFAULT_PASSWORD
    reset = os.getenv("SOKOL_BOOTSTRAP_ADMIN_RESET", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )

    engine = create_engine(url)
    ph = PasswordHasher()
    now = datetime.now(timezone.utc)

    with engine.begin() as db:
        row = db.execute(
            text("SELECT id FROM users WHERE username = 'admin'")
        ).fetchone()
        if row is None:
            pw_hash = ph.hash(password)
            db.execute(
                text(
                    """
                    INSERT INTO users (
                        id, username, password_hash, display_name,
                        created_at, is_platform_admin
                    )
                    VALUES (
                        :id, 'admin', :pw, 'Administrator', :now, true
                    )
                    """
                ),
                {"id": uuid4(), "pw": pw_hash, "now": now},
            )
            print(f"SOKOL: created admin user (password from bootstrap).")
            return 0

        if reset:
            pw_hash = ph.hash(password)
            db.execute(
                text(
                    """
                    UPDATE users
                    SET password_hash = :pw, is_platform_admin = true
                    WHERE username = 'admin'
                    """
                ),
                {"pw": pw_hash},
            )
            print("SOKOL: reset admin password (SOKOL_BOOTSTRAP_ADMIN_RESET).")
        else:
            db.execute(
                text(
                    "UPDATE users SET is_platform_admin = true WHERE username = 'admin'"
                )
            )
            print("SOKOL: admin user already present.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"SOKOL: ensure_admin failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
