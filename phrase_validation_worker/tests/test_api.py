"""Integration tests for the phrase validation worker FastAPI application."""

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sklearn")
pytest.importorskip("pydantic")
pytest.importorskip("sentence_transformers")

from fastapi.testclient import TestClient
from phrase_validation_worker.main import app  # noqa: E402  (import after optional skip)


@pytest.fixture(scope="module")
def client() -> TestClient:
    """Yield a test client backed by the FastAPI app."""
    with TestClient(app) as test_client:
        yield test_client


def test_health_check(client: TestClient) -> None:
    """Health endpoint returns a simple ok payload."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validate_accepts_valid_phrase(client: TestClient) -> None:
    """Valid dictionary phrases are accepted."""
    response = client.post("/validate", json={"phrase": "FREEDOM"})
    assert response.status_code == 200
    assert response.json() == {"is_valid": True, "error": ""}


def test_validate_rejects_invalid_phrase(client: TestClient) -> None:
    """Invalid phrases return an explanatory error message."""
    response = client.post("/validate", json={"phrase": "hello123"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_valid"] is False
    assert "letters" in payload["error"].lower()


def test_copy_endpoint_rejects_duplicate(client: TestClient) -> None:
    """Copy validation rejects submissions that exactly match the original."""
    response = client.post(
        "/validate/copy",
        json={
            "phrase": "MORNING SUNRISE",
            "original_phrase": "MORNING SUNRISE",
            "other_copy_phrase": None,
            "prompt_text": "A calming daily ritual",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["is_valid"] is False
    assert "same phrase as original" in payload["error"].lower()
