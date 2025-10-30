"""Tests for guest account creation and upgrade functionality."""
import pytest
from fastapi import status
from httpx import AsyncClient, ASGITransport
from backend.models.player import Player


class TestGuestAccountCreation:
    """Test guest account creation flow."""

    async def test_create_guest_account(self, test_app):
        """Test creating a guest account."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/player/guest")

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            # Check response structure
            assert "access_token" in data
            assert "refresh_token" in data
            assert "player_id" in data
            assert "username" in data
            assert "balance" in data
            assert "email" in data
            assert "password" in data
            assert "message" in data

            # Check guest email format
            assert data["email"].startswith("guest")
            assert data["email"].endswith("@quipflip.xyz")

            # Check password
            assert data["password"] == "QuipGuest"

            # Check balance is starting balance (5000f default)
            assert data["balance"] == 5000

    async def test_guest_account_is_marked_as_guest(self, test_app, db_session):
        """Test that guest accounts have is_guest=True."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response = await client.post("/player/guest")
            assert response.status_code == status.HTTP_201_CREATED

            data = response.json()
            player_id = data["player_id"]

            # Fetch player from database
            from uuid import UUID
            from sqlalchemy import select
            result = await db_session.execute(
                select(Player).where(Player.player_id == UUID(player_id))
            )
            player = result.scalar_one()

            assert player.is_guest is True

    async def test_multiple_guest_accounts_have_unique_emails(self, test_app):
        """Test that multiple guest accounts get unique emails."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            response1 = await client.post("/player/guest")
            response2 = await client.post("/player/guest")

            assert response1.status_code == status.HTTP_201_CREATED
            assert response2.status_code == status.HTTP_201_CREATED

            email1 = response1.json()["email"]
            email2 = response2.json()["email"]

            assert email1 != email2

    async def test_guest_can_login_with_generated_credentials(self, test_app):
        """Test that guest can login with auto-generated credentials."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED

            guest_data = create_response.json()
            email = guest_data["email"]
            password = guest_data["password"]

            # Try to login
            login_response = await client.post(
                "/auth/login",
                json={"email": email, "password": password}
            )

            assert login_response.status_code == status.HTTP_200_OK
            login_data = login_response.json()
            assert "access_token" in login_data


class TestGuestAccountUpgrade:
    """Test guest account upgrade flow."""

    async def test_upgrade_guest_account(self, test_app):
        """Test upgrading a guest account to a full account."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()

            # Upgrade guest
            upgrade_response = await client.post(
                "/player/upgrade",
                json={
                    "email": "upgraded@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            assert upgrade_response.status_code == status.HTTP_200_OK
            upgrade_data = upgrade_response.json()

            assert "access_token" in upgrade_data
            assert "message" in upgrade_data
            assert upgrade_data["player_id"] == guest_data["player_id"]

    async def test_upgraded_account_is_not_guest(self, test_app, db_session):
        """Test that upgraded accounts have is_guest=False."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            guest_data = create_response.json()

            # Upgrade guest
            await client.post(
                "/player/upgrade",
                json={
                    "email": "upgraded@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            # Fetch player from database
            from uuid import UUID
            from sqlalchemy import select
            result = await db_session.execute(
                select(Player).where(Player.player_id == UUID(guest_data["player_id"]))
            )
            player = result.scalar_one()

            assert player.is_guest is False
            assert player.email == "upgraded@example.com"

    async def test_upgrade_with_duplicate_email_fails(self, test_app):
        """Test that upgrading with an already-used email fails."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create regular account
            await client.post(
                "/player",
                json={
                    "email": "existing@example.com",
                    "password": "Password123"
                }
            )

            # Create guest
            create_response = await client.post("/player/guest")
            guest_data = create_response.json()

            # Try to upgrade with existing email
            upgrade_response = await client.post(
                "/player/upgrade",
                json={
                    "email": "existing@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            assert upgrade_response.status_code == status.HTTP_409_CONFLICT
            assert upgrade_response.json()["detail"] == "email_taken"

    async def test_upgrade_non_guest_account_fails(self, test_app):
        """Test that upgrading a non-guest account fails."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create regular account
            create_response = await client.post(
                "/player",
                json={
                    "email": "regular@example.com",
                    "password": "Password123"
                }
            )
            regular_data = create_response.json()

            # Try to upgrade
            upgrade_response = await client.post(
                "/player/upgrade",
                json={
                    "email": "newemail@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {regular_data['access_token']}"}
            )

            assert upgrade_response.status_code == status.HTTP_400_BAD_REQUEST
            assert upgrade_response.json()["detail"] == "not_a_guest"

    async def test_upgraded_account_can_login_with_new_credentials(self, test_app):
        """Test that upgraded account can login with new credentials."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            guest_data = create_response.json()

            # Upgrade guest
            new_email = "upgraded@example.com"
            new_password = "SecurePass123"
            await client.post(
                "/player/upgrade",
                json={"email": new_email, "password": new_password},
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            # Try to login with new credentials
            login_response = await client.post(
                "/auth/login",
                json={"email": new_email, "password": new_password}
            )

            assert login_response.status_code == status.HTTP_200_OK
            assert login_response.json()["player_id"] == guest_data["player_id"]
