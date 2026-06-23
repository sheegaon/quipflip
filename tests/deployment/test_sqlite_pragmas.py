from sqlalchemy import create_engine, text

from backend.utils.sqlite import configure_sqlite_engine


def test_configure_sqlite_engine_enables_pragmas(tmp_path):
    db_path = tmp_path / "crowdcraft.sqlite3"
    engine = create_engine(f"sqlite:///{db_path}")
    configure_sqlite_engine(engine)

    with engine.connect() as conn:
        foreign_keys = conn.execute(text("PRAGMA foreign_keys")).fetchone()[0]
        journal_mode = conn.execute(text("PRAGMA journal_mode")).fetchone()[0]
        busy_timeout = conn.execute(text("PRAGMA busy_timeout")).fetchone()[0]
        synchronous = conn.execute(text("PRAGMA synchronous")).fetchone()[0]

    engine.dispose()

    assert foreign_keys == 1
    assert journal_mode.lower() == "wal"
    assert busy_timeout == 5000
    assert synchronous == 2
