"""SOKOL auth — Argon2 password hashing and token-based sessions."""
from __future__ import annotations

import hashlib
import os
import secrets
import time
from dataclasses import dataclass
from uuid import UUID, uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import text
from sqlalchemy.orm import Session

from .db import get_session_factory

ph = PasswordHasher()

# In-memory session store (v1). Replace with DB-backed tokens later.
_sessions: dict[str, _SessionData] = {}


@dataclass
class _SessionData:
    user_id: UUID
    created_at: float


@dataclass
class CurrentUser:
    user_id: UUID


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(stored: str, password: str) -> bool:
    try:
        return ph.verify(stored, password)
    except VerifyMismatchError:
        return False


def create_session(user_id: UUID) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = _SessionData(user_id=user_id, created_at=time.time())
    return token


def _resolve_token(request: Request, query_token: str | None = None) -> CurrentUser:
    token = query_token
    if not token:
        auth = request.headers.get("Authorization", "")
        if auth.startswith("Bearer "):
            token = auth[7:]
    if not token:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    data = _sessions.get(token)
    if data is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return CurrentUser(user_id=data.user_id)


def get_current_user(request: Request) -> CurrentUser:
    return _resolve_token(request)


def get_media_user(request: Request, token: str | None = Query(None)) -> CurrentUser:
    """Like get_current_user but also accepts ?token= for <img>/<video> src URLs."""
    return _resolve_token(request, token)


def require_case_member(db: Session, case_id: UUID, user_id: UUID, roles: list[str] | None = None) -> str:
    """Return the user's role in the case, or raise 403."""
    row = db.execute(
        text("SELECT role FROM case_members WHERE case_id = :cid AND user_id = :uid"),
        {"cid": case_id, "uid": user_id},
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=403, detail="Not a member of this case")
    role = row[0]
    if roles and role not in roles:
        raise HTTPException(status_code=403, detail=f"Requires role: {', '.join(roles)}")
    return role


def require_platform_admin(db: Session, user_id: UUID) -> None:
    """Require users.is_platform_admin — not merely admin of one case."""
    row = db.execute(
        text("SELECT is_platform_admin FROM users WHERE id = :uid"),
        {"uid": user_id},
    ).fetchone()
    if row is None or not row[0]:
        raise HTTPException(status_code=403, detail="Platform admin role required")
