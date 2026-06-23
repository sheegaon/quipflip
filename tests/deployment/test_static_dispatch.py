from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, WebSocket
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from backend.middleware.host_scope import HostScopeMiddleware


def _make_static_release(static_root: Path) -> None:
    game_root = static_root / "qf"
    assets_root = game_root / "assets"
    assets_root.mkdir(parents=True, exist_ok=True)
    (game_root / "index.html").write_text("<html><body>qf index</body></html>", encoding="utf-8")
    (assets_root / "app.js").write_text("console.log('asset');", encoding="utf-8")


def _make_settings(tmp_path: Path) -> SimpleNamespace:
    runtime_root = tmp_path / "Crowdcraft"
    static_root = runtime_root / "static" / "current"
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    _make_static_release(static_root)

    return SimpleNamespace(
        environment="production",
        secret_key="a-very-secret-value",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'crowdcraft.sqlite3'}",
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
    )


def _build_app(settings: SimpleNamespace) -> FastAPI:
    app = FastAPI()
    app.add_middleware(HostScopeMiddleware, settings=settings)

    @app.get("/mm/ping")
    async def mm_ping() -> dict[str, bool]:
        return {"ok": True}

    @app.websocket("/qf/ws")
    async def qf_ws(websocket: WebSocket) -> None:
        await websocket.accept()
        await websocket.send_text("ok")
        await websocket.close()

    return app


@pytest.mark.asyncio
async def test_static_dispatch_serves_index_for_deep_links(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://quipflip.crowdcraftlabs.com") as client:
        response = await client.get("/dashboard", headers={"accept": "text/html"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "qf index" in response.text
    assert response.headers["cache-control"] == "no-cache, max-age=0, must-revalidate"


@pytest.mark.asyncio
async def test_static_dispatch_serves_assets_with_long_cache_headers(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://quipflip.crowdcraftlabs.com") as client:
        response = await client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.text.strip() == "console.log('asset');"
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_static_dispatch_rejects_foreign_game_prefixes(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://quipflip.crowdcraftlabs.com") as client:
        response = await client.get("/mm/ping")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_static_dispatch_rejects_unknown_hosts(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://unknown.example.com") as client:
        response = await client.get("/dashboard")

    assert response.status_code == 404


def test_static_dispatch_rejects_foreign_game_websockets(tmp_path):
    settings = _make_settings(tmp_path)
    app = _build_app(settings)

    with TestClient(app, base_url="http://quipflip.crowdcraftlabs.com") as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/mm/ws"):
                pass
