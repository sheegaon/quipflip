"""Production-shaped SQLite verification.

These tests deliberately use file-backed databases and real independent
connections. They are excluded from the deterministic default gate.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from backend.sqlite import (
    SQLITE_BUSY_TIMEOUT_MS,
    backup_sqlite_database,
    configure_production_sqlite,
)


ROOT = Path(__file__).resolve().parents[2]


def _migrate(path: Path) -> None:
    config = AlembicConfig(str(ROOT / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{path}")
    command.upgrade(config, "head")


@pytest.mark.asyncio
async def test_async_production_engine_enables_required_pragmas(tmp_path: Path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'pragmas.db'}")
    configure_production_sqlite(engine)

    async with engine.connect() as connection:
        foreign_keys = await connection.scalar(text("PRAGMA foreign_keys"))
        busy_timeout = await connection.scalar(text("PRAGMA busy_timeout"))
        journal_mode = await connection.scalar(text("PRAGMA journal_mode"))
        synchronous = await connection.scalar(text("PRAGMA synchronous"))
        await connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        await connection.execute(
            text(
                "CREATE TABLE child ("
                "id INTEGER PRIMARY KEY, "
                "parent_id INTEGER NOT NULL REFERENCES parent(id)"
                ")"
            )
        )
        await connection.commit()
        with pytest.raises(IntegrityError):
            await connection.execute(
                text("INSERT INTO child (id, parent_id) VALUES (1, 999)")
            )
        await connection.rollback()

    await engine.dispose()
    assert foreign_keys == 1
    assert busy_timeout == SQLITE_BUSY_TIMEOUT_MS
    assert journal_mode == "wal"
    assert synchronous == 2  # FULL


def test_sync_operational_connection_rejects_invalid_foreign_key(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'operational.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE parent (id INTEGER PRIMARY KEY)"))
        connection.execute(
            text(
                "CREATE TABLE child ("
                "id INTEGER PRIMARY KEY, "
                "parent_id INTEGER NOT NULL REFERENCES parent(id)"
                ")"
            )
        )

    with pytest.raises(IntegrityError):
        with engine.begin() as connection:
            connection.execute(text("INSERT INTO child (id, parent_id) VALUES (1, 999)"))
    engine.dispose()


def test_complete_migration_chain_enforces_foreign_keys(tmp_path: Path) -> None:
    database = tmp_path / "migrated.db"
    _migrate(database)

    with sqlite3.connect(database) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "INSERT INTO refresh_tokens "
                "(token_id, player_id, token_hash, expires_at, created_at) "
                "VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
                (
                    "00000000-0000-0000-0000-000000000001",
                    "missing-player",
                    "missing-player-token",
                ),
            )


def test_compare_and_swap_has_one_winner(tmp_path: Path) -> None:
    database = tmp_path / "cas.db"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE assignment (id INTEGER PRIMARY KEY, state TEXT NOT NULL)")
        connection.execute("INSERT INTO assignment VALUES (1, 'open')")

    first = sqlite3.connect(database, isolation_level=None)
    second = sqlite3.connect(database, isolation_level=None)
    try:
        first_result = first.execute(
            "UPDATE assignment SET state='claimed-a' WHERE id=1 AND state='open'"
        )
        second_result = second.execute(
            "UPDATE assignment SET state='claimed-b' WHERE id=1 AND state='open'"
        )
        assert (first_result.rowcount, second_result.rowcount) == (1, 0)
    finally:
        first.close()
        second.close()


def test_busy_wait_is_bounded_and_interrupted_write_rolls_back(tmp_path: Path) -> None:
    database = tmp_path / "busy.db"
    owner = sqlite3.connect(database, isolation_level=None)
    contender = sqlite3.connect(database, isolation_level=None)
    try:
        owner.execute("CREATE TABLE item (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        owner.execute("INSERT INTO item VALUES (1, 'original')")
        owner.execute("BEGIN IMMEDIATE")
        owner.execute("UPDATE item SET value='uncommitted' WHERE id=1")

        contender.execute("PRAGMA busy_timeout=100")
        started = time.monotonic()
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            contender.execute("UPDATE item SET value='contender' WHERE id=1")
        elapsed = time.monotonic() - started
        assert 0.05 <= elapsed < 1.0

        owner.rollback()
        assert contender.execute("SELECT value FROM item WHERE id=1").fetchone() == ("original",)
    finally:
        owner.close()
        contender.close()


def test_restart_rebuilds_queue_projection_from_durable_rows(tmp_path: Path) -> None:
    database = tmp_path / "restart.db"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE durable_queue "
            "(id INTEGER PRIMARY KEY, status TEXT NOT NULL, created_order INTEGER NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO durable_queue VALUES (?, ?, ?)",
            [(1, "claimable", 2), (2, "claimed", 1), (3, "claimable", 3)],
        )

    in_memory_queue: list[int] = []
    with sqlite3.connect(database) as restarted:
        in_memory_queue.extend(
            row[0]
            for row in restarted.execute(
                "SELECT id FROM durable_queue WHERE status='claimable' ORDER BY created_order"
            )
        )
    assert in_memory_queue == [1, 3]


def test_backup_integrity_restore_and_query(tmp_path: Path) -> None:
    source = tmp_path / "source.db"
    restored = tmp_path / "restored.db"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE evidence (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
        connection.executemany(
            "INSERT INTO evidence (value) VALUES (?)",
            [("alpha",), ("beta",)],
        )

    backup_sqlite_database(source, restored)

    with sqlite3.connect(restored) as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT value FROM evidence ORDER BY id").fetchall() == [
            ("alpha",),
            ("beta",),
        ]


def test_backup_rejects_missing_source_file(tmp_path: Path) -> None:
    source = tmp_path / "missing.db"
    restored = tmp_path / "restored.db"

    with pytest.raises(FileNotFoundError):
        backup_sqlite_database(source, restored)
