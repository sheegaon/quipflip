from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path
from subprocess import CompletedProcess

import pytest

from backend.config import get_settings
from scripts.ops import release as release_module


pytestmark = pytest.mark.owner_platform


def _seed_sqlite_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)")
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('revision-previous')")
        conn.commit()


def _make_checkout(root: Path) -> None:
    titles = {
        "qf": "Quipflip - Can you flip their quip?",
        "mm": "MemeMint - Mint the meme. Bank the laughs.",
        "ir": "Initial Reaction - Give every set of letters a story",
        "tl": "ThinkLink - Great minds think alike",
    }
    for game, title in titles.items():
        dist_root = root / "frontend" / game / "dist"
        dist_root.mkdir(parents=True, exist_ok=True)
        (dist_root / "index.html").write_text(
            f"<html><head><title>{title}</title></head></html>",
            encoding="utf-8",
        )
        (dist_root / "asset.js").write_text("console.log('asset');", encoding="utf-8")


def _make_runtime_tree(runtime_root: Path, release_id: str) -> Path:
    old_release_root = runtime_root / "static" / "releases" / "old-release"
    for game, title in {
        "qf": "Old Quipflip",
        "mm": "Old MemeMint",
        "ir": "Old Initial Reaction",
        "tl": "Old ThinkLink",
    }.items():
        game_root = old_release_root / game
        game_root.mkdir(parents=True, exist_ok=True)
        (game_root / "index.html").write_text(
            f"<html><head><title>{title}</title></head></html>",
            encoding="utf-8",
        )

    current_pointer = runtime_root / "static" / "current"
    current_pointer.parent.mkdir(parents=True, exist_ok=True)
    if current_pointer.exists() or current_pointer.is_symlink():
        current_pointer.unlink()
    current_pointer.symlink_to(old_release_root, target_is_directory=True)
    return old_release_root


