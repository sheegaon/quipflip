"""Shared SQLite connection policy and operational helpers."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine


SQLITE_BUSY_TIMEOUT_MS = 5_000
_policy_installed = False


def _is_sqlite_connection(dbapi_connection: Any) -> bool:
    return "sqlite" in type(dbapi_connection).__module__.lower()


def _apply_required_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
    if not _is_sqlite_connection(dbapi_connection):
        return

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute(f"PRAGMA busy_timeout={SQLITE_BUSY_TIMEOUT_MS}")
    finally:
        cursor.close()


def install_sqlite_connection_policy() -> None:
    """Install process-wide safety pragmas for every SQLAlchemy SQLite engine."""
    global _policy_installed
    if _policy_installed:
        return
    event.listen(Engine, "connect", _apply_required_pragmas)
    _policy_installed = True


def configure_production_sqlite(engine: Engine | AsyncEngine) -> None:
    """Apply production durability pragmas to an existing SQLite engine."""
    sync_engine = engine.sync_engine if isinstance(engine, AsyncEngine) else engine

    def apply_production_pragmas(dbapi_connection: Any, _connection_record: Any) -> None:
        if not _is_sqlite_connection(dbapi_connection):
            return
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=FULL")
        finally:
            cursor.close()

    event.listen(sync_engine, "connect", apply_production_pragmas)


def backup_sqlite_database(source: Path, destination: Path) -> None:
    """Create a consistent SQLite backup and verify the restored file."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as source_connection:
        with sqlite3.connect(destination) as destination_connection:
            source_connection.backup(destination_connection)

    with sqlite3.connect(destination) as restored:
        result = restored.execute("PRAGMA integrity_check").fetchone()
    if result != ("ok",):
        raise RuntimeError(f"SQLite backup integrity check failed: {result!r}")
