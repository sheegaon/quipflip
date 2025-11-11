"""Phrase validation client for remote phrase validation service."""
import asyncio
import logging
from typing import Tuple, Optional
import aiohttp
from aiohttp import ClientTimeout, ClientError

from backend.config import get_settings

logger = logging.getLogger(__name__)


class PhraseValidationClient:
    """
    Client for remote phrase validation service.

    Manages HTTP session lifecycle properly to prevent resource leaks.
    Session is created lazily on first use and should be closed on shutdown.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.phrase_validator_url.rstrip('/')
        self.timeout = ClientTimeout(total=120)  # 120 second timeout for hint generation
        self._session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - ensure session is closed."""
        await self.close()

    async def _ensure_session(self):
        """Ensure session exists and is not closed."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            logger.debug("Created new aiohttp session for phrase validation client")

    def _get_session(self) -> aiohttp.ClientSession:
        """
        Get the aiohttp session.

        Note: Use _ensure_session() in async methods instead.
        This method exists for backwards compatibility but should not be used directly.
        """
        if self._session is None:
            raise RuntimeError("Session not initialized. Call _ensure_session() first.")
        return self._session

    async def close(self):
        """Close the underlying aiohttp client session."""
        if self._session and not self._session.closed:
            await self._session.close()
            logger.debug("Closed aiohttp session for phrase validation client")
            self._session = None

    async def _make_request(self, endpoint: str, payload: dict) -> Tuple[bool, str]:
        """Make HTTP request to validation service."""
        await self._ensure_session()
        url = f"{self.base_url}{endpoint}"

        try:
            async with self._session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("is_valid", False), data.get("error", "")
                else:
                    error_text = await response.text()
                    logger.error(f"Phrase validator API error {response.status}: {error_text}")
                    return False, f"Validation service error: {response.status}"
                        
        except asyncio.TimeoutError:
            logger.error(f"Phrase validator API timeout for {endpoint}")
            return False, "Validation service timeout - please try again"
        except ClientError as e:
            logger.error(f"Phrase validator API client error for {endpoint}: {e}")
            return False, "Validation service unavailable - please try again"
        except Exception as e:
            logger.error(f"Phrase validator API unexpected error for {endpoint}: {e}")
            return False, "Validation service error - please try again"

    async def common_words(self) -> set[str]:
        """
        Retrieve the set of common words from the validation service.

        Returns:
            Set of common words.
        """
        await self._ensure_session()
        url = f"{self.base_url}/common-words"

        try:
            async with self._session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # The API returns a list directly, not a dict with "common_words" key
                    if isinstance(data, list):
                        return set(data)
                    else:
                        # Fallback for unexpected response format
                        logger.warning(f"Unexpected response format from common-words API: {type(data)}")
                        return set()
                else:
                    logger.error(f"Phrase validator common words API error: {response.status}")
                    return set()

        except asyncio.TimeoutError:
            logger.error("Phrase validator common words API timeout")
            return set()
        except ClientError as e:
            logger.error(f"Phrase validator common words API client error: {e}")
            return set()
        except Exception as e:
            logger.error(f"Phrase validator common words API unexpected error: {e}")
            return set()

    async def validate(self, phrase: str) -> Tuple[bool, str]:
        """
        Validate a phrase for format and dictionary compliance.

        Args:
            phrase: The phrase to validate

        Returns:
            (is_valid, error_message)
        """
        payload = {"phrase": phrase}
        logger.info(f"Validating phrase: {phrase}")
        return await self._make_request("/validate", payload)

    async def validate_prompt_phrase(self, phrase: str, prompt_text: str | None) -> Tuple[bool, str]:
        """
        Validate a prompt submission against the originating prompt text.

        Args:
            phrase: The phrase to validate
            prompt_text: The prompt text to check relevance against

        Returns:
            (is_valid, error_message)
        """
        payload = {
            "phrase": phrase,
            "prompt_text": prompt_text
        }
        logger.info(f"Validating prompt phrase: {phrase} against prompt text: {prompt_text}")
        return await self._make_request("/validate/prompt", payload)

    async def validate_copy(
        self,
        phrase: str,
        original_phrase: str,
        other_copy_phrase: str | None = None,
        prompt_text: str | None = None,
    ) -> Tuple[bool, str]:
        """
        Validate a copy phrase (includes duplicate and similarity checks).

        Args:
            phrase: The copy phrase to validate
            original_phrase: The original prompt phrase
            other_copy_phrase: The other copy phrase (if already submitted)
            prompt_text: The prompt text associated with the original submission

        Returns:
            (is_valid, error_message)
        """
        payload = {
            "phrase": phrase,
            "original_phrase": original_phrase,
            "other_copy_phrase": other_copy_phrase,
            "prompt_text": prompt_text
        }
        logger.info(f"Validating copy phrase: {phrase} against original: {original_phrase} prompt: {prompt_text} "
                    f"and other copy: {other_copy_phrase}")
        return await self._make_request("/validate/copy", payload)

    async def health_check(self) -> bool:
        """
        Check if the phrase validation service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        await self._ensure_session()
        url = f"{self.base_url}/healthz"

        try:
            async with self._session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("status") == "ok"
                else:
                    logger.error(f"Phrase validator health check failed: {response.status}")
                    return False
                        
        except asyncio.TimeoutError:
            logger.error("Phrase validator health check timeout")
            return False
        except ClientError as e:
            logger.error(f"Phrase validator health check client error: {e}")
            return False
        except Exception as e:
            logger.error(f"Phrase validator health check unexpected error: {e}")
            return False


# Singleton instance
_phrase_validation_client: PhraseValidationClient | None = None


def get_phrase_validation_client() -> PhraseValidationClient:
    """Get singleton phrase validation client instance."""
    global _phrase_validation_client
    if _phrase_validation_client is None:
        _phrase_validation_client = PhraseValidationClient()
    return _phrase_validation_client