def _configure_production_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    db_path = tmp_path / "crowdcraft.sqlite3"
    _seed_sqlite_db(db_path)
    _make_runtime_tree(runtime_root, "old-release")

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SECRET_KEY", "a-very-secret-value")
    monkeypatch.setenv("DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
    monkeypatch.setenv("CROWDCRAFT_RUNTIME_ROOT", str(runtime_root))
    monkeypatch.setenv("CROWDCRAFT_STATIC_ROOT", str(static_root))
    monkeypatch.setenv("CROWDCRAFT_LOG_DIR", str(log_dir))
    monkeypatch.setenv("CROWDCRAFT_RELEASE_ID", "release-123")
    monkeypatch.setenv("CROWDCRAFT_EXPECTED_REVISION", "revision-123")
    monkeypatch.setenv("CROWDCRAFT_WORKERS", "1")
    monkeypatch.setenv("CROWDCRAFT_TRUST_PROXY", "true")
    monkeypatch.setenv("QF_FRONTEND_URL", "https://quipflip.crowdcraftlabs.com")
    monkeypatch.setenv("MM_FRONTEND_URL", "https://mememint.crowdcraftlabs.com")
    monkeypatch.setenv("IR_FRONTEND_URL", "https://initialreaction.crowdcraftlabs.com")
    monkeypatch.setenv("TL_FRONTEND_URL", "https://thinklink.crowdcraftlabs.com")
    get_settings.cache_clear()
    return db_path


def _prepare_release_module(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    checkout_root = tmp_path / "checkout"
    _make_checkout(checkout_root)
    monkeypatch.setattr(release_module, "ROOT_DIR", checkout_root)
    monkeypatch.setattr(release_module.shutil, "which", lambda _name: "/usr/bin/fake-tool")
    return checkout_root


def test_run_release_publishes_static_and_records_artifacts(tmp_path, monkeypatch):
    db_path = _configure_production_env(monkeypatch, tmp_path)
    checkout_root = _prepare_release_module(monkeypatch, tmp_path)
    commands: list[list[str]] = []

    def fake_run_command(command, **_kwargs):
        commands.append(command)
        if command[:4] == [release_module.sys.executable, "scripts/verify.py", "verify"]:
            return CompletedProcess(command, 0, stdout="verify ok\n", stderr="")
        if command[:2] == ["launchctl", "bootout"]:
            return CompletedProcess(command, 0, stdout="bootout ok\n", stderr="")
        if command[:2] == ["launchctl", "kickstart"]:
            return CompletedProcess(command, 0, stdout="kickstart ok\n", stderr="")
        if command[:3] == [release_module.sys.executable, "-m", "alembic"]:
            return CompletedProcess(command, 0, stdout="alembic ok\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    async def fake_sync_content(*, apply: bool, release_id: str):
        assert apply is True
        return {
            "release_id": release_id,
            "applied": True,
            "source": {"qf_prompts": 0},
            "database": {"players": 0},
        }

    async def fake_wait_for_livez(host_header: str, *, base_url: str = "http://127.0.0.1:8000"):
        return {"ok": True, "path": "/livez", "host": host_header, "base_url": base_url}

    async def fake_wait_for_readyz(host_header: str, *, base_url: str = "http://127.0.0.1:8000"):
        return {"ok": True, "path": "/readyz", "host": host_header, "base_url": base_url}

    monkeypatch.setattr(release_module, "run_command", fake_run_command)
    monkeypatch.setattr(release_module, "sync_content", fake_sync_content)
    monkeypatch.setattr(release_module, "_wait_for_listener_closed", lambda **_kwargs: {"ok": True, "status": "closed"})
    monkeypatch.setattr(release_module, "_wait_for_livez", fake_wait_for_livez)
    monkeypatch.setattr(release_module, "_wait_for_readyz", fake_wait_for_readyz)
    monkeypatch.setattr(
        release_module,
        "run_smoke_sync",
        lambda **_kwargs: {
            "ok": True,
            "base_url": "http://127.0.0.1:8000",
            "cases": [{"host": "quipflip.crowdcraftlabs.com"}],
            "results": [{"path": "/", "title": "Quipflip - Can you flip their quip?"}],
        },
    )

    report = release_module.run_release(revision="revision-123", release_id="release-123", apply=True, run_smoke=True)

    runtime_root = tmp_path / "Crowdcraft"
    release_record_path = runtime_root / "releases" / "release-123.json"
    current_pointer = runtime_root / "static" / "current"
    published_root = runtime_root / "static" / "releases" / "release-123"
    backup_dir = runtime_root / "backups" / "release-123"

    assert report["status"] == "complete"
    assert report["current_state"] == release_module.STATE_COMPLETE
    assert report["previous_static_release_id"] == "old-release"
    assert report["backup"]["manifest"]["backup_id"]
    assert report["static_staging"]["release_id"] == "release-123"
    assert report["state_history"].index(release_module.STATE_VERIFIED) < report["state_history"].index(
        release_module.STATE_STATIC_STAGED
    )
    assert report["state_history"].index(release_module.STATE_STATIC_STAGED) < report["state_history"].index(
        release_module.STATE_SERVICE_QUIESCED
    )
    assert report["service_quiesce"]["returncode"] == 0
    assert report["listener_closed"]["ok"] is True
    assert report["service_restart"]["returncode"] == 0
    assert report["livez"]["ok"] is True
    assert report["readyz"]["ok"] is True
    assert report["state_history"].index(release_module.STATE_STATIC_STAGED) < report["state_history"].index(
        release_module.STATE_STATIC_PUBLISHED
    )
    assert report["state_history"].index(release_module.STATE_STATIC_PUBLISHED) < report["state_history"].index(
        release_module.STATE_SERVICE_READY
    )
    assert release_record_path.is_file()
    assert published_root.is_dir()
    assert current_pointer.resolve(strict=False) == published_root
    assert backup_dir.is_dir()
    assert any(command[:4] == [release_module.sys.executable, "scripts/verify.py", "verify"] for command in commands)
    assert any(command[:3] == [release_module.sys.executable, "-m", "alembic"] for command in commands)
    assert any(command[:3] == ["launchctl", "bootout", f"gui/{os.getuid()}"] for command in commands)
    assert any(command[:4] == ["launchctl", "kickstart", "-k", f"gui/{os.getuid()}"] for command in commands)

    record = sqlite3.connect(db_path)
    try:
        row = record.execute("SELECT version_num FROM alembic_version").fetchone()
    finally:
        record.close()
    assert row == ("revision-previous",)


def test_run_rollback_restores_backup_and_previous_static_release(tmp_path, monkeypatch):
    _configure_production_env(monkeypatch, tmp_path)
    _prepare_release_module(monkeypatch, tmp_path)

    async def fake_sync_content(*, apply: bool, release_id: str):
        return {"release_id": release_id, "applied": apply}

    async def fake_wait_for_livez(host_header: str, *, base_url: str = "http://127.0.0.1:8000"):
        return {"ok": True, "path": "/livez", "host": host_header, "base_url": base_url}

    async def fake_wait_for_readyz(host_header: str, *, base_url: str = "http://127.0.0.1:8000"):
        return {"ok": True, "path": "/readyz", "host": host_header, "base_url": base_url}

    monkeypatch.setattr(release_module, "run_command", lambda command, **_kwargs: CompletedProcess(command, 0, stdout="", stderr=""))
    monkeypatch.setattr(release_module, "sync_content", fake_sync_content)
    monkeypatch.setattr(release_module, "_wait_for_listener_closed", lambda **_kwargs: {"ok": True, "status": "closed"})
    monkeypatch.setattr(release_module, "_wait_for_livez", fake_wait_for_livez)
    monkeypatch.setattr(release_module, "_wait_for_readyz", fake_wait_for_readyz)
    monkeypatch.setattr(
        release_module,
        "run_smoke_sync",
        lambda **_kwargs: {"ok": True, "base_url": "http://127.0.0.1:8000", "cases": [], "results": []},
    )

    release_module.run_release(revision="revision-123", release_id="release-123", apply=True, run_smoke=False)

    runtime_root = tmp_path / "Crowdcraft"
    current_pointer = runtime_root / "static" / "current"
    db_path = tmp_path / "crowdcraft.sqlite3"

    # Corrupt the active database so rollback has something to preserve.
    with sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO alembic_version (version_num) VALUES ('forward-revision')")
        conn.commit()

    rollback_report = release_module.run_rollback(release_id="release-123", apply=True)

    assert rollback_report["apply"] is True
    assert rollback_report["static_restore"]["restored_release_id"] == "old-release"
    assert rollback_report["service_quiesce"]["returncode"] == 0
    assert rollback_report["listener_closed"]["ok"] is True
    assert rollback_report["service_restart"]["returncode"] == 0
    assert rollback_report["livez"]["ok"] is True
    assert rollback_report["readyz"]["ok"] is True
    assert rollback_report["smoke"]["ok"] is True
    assert current_pointer.resolve(strict=False) == runtime_root / "static" / "releases" / "old-release"
    preserved = rollback_report["restore"]["preserved_existing"]
    assert Path(preserved).is_file()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT version_num FROM alembic_version ORDER BY rowid").fetchall()

    assert rows == [("revision-previous",)]


def test_run_release_dry_run_includes_static_staged_state(tmp_path, monkeypatch):
    _configure_production_env(monkeypatch, tmp_path)
    _prepare_release_module(monkeypatch, tmp_path)

    report = release_module.run_release(revision="revision-123", release_id="release-123", apply=False)

    assert report["ok"] is True
    assert report["apply"] is False
    assert release_module.STATE_STATIC_STAGED in report["planned_states"]
    assert report["planned_states"].index(release_module.STATE_VERIFIED) < report["planned_states"].index(
        release_module.STATE_STATIC_STAGED
    )
    assert report["planned_states"].index(release_module.STATE_STATIC_STAGED) < report["planned_states"].index(
        release_module.STATE_SERVICE_QUIESCED
    )
