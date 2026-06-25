"""
backend/database/engine.py — SQLAlchemy engine and session factory.

Reads DATABASE_URL from settings. Defaults to SQLite for zero-config local dev.
Switch to PostgreSQL by setting DATABASE_URL env var.

Usage:
    from database.engine import get_db
    # Use as FastAPI dependency: db: Session = Depends(get_db)
"""
from __future__ import annotations

import os, sys
_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase, Session
from typing import Generator

from core.config import settings

# ── Engine ────────────────────────────────────────────────────────────────────

_connect_args = {}
if settings.DATABASE_URL.startswith("sqlite"):
    _connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.DATABASE_URL,
    connect_args=_connect_args,
    echo=settings.DEBUG,
)

# Enable WAL mode for SQLite — better concurrency
if settings.DATABASE_URL.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


# ── Session Factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ── Base ──────────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ── FastAPI Dependency ────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    Yield a database session per request and ensure it is closed afterwards.
    Use as: db: Session = Depends(get_db)
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
