"""Thin Redis cache wrapper with silent degradation on connection failure."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

import redis

_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
logger = logging.getLogger(__name__)


def _client() -> redis.Redis:
    return redis.from_url(_REDIS_URL, decode_responses=True)


def cache_get(key: str) -> Any | None:
    """Return cached value or None on miss / Redis unavailable."""
    try:
        raw = _client().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception as exc:
        logger.warning("cache_get failed (key=%s): %s", key, exc)
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Store value as JSON with TTL. Silently skips on Redis failure."""
    try:
        _client().setex(key, ttl_seconds, json.dumps(value, default=str))
    except Exception as exc:
        logger.warning("cache_set failed (key=%s): %s", key, exc)


def cache_invalidate(prefix: str) -> None:
    """Delete all keys matching prefix:* via SCAN. Silently skips on failure."""
    try:
        client = _client()
        cursor = 0
        while True:
            cursor, keys = client.scan(cursor, match=f"{prefix}:*", count=100)
            if keys:
                client.delete(*keys)
            if cursor == 0:
                break
    except Exception as exc:
        logger.warning("cache_invalidate failed (prefix=%s): %s", prefix, exc)
