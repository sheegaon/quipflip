"""Tests for phrase validation client that calls remote phrase validation service.

This test suite covers:
- Client initialization and configuration
- Session lifecycle management (creation, reuse, closure)
- Async context manager support
- All validation methods: validate(), validate_prompt_phrase(), validate_copy()
- Common words retrieval
- Health check functionality
- Error handling: timeouts, client errors, API errors, unexpected errors
- Singleton pattern implementation
- Edge cases: missing response fields, already closed sessions, None parameters

Total: 44 tests covering all public methods and error conditions.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import aiohttp
from aiohttp import ClientTimeout, ClientError

from backend.services.phrase_validation_client import (
    PhraseValidationClient,
    get_phrase_validation_client,
)


@pytest.fixture
def mock_settings():
    """Mock settings for tests."""
    settings = MagicMock()
    settings.phrase_validator_url = "http://validator.example.com/"
    return settings


@pytest.fixture
def client(mock_settings):
    """Create a phrase validation client with mocked settings."""
    with patch("backend.services.phrase_validation_client.get_settings", return_value=mock_settings):
        return PhraseValidationClient()


class TestPhraseValidationClientInit:
    """Test client initialization."""

    def test_init_sets_base_url(self, client):
        """Test that initialization sets the base URL correctly."""
        assert client.base_url == "http://validator.example.com"

    def test_init_strips_trailing_slash(self, mock_settings):
        """Test that trailing slash is stripped from base URL."""
        mock_settings.phrase_validator_url = "http://validator.example.com///"
        with patch("backend.services.phrase_validation_client.get_settings", return_value=mock_settings):
            client = PhraseValidationClient()
            assert client.base_url == "http://validator.example.com"

    def test_init_sets_timeout(self, client):
        """Test that timeout is configured."""
        assert isinstance(client.timeout, ClientTimeout)
        assert client.timeout.total == 120

    def test_init_session_is_none(self, client):
        """Test that session is not created on init."""
        assert client._session is None


class TestSessionManagement:
    """Test aiohttp session lifecycle management."""

    @pytest.mark.asyncio
    async def test_ensure_session_creates_session(self, client):
        """Test that _ensure_session creates a new session."""
        assert client._session is None
        await client._ensure_session()
        assert client._session is not None
        assert isinstance(client._session, aiohttp.ClientSession)
        await client.close()

    @pytest.mark.asyncio
    async def test_ensure_session_reuses_existing_session(self, client):
        """Test that _ensure_session reuses existing session."""
        await client._ensure_session()
        first_session = client._session
        await client._ensure_session()
        second_session = client._session
        assert first_session is second_session
        await client.close()

    @pytest.mark.asyncio
    async def test_ensure_session_recreates_closed_session(self, client):
        """Test that _ensure_session recreates a closed session."""
        await client._ensure_session()
        first_session = client._session
        await client.close()
        await client._ensure_session()
        second_session = client._session
        assert first_session is not second_session
        await client.close()

    @pytest.mark.asyncio
    async def test_close_closes_session(self, client):
        """Test that close() closes the session."""
        await client._ensure_session()
        assert not client._session.closed
        await client.close()
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_when_session_is_none(self, client):
        """Test that close() handles None session gracefully."""
        assert client._session is None
        await client.close()  # Should not raise
        assert client._session is None

    @pytest.mark.asyncio
    async def test_close_when_session_already_closed(self, client):
        """Test that close() handles already closed session gracefully."""
        await client._ensure_session()
        await client._session.close()
        # When session is already closed, close() should not raise an error
        # but also won't set _session to None (session remains in closed state)
        await client.close()  # Should not raise
        assert client._session.closed

    def test_get_session_raises_when_not_initialized(self, client):
        """Test that _get_session raises error when session not initialized."""
        with pytest.raises(RuntimeError, match="Session not initialized"):
            client._get_session()

    @pytest.mark.asyncio
    async def test_get_session_returns_session(self, client):
        """Test that _get_session returns the session."""
        await client._ensure_session()
        session = client._get_session()
        assert session is client._session
        await client.close()


class TestContextManager:
    """Test async context manager support."""

    @pytest.mark.asyncio
    async def test_context_manager_creates_session(self, client):
        """Test that entering context creates session."""
        async with client as ctx_client:
            assert ctx_client is client
            assert client._session is not None

    @pytest.mark.asyncio
    async def test_context_manager_closes_session(self, client):
        """Test that exiting context closes session."""
        async with client:
            pass
        assert client._session is None

    @pytest.mark.asyncio
    async def test_context_manager_closes_on_exception(self, client):
        """Test that session is closed even when exception occurs."""
        with pytest.raises(ValueError):
            async with client:
                raise ValueError("Test error")
        assert client._session is None


class TestValidateMethod:
    """Test the validate() method."""

    @pytest.mark.asyncio
    async def test_validate_success(self, client):
        """Test successful validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate("ice cream")

        assert is_valid is True
        assert error == ""
        mock_session.post.assert_called_once_with(
            "http://validator.example.com/validate",
            json={"phrase": "ice cream"}
        )

    @pytest.mark.asyncio
    async def test_validate_failure(self, client):
        """Test validation failure."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "is_valid": False,
            "error": "Phrase must be at least 2 words"
        })

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate("word")

        assert is_valid is False
        assert "at least 2 words" in error

    @pytest.mark.asyncio
    async def test_validate_api_error(self, client):
        """Test validation when API returns error status."""
        mock_response = AsyncMock()
        mock_response.status = 500
        mock_response.text = AsyncMock(return_value="Internal Server Error")

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate("ice cream")

        assert is_valid is False
        assert "Validation service error: 500" in error

    @pytest.mark.asyncio
    async def test_validate_timeout(self, client):
        """Test validation when API times out."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(side_effect=TimeoutError())
            mock_session.closed = False

            is_valid, error = await client.validate("ice cream")

        assert is_valid is False
        assert "timeout" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_client_error(self, client):
        """Test validation when client error occurs."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(side_effect=ClientError())
            mock_session.closed = False

            is_valid, error = await client.validate("ice cream")

        assert is_valid is False
        assert "unavailable" in error.lower()

    @pytest.mark.asyncio
    async def test_validate_unexpected_error(self, client):
        """Test validation when unexpected error occurs."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(side_effect=ValueError("Unexpected"))
            mock_session.closed = False

            is_valid, error = await client.validate("ice cream")

        assert is_valid is False
        assert "error" in error.lower()


