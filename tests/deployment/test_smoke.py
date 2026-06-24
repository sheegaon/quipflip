from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException

from backend.middleware.host_scope import HostScopeMiddleware
from scripts.ops.smoke import run_smoke


pytestmark = pytest.mark.smoke


def _write_static_release(static_root: Path, release_id: str, titles: dict[str, str]) -> None:
    release_root = static_root / "releases" / release_id
    for game, title in titles.items():
        game_root = release_root / game
        game_root.mkdir(parents=True, exist_ok=True)
        (game_root / "index.html").write_text(f"<html><head><title>{title}</title></head></html>", encoding="utf-8")

    current_pointer = static_root / "current"
    if current_pointer.exists() or current_pointer.is_symlink():
        current_pointer.unlink()
    current_pointer.symlink_to(release_root, target_is_directory=True)


def _make_settings(tmp_path: Path, *, titles: dict[str, str] | None = None) -> SimpleNamespace:
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static"
    titles = titles or {
        "qf": "Quipflip - Can you flip their quip?",
        "mm": "MemeMint - Mint the meme. Bank the laughs.",
        "ir": "Initial Reaction - Give every set of letters a story",
        "tl": "ThinkLink - Great minds think alike",
    }
    _write_static_release(static_root, "release-123", titles)

    return SimpleNamespace(
        environment="production",
        secret_key="a-very-secret-value",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'crowdcraft.sqlite3'}",
        crowdcraft_runtime_root=str(runtime_root),
        crowdcraft_static_root=str(static_root / "current"),
        crowdcraft_log_dir=str(tmp_path / "logs"),
        crowdcraft_release_id="release-123",
        crowdcraft_expected_revision="revision-123",
        crowdcraft_workers=1,
        crowdcraft_trust_proxy=True,
        qf_frontend_url="https://quipflip.crowdcraftlabs.com",
        mm_frontend_url="https://mememint.crowdcraftlabs.com",
        ir_frontend_url="https://initialreaction.crowdcraftlabs.com",
        tl_frontend_url="https://thinklink.crowdcraftlabs.com",
    )


def _build_app(settings: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.add_middleware(HostScopeMiddleware, settings=settings)

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/qf/health")
    async def qf_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/mm/health")
    async def mm_health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ir/leaderboard/creators")
    async def ir_creators() -> dict[str, str]:
        raise HTTPException(status_code=401, detail="auth_required")

    @app.get("/tl/game/prompts/preview")
    async def tl_preview() -> dict[str, str]:
        return {"prompt_text": "Preview"}

    return app


@pytest.mark.asyncio
async def test_smoke_runner_passes_for_host_matrix(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    report = await run_smoke(base_url="http://testserver", settings=settings, app=app)

    assert report["ok"] is True
    assert len(report["cases"]) == 4
    assert any(result["path"] == "/livez" for result in report["results"])
    assert any(result["path"] == "/" and "Quipflip" in result["title"] for result in report["results"])


@pytest.mark.asyncio
async def test_smoke_runner_flags_title_mismatch(tmp_path):
    settings = _make_settings(
        tmp_path,
        titles={
            "qf": "Wrong title",
            "mm": "MemeMint - Mint the meme. Bank the laughs.",
            "ir": "Initial Reaction - Give every set of letters a story",
            "tl": "ThinkLink - Great minds think alike",
        },
    )
    app = _build_app(settings)

    with pytest.raises(RuntimeError, match="title"):
        await run_smoke(base_url="http://testserver", settings=settings, app=app)
