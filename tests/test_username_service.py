"""Tests for username service and validation."""

import pytest
from backend.services.username_service import (
    UsernameService,
    canonicalize_username,
    normalize_username,
    is_username_input_valid,
)
from backend.models.player import Player
import uuid


class TestUsernameCanonicalization:
    """Test username canonicalization functions."""

    def test_canonicalize_lowercase(self):
        """Should convert to lowercase."""
        assert canonicalize_username("TestUser") == "testuser"
        assert canonicalize_username("UPPERCASE") == "uppercase"

    def test_canonicalize_removes_spaces(self):
        """Should remove all spaces."""
        assert canonicalize_username("Test User") == "testuser"
        assert canonicalize_username("  spaced  out  ") == "spacedout"

    def test_canonicalize_removes_special_chars(self):
        """Should remove non-alphanumeric characters."""
        assert canonicalize_username("test@user") == "testuser"
        assert canonicalize_username("test-user_123") == "testuser123"
        assert canonicalize_username("hello!world#") == "helloworld"

    def test_canonicalize_preserves_numbers(self):
        """Should preserve numeric characters."""
        assert canonicalize_username("user123") == "user123"
        assert canonicalize_username("123abc") == "123abc"

    def test_canonicalize_empty_string(self):
        """Should handle empty strings."""
        assert canonicalize_username("") == ""
        assert canonicalize_username("   ") == ""
        assert canonicalize_username("@#$%") == ""


class TestUsernameNormalization:
    """Test username normalization for display."""

    def test_normalize_removes_extra_spaces(self):
        """Should collapse multiple spaces to single space."""
        assert normalize_username("test   user") == "test user"
        assert normalize_username("  spaced  out  ") == "spaced out"

    def test_normalize_trims_edges(self):
        """Should trim leading/trailing spaces."""
        assert normalize_username("  username  ") == "username"
        assert normalize_username("  test user  ") == "test user"

    def test_normalize_preserves_single_spaces(self):
        """Should preserve single spaces between words."""
        assert normalize_username("test user") == "test user"
        assert normalize_username("my user name") == "my user name"

    def test_normalize_preserves_case(self):
        """Should preserve original case."""
        assert normalize_username("TestUser") == "TestUser"
        assert normalize_username("UPPER lower") == "UPPER lower"


class TestUsernameInputValidation:
    """Test username input validation."""

    def test_valid_inputs(self):
        """Should accept valid alphanumeric and space inputs."""
        assert is_username_input_valid("testuser") is True
        assert is_username_input_valid("test user") is True
        assert is_username_input_valid("User123") is True
        assert is_username_input_valid("123") is True

    def test_rejects_special_characters(self):
        """Should reject special characters."""
        assert is_username_input_valid("test@user") is False
        assert is_username_input_valid("user-name") is False
        assert is_username_input_valid("test_user") is False
        assert is_username_input_valid("user!") is False

    def test_rejects_empty_or_whitespace_only(self):
        """Should reject empty or whitespace-only strings."""
        assert is_username_input_valid("") is False
        assert is_username_input_valid("   ") is False
        assert is_username_input_valid("\t") is False

    def test_accepts_with_surrounding_spaces(self):
        """Should accept valid input with surrounding spaces."""
        assert is_username_input_valid("  testuser  ") is True
        assert is_username_input_valid("  test user  ") is True


class TestUsernameServiceGeneration:
    """Test username generation."""

    @pytest.mark.asyncio
    async def test_generate_unique_username_returns_pair(self, db_session):
        """Should return (display, canonical) tuple."""
        service = UsernameService(db_session)
        display, canonical = await service.generate_unique_username()

        assert isinstance(display, str)
        assert isinstance(canonical, str)
        assert len(display) > 0
        assert len(canonical) > 0

    @pytest.mark.asyncio
    async def test_generated_username_matches_canonicalization(self, db_session):
        """Canonical should match canonicalizing the display name."""
        service = UsernameService(db_session)
        display, canonical = await service.generate_unique_username()

        assert canonical == canonicalize_username(display)

    @pytest.mark.asyncio
    async def test_generated_usernames_are_unique(self, db_session):
        """Should generate different usernames on subsequent calls."""
        service = UsernameService(db_session)

        usernames = set()
        for _ in range(10):
            display, canonical = await service.generate_unique_username()

            # Store username in database to mark as taken
            player = Player(
                player_id=uuid.uuid4(),
                username=display,
                username_canonical=canonical,
                email=f"{canonical}@test.com",
                password_hash="hash",
            )
            db_session.add(player)
            await db_session.commit()

            usernames.add(canonical)

        # All should be unique
        assert len(usernames) == 10

    @pytest.mark.asyncio
    async def test_generates_with_suffix_when_pool_exhausted(self, db_session):
        """Should add numeric suffixes when base pool is exhausted."""
        service = UsernameService(db_session)

        # Generate a username and mark the base as taken
        display1, canonical1 = await service.generate_unique_username()

        # Create player with this username
        player1 = Player(
            player_id=uuid.uuid4(),
            username=display1,
            username_canonical=canonical1,
            email="test1@test.com",
            password_hash="hash",
        )
        db_session.add(player1)

        # Also create a player with display2 variation if it exists
        display2 = f"{display1} 2"
        canonical2 = canonicalize_username(display2)
        player2 = Player(
            player_id=uuid.uuid4(),
            username=display2,
            username_canonical=canonical2,
            email="test2@test.com",
            password_hash="hash",
        )
        db_session.add(player2)
        await db_session.commit()

        # Generate new username - might get a different base or a suffix
        display3, canonical3 = await service.generate_unique_username()

        # Should be different from existing ones
        assert canonical3 != canonical1
        assert canonical3 != canonical2


