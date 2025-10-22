"""Phrase validation client for remote phrase validation service."""
import asyncio
import logging
from typing import Tuple
import aiohttp
from aiohttp import ClientTimeout, ClientError

from backend.config import get_settings

logger = logging.getLogger(__name__)


class PhraseValidationClient:
    """Client for remote phrase validation service."""

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.phrase_validator_url.rstrip('/')
        self.timeout = ClientTimeout(total=30)  # 30 second timeout
        self._session = aiohttp.ClientSession(timeout=self.timeout)

    async def close(self):
        """Close the underlying aiohttp client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _make_request(self, endpoint: str, payload: dict) -> Tuple[bool, str]:
        """Make HTTP request to validation service."""
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

    async def validate(self, phrase: str) -> Tuple[bool, str]:
        """
        Validate a phrase for format and dictionary compliance.

        Args:
            phrase: The phrase to validate

        Returns:
            (is_valid, error_message)
        """
        payload = {"phrase": phrase}
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
        return await self._make_request("/validate/copy", payload)

    async def health_check(self) -> bool:
        """
        Check if the phrase validation service is healthy.

        Returns:
            True if service is healthy, False otherwise
        """
        url = f"{self.base_url}/healthz"
        
        try:
            async with aiohttp.ClientSession(timeout=self.timeout) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get("status") == "ok"
                    else:
                        logger.error(f"Phrase validator health check failed: {response.status}")
                        return False
                        
        except Exception as e:
            logger.error(f"Phrase validator health check error: {e}")
            return False


# Singleton instance
_phrase_validation_client: PhraseValidationClient | None = None


def get_phrase_validation_client() -> PhraseValidationClient:
    """Get singleton phrase validation client instance."""
    global _phrase_validation_client
    if _phrase_validation_client is None:
        _phrase_validation_client = PhraseValidationClient()
    return _phrase_validation_client