import sqlite3

from backend.database import configure_sqlite_connection


def test_configure_sqlite_connection_enables_production_pragmas(tmp_path):
    db_path = tmp_path / "crowdcraft.sqlite3"
    connection = sqlite3.connect(db_path)
    try:
        configure_sqlite_connection(connection)

        cursor = connection.cursor()
        try:
            foreign_keys = cursor.execute("PRAGMA foreign_keys").fetchone()[0]
            journal_mode = cursor.execute("PRAGMA journal_mode").fetchone()[0]
            busy_timeout = cursor.execute("PRAGMA busy_timeout").fetchone()[0]
            synchronous = cursor.execute("PRAGMA synchronous").fetchone()[0]
        finally:
            cursor.close()
    finally:
        connection.close()

    assert foreign_keys == 1
    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5000
    assert synchronous == 2
