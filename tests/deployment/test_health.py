import pytest
from httpx import ASGITransport, AsyncClient

import backend.routers.health as health_module
from backend.runtime.readiness import ReadinessCheck, ReadinessReport


API_BASE_URL = "http://test/qf"


@pytest.mark.asyncio
async def test_livez_returns_ok(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.get("/livez")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readyz_returns_503_when_readiness_fails(test_app, monkeypatch):
    async def fake_report():
        return ReadinessReport(
            version="test-version",
            environment="production",
            release_id="release-123",
            expected_revision="revision-123",
            checks=(
                ReadinessCheck(name="runtime_config", ok=False, detail="missing release id"),
            ),
        )

    monkeypatch.setattr(health_module, "build_readiness_report", fake_report)

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.get("/readyz")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["checks"][0]["name"] == "runtime_config"
    assert payload["checks"][0]["ok"] is False


@pytest.mark.asyncio
async def test_health_returns_503_on_database_failure(test_app, monkeypatch):
    class BrokenConnection:
        async def __aenter__(self):
            raise RuntimeError("database unavailable")

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class BrokenEngine:
        def begin(self):
            return BrokenConnection()

    monkeypatch.setattr(health_module, "engine", BrokenEngine())

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url=API_BASE_URL) as client:
        response = await client.get("/health")

    assert response.status_code == 503
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["database"] == "disconnected"
