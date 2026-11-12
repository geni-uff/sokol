"""SOKOL API — shared dependencies and database session."""
from __future__ import annotations

import os
import re
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase


class Base(DeclarativeBase):
    pass


def normalize_database_url(url: str) -> str:
    """Fixa o driver psycopg2 (o único na imagem).

    SQLAlchemy 2.1 mudou o padrão de `postgresql://` para psycopg v3;
    sem driver explícito a API cai em `No module named 'psycopg'`.
    """
    return re.sub(r"^postgres(?:ql)?(?:\+psycopg)?://", "postgresql+psycopg2://", url)


@lru_cache
def get_engine():
    url = os.getenv("DATABASE_URL", "postgresql://sokol:change_me@localhost:5433/sokol")
    return create_engine(normalize_database_url(url), pool_pre_ping=True)


@lru_cache
def get_session_factory():
    return sessionmaker(bind=get_engine())
