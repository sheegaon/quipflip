"""SQLite engine helpers and connection pragmas."""
from __future__ import annotations

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import make_url


def is_sqlite_url(database_url: str) -> bool:
    """Return True when the URL targets SQLite."""
    try:
        return make_url(database_url).drivername.startswith("sqlite")
    except Exception:
        return False


def configure_sqlite_engine(engine: Engine) -> Engine:
    """Install production SQLite pragmas on an engine when applicable."""
    try:
        url = make_url(str(engine.url))
    except Exception:
        return engine

    if not url.drivername.startswith("sqlite"):
        return engine

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:  # pragma: no cover - low-level hook
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=FULL")
            if url.database and url.database != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL")
        finally:
            cursor.close()

    return engine
