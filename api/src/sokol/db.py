"""SOKOL API — shared dependencies and database session."""
from __future__ import annotations

import os
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    url = os.getenv("DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol")
    return create_engine(url, pool_pre_ping=True)


@lru_cache
def get_session_factory():
    return sessionmaker(bind=get_engine())
