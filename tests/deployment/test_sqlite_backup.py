import sqlite3
from pathlib import Path

from scripts.ops.sqlite_backup import create_backup, restore_backup, verify_backup


def _seed_sqlite_db(path):
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE example (id INTEGER PRIMARY KEY, name TEXT NOT NULL)")
        conn.execute("INSERT INTO example (name) VALUES ('alpha')")
        conn.commit()


def test_sqlite_backup_restore_preserves_existing_destination_by_default(tmp_path):
    source_db = tmp_path / "source.sqlite3"
    backup_dir = tmp_path / "backup"
    destination_db = tmp_path / "destination.sqlite3"

    _seed_sqlite_db(source_db)
    _seed_sqlite_db(destination_db)
    with sqlite3.connect(destination_db) as conn:
        conn.execute("INSERT INTO example (name) VALUES ('beta')")
        conn.commit()

    manifest = create_backup(
        source_db,
        backup_dir,
        release_id="release-123",
        git_sha="git-sha-123",
        source_revision="revision-123",
    )
    verified = verify_backup(backup_dir)
    restored = restore_backup(backup_dir, destination_db)

    assert manifest["backup_id"]
    assert verified["verified_at"]
    assert restored["restored_at"]
    assert "preserved_existing" in restored
    assert destination_db.is_file()
    preserved_path = Path(restored["preserved_existing"])
    assert preserved_path.is_file()

    with sqlite3.connect(destination_db) as conn:
        rows = conn.execute("SELECT name FROM example ORDER BY id").fetchall()

    assert rows == [("alpha",)]