class TestValidatePromptPhraseMethod:
    """Test the validate_prompt_phrase() method."""

    @pytest.mark.asyncio
    async def test_validate_prompt_phrase_success(self, client):
        """Test successful prompt phrase validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_prompt_phrase(
                "ice cream",
                "What is your favorite dessert?"
            )

        assert is_valid is True
        assert error == ""
        mock_session.post.assert_called_once_with(
            "http://validator.example.com/validate/prompt",
            json={
                "phrase": "ice cream",
                "prompt_text": "What is your favorite dessert?"
            }
        )

    @pytest.mark.asyncio
    async def test_validate_prompt_phrase_failure(self, client):
        """Test prompt phrase validation failure."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "is_valid": False,
            "error": "Cannot reuse word 'dessert' from prompt"
        })

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_prompt_phrase(
                "favorite dessert",
                "What is your favorite dessert?"
            )

        assert is_valid is False
        assert "dessert" in error

    @pytest.mark.asyncio
    async def test_validate_prompt_phrase_with_none_prompt(self, client):
        """Test prompt phrase validation with None prompt text."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_prompt_phrase("ice cream", None)

        assert is_valid is True
        mock_session.post.assert_called_once()
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["prompt_text"] is None


class TestValidateCopyMethod:
    """Test the validate_copy() method."""

    @pytest.mark.asyncio
    async def test_validate_copy_success(self, client):
        """Test successful copy validation."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_copy(
                phrase="big liberty",
                original_phrase="small freedom"
            )

        assert is_valid is True
        assert error == ""
        mock_session.post.assert_called_once_with(
            "http://validator.example.com/validate/copy",
            json={
                "phrase": "big liberty",
                "original_phrase": "small freedom",
                "other_copy_phrase": None,
                "prompt_text": None
            }
        )

    @pytest.mark.asyncio
    async def test_validate_copy_with_all_params(self, client):
        """Test copy validation with all parameters."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_copy(
                phrase="big liberty",
                original_phrase="small freedom",
                other_copy_phrase="huge independence",
                prompt_text="What is your favorite concept?"
            )

        assert is_valid is True
        call_args = mock_session.post.call_args
        assert call_args[1]["json"]["phrase"] == "big liberty"
        assert call_args[1]["json"]["original_phrase"] == "small freedom"
        assert call_args[1]["json"]["other_copy_phrase"] == "huge independence"
        assert call_args[1]["json"]["prompt_text"] == "What is your favorite concept?"

    @pytest.mark.asyncio
    async def test_validate_copy_duplicate_rejected(self, client):
        """Test copy validation rejects duplicates."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "is_valid": False,
            "error": "Cannot submit the same phrase"
        })

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client.validate_copy(
                phrase="big freedom",
                original_phrase="big freedom"
            )

        assert is_valid is False
        assert "same phrase" in error.lower()


