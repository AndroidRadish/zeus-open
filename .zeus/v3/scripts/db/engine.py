"""
Async database engine and session factory for ZeusOpen v3.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


def make_async_engine(database_url: str | None = None):
    """Create an async SQLAlchemy engine.

    Supports:
      - sqlite+aiosqlite:///path/to/db.sqlite
      - postgresql+asyncpg://user:pass@host/dbname
    """
    if database_url is None:
        database_url = "sqlite+aiosqlite:///./zeus_open_v3.sqlite"
    kwargs: dict[str, Any] = {"echo": False, "future": True}
    if database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"timeout": 30.0, "check_same_thread": False}

    engine = create_async_engine(database_url, **kwargs)

    # Enable WAL mode for SQLite to reduce lock contention
    if database_url.startswith("sqlite"):

        @event.listens_for(engine.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

    return engine


def get_async_session(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
