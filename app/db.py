"""SQLAlchemy engine, session factory and schema bootstrap."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import BASE_DIR, settings


class Base(DeclarativeBase):
    pass


def _engine_kwargs() -> dict:
    if not settings.is_sqlite:
        return {"pool_pre_ping": True}
    # Requests are served from a thread pool, so the connection must be
    # usable outside the thread that created it.
    return {"connect_args": {"check_same_thread": False}}


def _ensure_sqlite_directory(url: str) -> None:
    """Create the folder holding a relative SQLite file (sqlite won't)."""
    if not url.startswith("sqlite:///") or url.startswith("sqlite:////"):
        return
    raw_path = url[len("sqlite:///") :]
    if raw_path in ("", ":memory:") or raw_path.startswith("file:"):
        return
    path = Path(raw_path)
    if not path.is_absolute():
        path = BASE_DIR / path
    path.parent.mkdir(parents=True, exist_ok=True)


_ensure_sqlite_directory(settings.database_url)

engine = create_engine(settings.database_url, future=True, **_engine_kwargs())
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


if settings.is_sqlite:

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create any missing tables. Safe to call on every boot."""
    from app import models  # noqa: F401  (registers mappers)

    Base.metadata.create_all(bind=engine)
