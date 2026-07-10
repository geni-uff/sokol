"""SOKOL audit — hash-chain append-only audit log."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session


def _canonical_json(payload: dict) -> str:
    """Stable JSON serialization: sorted keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_hash(prev_hash: str | None, payload: dict) -> str:
    """hash = sha256(prev_hash || canonical_json(payload))"""
    prev = prev_hash or ""
    canonical = _canonical_json(payload)
    return hashlib.sha256((prev + canonical).encode()).hexdigest()


def append_audit(
    db: Session,
    *,
    case_id: UUID | None,
    actor_user_id: UUID | None,
    action: str,
    payload: dict,
) -> UUID:
    """Append an audit record. Returns the record ID."""
    # Get the last hash for this case (or global if case_id is None)
    if case_id:
        row = db.execute(
            text("SELECT hash FROM audit_log WHERE case_id = :cid ORDER BY created_at DESC LIMIT 1"),
            {"cid": case_id},
        ).fetchone()
    else:
        row = db.execute(
            text("SELECT hash FROM audit_log WHERE case_id IS NULL ORDER BY created_at DESC LIMIT 1")
        ).fetchone()

    prev_hash = row[0] if row else None
    h = compute_hash(prev_hash, payload)
    now = datetime.now(timezone.utc)
    audit_id = uuid4()

    db.execute(
        text("""
            INSERT INTO audit_log (id, case_id, actor_user_id, action, payload, prev_hash, hash, created_at)
            VALUES (:id, :cid, :actor, :action, :payload, :prev, :hash, :now)
        """),
        {
            "id": audit_id,
            "cid": case_id,
            "actor": actor_user_id,
            "action": action,
            "payload": json.dumps(payload, default=str),
            "prev": prev_hash,
            "hash": h,
            "now": now,
        },
    )
    return audit_id


def verify_chain(db: Session, case_id: UUID | None = None) -> list[dict]:
    """Verify the entire audit chain. Returns list of errors (empty = valid)."""
    if case_id:
        rows = db.execute(
            text("""
                SELECT id, prev_hash, hash, payload, action, created_at
                FROM audit_log WHERE case_id = :cid
                ORDER BY created_at ASC
            """),
            {"cid": case_id},
        ).fetchall()
    else:
        rows = db.execute(
            text("""
                SELECT id, prev_hash, hash, payload, action, created_at
                FROM audit_log WHERE case_id IS NULL
                ORDER BY created_at ASC
            """)
        ).fetchall()

    errors: list[dict] = []
    expected_prev: str | None = None

    for row in rows:
        rec_id, prev_hash, current_hash, payload_raw, action, created_at = row
        payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw

        # Check prev_hash linkage
        if prev_hash != expected_prev:
            errors.append({
                "id": str(rec_id),
                "action": action,
                "created_at": str(created_at),
                "error": f"prev_hash mismatch: expected {expected_prev}, got {prev_hash}",
            })

        # Recompute hash
        recomputed = compute_hash(expected_prev, payload)
        if recomputed != current_hash:
            errors.append({
                "id": str(rec_id),
                "action": action,
                "created_at": str(created_at),
                "error": f"hash mismatch: expected {recomputed}, got {current_hash}",
            })

        expected_prev = current_hash

    return errors
