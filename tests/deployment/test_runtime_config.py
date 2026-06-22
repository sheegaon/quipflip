from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import Settings
from backend.runtime.readiness import build_readiness_report
from backend.utils.sqlite import configure_sqlite_engine


def _make_static_release(static_root: Path) -> None:
    for game in ("qf", "mm", "ir", "tl"):
        game_root = static_root / game
        game_root.mkdir(parents=True, exist_ok=True)
        (game_root / "index.html").write_text(f"<html>{game}</html>", encoding="utf-8")


@pytest.mark.asyncio
async def test_readiness_report_passes_for_complete_runtime(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(static_root)

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    configure_sqlite_engine(engine.sync_engine)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('revision-123')"))

    settings = SimpleNamespace(
        environment="production",
        secret_key="a-very-secret-value",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        crowdcraft_runtime_root=str(runtime_root),
        crowdcraft_static_root=str(static_root),
        crowdcraft_log_dir=str(log_dir),
        crowdcraft_release_id="release-123",
        crowdcraft_expected_revision="revision-123",
        crowdcraft_workers=1,
        crowdcraft_trust_proxy=True,
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert report.ready
    assert report.release_id == "release-123"
    assert report.expected_revision == "revision-123"
    assert all(check.ok for check in report.checks)

    await engine.dispose()


def test_production_runtime_validation_rejects_worker_count(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(static_root)

    with pytest.raises(ValueError, match="CROWDCRAFT_WORKERS must be exactly 1"):
        Settings(
            environment="production",
            secret_key="a-very-secret-value",
            database_url=f"sqlite+aiosqlite:///{db_path}",
            crowdcraft_runtime_root=str(runtime_root),
            crowdcraft_static_root=str(static_root),
            crowdcraft_log_dir=str(log_dir),
            crowdcraft_release_id="release-123",
            crowdcraft_expected_revision="revision-123",
            crowdcraft_workers=2,
            crowdcraft_trust_proxy=True,
        )


@pytest.mark.asyncio
async def test_readiness_report_flags_missing_static_bundle(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    static_root.mkdir(parents=True)
    (static_root / "qf").mkdir()
    (static_root / "qf" / "index.html").write_text("<html>qf</html>", encoding="utf-8")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    configure_sqlite_engine(engine.sync_engine)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('revision-123')"))

    settings = SimpleNamespace(
        environment="production",
        secret_key="a-very-secret-value",
        database_url=f"sqlite+aiosqlite:///{db_path}",
        crowdcraft_runtime_root=str(runtime_root),
        crowdcraft_static_root=str(static_root),
        crowdcraft_log_dir=str(log_dir),
        crowdcraft_release_id="release-123",
        crowdcraft_expected_revision="revision-123",
        crowdcraft_workers=1,
        crowdcraft_trust_proxy=True,
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert not report.ready
    static_check = next(check for check in report.checks if check.name == "static_assets")
    assert not static_check.ok
    assert "missing built SPAs" in static_check.detail

    await engine.dispose()
