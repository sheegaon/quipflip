"""Unit tests for beta survey functionality.

NOTE: These are basic smoke tests for the survey endpoints. The fixtures
that create players with rounds have database session issues (fixtures use
db_session while test_app uses its own database override). More comprehensive
tests should create players via the API endpoint like test_api_player.py does.

The survey feature is also tested via integration tests when players submit
surveys through the actual API endpoints.
"""
from __future__ import annotations

import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport


@pytest.mark.asyncio
async def test_status_requires_authentication(test_app):
    """Status endpoint should require authentication."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/feedback/beta-survey/status")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_submission_requires_authentication(test_app):
    """Survey submission should require authentication."""
    payload = {
        "survey_id": "beta_oct_2025",
        "answers": [{"question_id": "q1", "value": 5}],
    }

    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.post("/feedback/beta-survey", json=payload)
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.asyncio
async def test_list_requires_authentication(test_app):
    """List endpoint should require authentication."""
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
        response = await client.get("/feedback/beta-survey")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


# TODO: Add more comprehensive tests that:
# - Create players via the API (not fixtures) to avoid db session issues
# - Test eligibility based on round count
# - Test survey submission and duplicate prevention
# - Test admin list functionality
# - Test data model constraints
# See test_api_player.py for the correct pattern
