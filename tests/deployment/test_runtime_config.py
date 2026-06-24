import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from backend.config import Settings
from backend.runtime.readiness import build_readiness_report
from backend.utils.sqlite import configure_sqlite_engine


def _write_release_record(runtime_root: Path, release_id: str) -> None:
    records_root = runtime_root / "releases"
    records_root.mkdir(parents=True, exist_ok=True)
    (records_root / f"{release_id}.json").write_text(
        json.dumps({"release_id": release_id, "git_sha": "test-sha"}),
        encoding="utf-8",
    )


def _make_static_release(
    runtime_root: Path,
    release_id: str,
    *,
    games: tuple[str, ...] = ("qf", "mm", "ir", "tl"),
    link_current: bool = True,
) -> Path:
    release_root = runtime_root / "static" / "releases" / release_id
    for game in games:
        game_root = release_root / game
        game_root.mkdir(parents=True, exist_ok=True)
        (game_root / "index.html").write_text(f"<html>{game}</html>", encoding="utf-8")

    _write_release_record(runtime_root, release_id)

    if link_current:
        current_root = runtime_root / "static" / "current"
        if current_root.exists() or current_root.is_symlink():
            current_root.unlink()
        current_root.symlink_to(release_root, target_is_directory=True)

    return release_root


@pytest.mark.asyncio
async def test_readiness_report_passes_for_complete_runtime(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(runtime_root, "release-123")

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
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert report.ready
    assert report.release_id == "release-123"
    assert report.expected_revision == "revision-123"
    assert all(check.ok for check in report.checks)

    await engine.dispose()


@pytest.mark.asyncio
async def test_readiness_report_rejects_stale_static_release_pointer(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()

    _make_static_release(runtime_root, "release-old")
    _write_release_record(runtime_root, "release-123")
    if static_root.exists() or static_root.is_symlink():
        static_root.unlink()
    static_root.symlink_to(runtime_root / "static" / "releases" / "release-old", target_is_directory=True)

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
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert not report.ready
    static_check = next(check for check in report.checks if check.name == "static_assets")
    assert not static_check.ok
    assert "does not match expected" in static_check.detail

    await engine.dispose()


def test_production_runtime_validation_rejects_worker_count(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(runtime_root, "release-123")

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


def test_production_runtime_validation_rejects_localhost_frontend_url(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(runtime_root, "release-123")

    with pytest.raises(ValueError, match="QF_FRONTEND_URL must not point at localhost"):
        Settings(
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
            qf_frontend_url="https://localhost",
        )


@pytest.mark.asyncio
async def test_readiness_report_flags_missing_static_bundle(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(runtime_root, "release-123", games=("qf",))

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
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert not report.ready
    static_check = next(check for check in report.checks if check.name == "static_assets")
    assert not static_check.ok
    assert "missing built SPAs" in static_check.detail

    await engine.dispose()


@pytest.mark.asyncio
async def test_readiness_report_rejects_multiple_alembic_versions(tmp_path):
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    db_path = tmp_path / "crowdcraft.sqlite3"
    log_dir.mkdir()
    _make_static_release(runtime_root, "release-123")

    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    configure_sqlite_engine(engine.sync_engine)
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('revision-123')"))
        await conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('revision-456')"))

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
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
        use_phrase_validator_api=False,
    )

    report = await build_readiness_report(engine=engine, settings=settings)

    assert not report.ready
    revision_check = next(check for check in report.checks if check.name == "alembic_revision")
    assert not revision_check.ok
    assert "revision-456" in revision_check.detail

    await engine.dispose()
