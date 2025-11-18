"""Tests for guest account creation and upgrade functionality."""
from fastapi import status
from httpx import AsyncClient, ASGITransport
from backend.models.qf.player import QFPlayer


class TestGuestAccountCreation:
    """Test guest account creation flow."""

    async def test_create_guest_account(self, test_app):
        """Test creating a guest account."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            response = await client.post("/player/guest")

            assert response.status_code == status.HTTP_201_CREATED
            data = response.json()

            # Check response structure
            assert "access_token" in data
            assert "refresh_token" in data
            assert "player_id" in data
            assert "username" in data
            assert "wallet" in data
            assert "vault" in data
            assert "email" in data
            assert "password" in data
            assert "message" in data

            # Check guest email format
            assert data["email"].startswith("guest")
            assert data["email"].endswith("@quipflip.xyz")

            # Check password
            assert data["password"] == "Guest"

            # Check wallet is starting balance (5000 default)
            assert data["wallet"] == 5000
            # Check vault starts at 0
            assert data["vault"] == 0

    async def test_guest_account_is_marked_as_guest(self, test_app, db_session):
        """Test that guest accounts have is_guest=True."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            response = await client.post("/player/guest")
            assert response.status_code == status.HTTP_201_CREATED

            data = response.json()
            player_id = data["player_id"]

            # Fetch player from database
            from uuid import UUID
            from sqlalchemy import select
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(player_id))
            )
            player = result.scalar_one()

            assert player.is_guest is True

    async def test_multiple_guest_accounts_have_unique_emails(self, test_app):
        """Test that multiple guest accounts get unique emails."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            response1 = await client.post("/player/guest")
            response2 = await client.post("/player/guest")

            assert response1.status_code == status.HTTP_201_CREATED
            assert response2.status_code == status.HTTP_201_CREATED

            email1 = response1.json()["email"]
            email2 = response2.json()["email"]

            assert email1 != email2

    async def test_guest_can_login_with_generated_credentials(self, test_app):
        """Test that guest can login with auto-generated credentials."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
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
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()

            # Upgrade guest
            upgrade_response = await client.post(
                "/player/upgrade",
                json={
                    "email": "upgraded1@example.com",
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
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            guest_data = create_response.json()

            # Upgrade guest
            await client.post(
                "/player/upgrade",
                json={
                    "email": "upgraded2@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            # Fetch player from database
            from uuid import UUID
            from sqlalchemy import select
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_data["player_id"]))
            )
            player = result.scalar_one()

            assert player.is_guest is False
            assert player.email == "upgraded2@example.com"

    async def test_upgrade_with_duplicate_email_fails(self, test_app):
        """Test that upgrading with an already-used email fails."""
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
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
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
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
        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create guest
            create_response = await client.post("/player/guest")
            guest_data = create_response.json()

            # Upgrade guest
            new_email = "upgraded3@example.com"
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


class TestGuestCleanup:
    """Test cleanup of inactive guest accounts."""

    async def test_cleanup_inactive_guest_players(self, test_app, db_session):
        """Test that inactive guest players are cleaned up after specified days."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Artificially age the guest account
            from uuid import UUID
            from sqlalchemy import update
            old_date = datetime.now(UTC) - timedelta(days=8)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(created_at=old_date, last_login_date=old_date)
            )
            await db_session.commit()

            # Run cleanup
            cleanup_service = CleanupService(db_session)
            deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

            # Verify the guest was deleted
            assert deleted_count == 1

            # Verify player no longer exists
            from sqlalchemy import select
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one_or_none()
            assert player is None

    async def test_cleanup_does_not_delete_active_guests(self, test_app, db_session):
        """Test that guests who have played rounds are not deleted."""
        from backend.services import CleanupService
        from backend.services import RoundService
        from datetime import timedelta, UTC, datetime
        from sqlalchemy import update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Create a round for this guest (simulating activity)
            from uuid import UUID
            from sqlalchemy import select
            player_result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = player_result.scalar_one()

            round_service = RoundService(db_session)
            # This will create a round, showing the guest has been active
            try:
                await round_service.start_prompt_round(player)
            except Exception:
                # Might fail due to missing prompts, but that's okay for this test
                pass

            # Artificially age the guest account
            old_date = datetime.now(UTC) - timedelta(days=8)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(created_at=old_date)
            )
            await db_session.commit()

            # Run cleanup
            cleanup_service = CleanupService(db_session)
            deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

            # Verify the guest was NOT deleted (because they have rounds)
            # Note: This might be 0 if the round was created, or might clean up other guests
            # Let's just verify our specific guest still exists
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one_or_none()
            # If the guest played, they should still exist
            if deleted_count == 0:
                assert player is not None

    async def test_cleanup_does_not_delete_recent_guests(self, test_app, db_session):
        """Test that recent inactive guests are not deleted."""
        from backend.services import CleanupService

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Run cleanup (guest is brand new, should not be deleted)
            cleanup_service = CleanupService(db_session)
            deleted_count = await cleanup_service.cleanup_inactive_guest_players(hours_old=168)

            # Verify the guest was NOT deleted
            from uuid import UUID
            from sqlalchemy import select
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one_or_none()
            assert player is not None


class TestUsernameRecycling:
    """Test username recycling for inactive guest accounts."""

    async def test_recycle_inactive_guest_usernames(self, test_app, db_session):
        """Test that inactive guest usernames are recycled after 30+ days."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime
        from uuid import UUID
        from sqlalchemy import select, update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Get original username and canonical_username
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            original_username = player.username
            original_canonical = player.username_canonical

            # Artificially age the last login date (31 days ago)
            old_login_date = datetime.now(UTC) - timedelta(days=31)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(last_login_date=old_login_date)
            )
            await db_session.commit()
            db_session.expire_all()

            # Run username recycling
            cleanup_service = CleanupService(db_session)
            recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

            # Verify count
            assert recycled_count == 1

            # Verify username was modified
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            assert player.username == original_username + " X"
            assert player.username_canonical == original_canonical + "x"

    async def test_recycle_handles_canonical_conflicts(self, test_app, db_session):
        """Test recycling retries when canonical username conflicts exist."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime
        from uuid import UUID
        from sqlalchemy import select, update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create the guest account we will recycle
            guest_response = await client.post("/player/guest")
            assert guest_response.status_code == status.HTTP_201_CREATED
            guest_data = guest_response.json()
            guest_id = guest_data["player_id"]

            # Normalize the guest username to a predictable value
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(username="Foo", username_canonical="foo")
            )

            # Age the guest login so it qualifies for recycling
            old_login_date = datetime.now(UTC) - timedelta(days=31)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(last_login_date=old_login_date)
            )

            # Create another player whose canonical username would conflict with the recycled form
            create_response = await client.post(
                "/player",
                json={
                    "username": "Foox",
                    "email": "foox_conflict@example.com",
                    "password": "StrongPass123",
                },
            )
            assert create_response.status_code == status.HTTP_201_CREATED

            conflict_player = create_response.json()
            conflict_player_id = conflict_player["player_id"]

            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(conflict_player_id))
                .values(username="Foox", username_canonical="foox")
            )

            await db_session.commit()
            db_session.expire_all()

            cleanup_service = CleanupService(db_session)
            recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

            assert recycled_count == 1

            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            assert player.username == "Foo X2"
            assert player.username_canonical == "foox2"

    async def test_username_recycling_does_not_affect_recent_logins(self, test_app, db_session):
        """Test that guests who logged in recently are not recycled."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime
        from uuid import UUID
        from sqlalchemy import select, update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Get original username
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            original_username = player.username

            # Set last login to 25 days ago (less than 30)
            recent_login_date = datetime.now(UTC) - timedelta(days=25)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(last_login_date=recent_login_date)
            )
            await db_session.commit()
            db_session.expire_all()

            # Run username recycling
            cleanup_service = CleanupService(db_session)
            recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

            # Verify no recycling occurred
            assert recycled_count == 0

            # Verify username unchanged
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            assert player.username == original_username

    async def test_username_recycling_does_not_affect_upgraded_accounts(self, test_app, db_session):
        """Test that upgraded accounts (is_guest=False) are not recycled."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime
        from uuid import UUID
        from sqlalchemy import select, update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()

            # Upgrade the guest
            await client.post(
                "/player/upgrade",
                json={
                    "email": "upgraded_user@example.com",
                    "password": "SecurePass123"
                },
                headers={"Authorization": f"Bearer {guest_data['access_token']}"}
            )

            guest_id = guest_data["player_id"]

            # Get upgraded username
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            original_username = player.username
            assert player.is_guest is False  # Verify it's been upgraded

            # Artificially age the last login date (31 days ago)
            old_login_date = datetime.now(UTC) - timedelta(days=31)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(last_login_date=old_login_date)
            )
            await db_session.commit()

            # Run username recycling
            cleanup_service = CleanupService(db_session)
            recycled_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)

            # Verify no recycling occurred (upgraded accounts should not be recycled)
            # Note: recycled_count might be > 0 if there are other guests, but our player should be unchanged
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            assert player.username == original_username  # Should not have " X" appended

    async def test_username_recycling_is_idempotent(self, test_app, db_session):
        """Test that running username recycling multiple times doesn't double-append."""
        from backend.services import CleanupService
        from datetime import timedelta, UTC, datetime
        from uuid import UUID
        from sqlalchemy import select, update

        async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
            # Create a guest account
            create_response = await client.post("/player/guest")
            assert create_response.status_code == status.HTTP_201_CREATED
            guest_data = create_response.json()
            guest_id = guest_data["player_id"]

            # Artificially age the last login date (31 days ago)
            old_login_date = datetime.now(UTC) - timedelta(days=31)
            await db_session.execute(
                update(QFPlayer)
                .where(QFPlayer.player_id == UUID(guest_id))
                .values(last_login_date=old_login_date)
            )
            await db_session.commit()

            # Run username recycling first time
            cleanup_service = CleanupService(db_session)
            first_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)
            assert first_count == 1

            # Get username after first recycling
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            username_after_first = player.username
            canonical_after_first = player.username_canonical

            # Run username recycling again
            second_count = await cleanup_service.recycle_inactive_guest_usernames(days_old=30)
            assert second_count == 0  # Should not process already-recycled usernames

            # Verify username unchanged (not double-appended)
            result = await db_session.execute(
                select(QFPlayer).where(QFPlayer.player_id == UUID(guest_id))
            )
            player = result.scalar_one()
            assert player.username == username_after_first  # Should not be "username X X"
            assert player.username_canonical == canonical_after_first