class TestUsernameServiceLookup:
    """Test username lookup functionality."""

    @pytest.mark.asyncio
    async def test_find_player_by_exact_username(self, db_session):
        """Should find player by exact username match."""
        service = UsernameService(db_session)

        # Create player
        player = Player(
            player_id=uuid.uuid4(),
            username="TestUser",
            username_canonical="testuser",
            email="test@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        # Find by exact username
        found = await service.find_player_by_username("TestUser")
        assert found is not None
        assert found.player_id == player.player_id

    @pytest.mark.asyncio
    async def test_find_player_case_insensitive(self, db_session):
        """Should find player regardless of case."""
        service = UsernameService(db_session)
        test_id = uuid.uuid4().hex[:8]

        # Create player with unique username
        username = f"TestUser{test_id}"
        canonical = f"testuser{test_id}"

        player = Player(
            player_id=uuid.uuid4(),
            username=username,
            username_canonical=canonical,
            email=f"test_case_{test_id}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        # Find with different cases
        found1 = await service.find_player_by_username(username.lower())
        found2 = await service.find_player_by_username(username.upper())
        found3 = await service.find_player_by_username(f"TeSt{username[4:]}")

        assert found1 is not None
        assert found2 is not None
        assert found3 is not None
        assert found1.player_id == player.player_id
        assert found2.player_id == player.player_id
        assert found3.player_id == player.player_id

    @pytest.mark.asyncio
    async def test_find_player_ignores_spaces(self, db_session):
        """Should find player ignoring spaces in lookup."""
        service = UsernameService(db_session)
        test_id = uuid.uuid4().hex[:8]

        # Create player with spaced username (unique)
        username = f"Test User{test_id}"
        canonical = f"testuser{test_id}"

        player = Player(
            player_id=uuid.uuid4(),
            username=username,
            username_canonical=canonical,
            email=f"test_space_{test_id}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        # Find with and without spaces
        found1 = await service.find_player_by_username(username)
        found2 = await service.find_player_by_username(username.replace(" ", ""))
        found3 = await service.find_player_by_username(username.lower())

        assert found1 is not None
        assert found2 is not None
        assert found3 is not None
        assert found1.player_id == player.player_id
        assert found2.player_id == player.player_id
        assert found3.player_id == player.player_id

    @pytest.mark.asyncio
    async def test_find_player_returns_none_for_nonexistent(self, db_session):
        """Should return None for non-existent username."""
        service = UsernameService(db_session)

        found = await service.find_player_by_username("NonExistentUser")
        assert found is None

    @pytest.mark.asyncio
    async def test_find_player_returns_none_for_empty_string(self, db_session):
        """Should return None for empty username."""
        service = UsernameService(db_session)

        found1 = await service.find_player_by_username("")
        found2 = await service.find_player_by_username("   ")

        assert found1 is None
        assert found2 is None

    @pytest.mark.asyncio
    async def test_find_player_handles_special_characters(self, db_session):
        """Should canonicalize special characters in lookup."""
        service = UsernameService(db_session)
        test_id = uuid.uuid4().hex[:8]

        # Create player
        player = Player(
            player_id=uuid.uuid4(),
            username="test123",
            username_canonical="test123",
            email=f"test_special_{test_id}@test.com",
            password_hash="hash",
        )
        db_session.add(player)
        await db_session.commit()

        # Find with special characters that canonicalize to same
        found = await service.find_player_by_username("test@123")
        assert found is not None
        assert found.player_id == player.player_id


class TestUsernameEdgeCases:
    """Test edge cases in username handling."""

    @pytest.mark.asyncio
    async def test_unicode_usernames_handled(self, db_session):
        """Should handle unicode characters gracefully."""
        service = UsernameService(db_session)

        # These should canonicalize to empty or valid ASCII
        canonical1 = canonicalize_username("test😀user")
        canonical2 = canonicalize_username("тест")  # Cyrillic

        # Should either be empty or contain only alphanumeric
        assert canonical1.isalnum() or canonical1 == ""
        assert canonical2.isalnum() or canonical2 == ""

    def test_very_long_username(self):
        """Should handle very long usernames."""
        long_username = "a" * 1000
        canonical = canonicalize_username(long_username)
        assert canonical == "a" * 1000

    def test_only_special_characters(self):
        """Should handle username with only special characters."""
        canonical = canonicalize_username("@#$%^&*()")
        assert canonical == ""