class TestCommonWordsMethod:
    """Test the common_words() method."""

    @pytest.mark.asyncio
    async def test_common_words_success(self, client):
        """Test successful retrieval of common words."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=["the", "a", "an", "of", "to"])

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            words = await client.common_words()

        assert words == {"the", "a", "an", "of", "to"}
        mock_session.get.assert_called_once_with("http://validator.example.com/common-words")

    @pytest.mark.asyncio
    async def test_common_words_empty_list(self, client):
        """Test common words returns empty set for empty list."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=[])

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            words = await client.common_words()

        assert words == set()

    @pytest.mark.asyncio
    async def test_common_words_unexpected_format(self, client):
        """Test common words handles unexpected response format."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"common_words": ["the", "a"]})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            words = await client.common_words()

        assert words == set()

    @pytest.mark.asyncio
    async def test_common_words_api_error(self, client):
        """Test common words handles API errors."""
        mock_response = AsyncMock()
        mock_response.status = 500

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            words = await client.common_words()

        assert words == set()

    @pytest.mark.asyncio
    async def test_common_words_timeout(self, client):
        """Test common words handles timeout."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(side_effect=TimeoutError())
            mock_session.closed = False

            words = await client.common_words()

        assert words == set()

    @pytest.mark.asyncio
    async def test_common_words_client_error(self, client):
        """Test common words handles client errors."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(side_effect=ClientError())
            mock_session.closed = False

            words = await client.common_words()

        assert words == set()


class TestHealthCheckMethod:
    """Test the health_check() method."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(self, client):
        """Test health check when service is healthy."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_healthy = await client.health_check()

        assert is_healthy is True
        mock_session.get.assert_called_once_with("http://validator.example.com/healthz")

    @pytest.mark.asyncio
    async def test_health_check_unhealthy_status(self, client):
        """Test health check when service returns unhealthy status."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "error"})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_healthy = await client.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_api_error(self, client):
        """Test health check when API returns error."""
        mock_response = AsyncMock()
        mock_response.status = 503

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(return_value=mock_response)
            mock_session.get.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.get.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_healthy = await client.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_timeout(self, client):
        """Test health check when request times out."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(side_effect=TimeoutError())
            mock_session.closed = False

            is_healthy = await client.health_check()

        assert is_healthy is False

    @pytest.mark.asyncio
    async def test_health_check_client_error(self, client):
        """Test health check when client error occurs."""
        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.get = MagicMock(side_effect=ClientError())
            mock_session.closed = False

            is_healthy = await client.health_check()

        assert is_healthy is False


class TestSingletonPattern:
    """Test the singleton pattern for the client."""

    def test_get_phrase_validation_client_returns_instance(self):
        """Test that get_phrase_validation_client returns an instance."""
        client = get_phrase_validation_client()
        assert isinstance(client, PhraseValidationClient)

    def test_get_phrase_validation_client_returns_same_instance(self):
        """Test that get_phrase_validation_client returns the same instance."""
        client1 = get_phrase_validation_client()
        client2 = get_phrase_validation_client()
        assert client1 is client2

    def test_singleton_resets_between_test_runs(self, client):
        """Test that singleton can be reset for testing."""
        # This test verifies that the fixture creates a new instance
        # rather than using the singleton
        singleton = get_phrase_validation_client()
        assert singleton is not client


class TestMakeRequestMethod:
    """Test the internal _make_request() method."""

    @pytest.mark.asyncio
    async def test_make_request_missing_is_valid(self, client):
        """Test _make_request handles missing is_valid in response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"error": "some error"})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client._make_request("/validate", {"phrase": "test"})

        # When is_valid is missing, it should default to False
        assert is_valid is False
        assert error == "some error"

    @pytest.mark.asyncio
    async def test_make_request_missing_error(self, client):
        """Test _make_request handles missing error in response."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True})

        with patch.object(client, "_session", create=True) as mock_session:
            mock_session.post = MagicMock(return_value=mock_response)
            mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_session.post.return_value.__aexit__ = AsyncMock()
            mock_session.closed = False

            is_valid, error = await client._make_request("/validate", {"phrase": "test"})

        assert is_valid is True
        # When error is missing, it should default to empty string
        assert error == ""

    @pytest.mark.asyncio
    async def test_make_request_ensures_session(self, client):
        """Test that _make_request ensures session is created."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"is_valid": True, "error": ""})

        # Don't pre-create session - let _make_request do it
        assert client._session is None

        with patch.object(client, "_ensure_session") as mock_ensure:
            mock_ensure.return_value = None
            with patch.object(client, "_session", create=True) as mock_session:
                mock_session.post = MagicMock(return_value=mock_response)
                mock_session.post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_session.post.return_value.__aexit__ = AsyncMock()
                mock_session.closed = False

                await client._make_request("/validate", {"phrase": "test"})

        # Verify _ensure_session was called
        mock_ensure.assert_called_once()
