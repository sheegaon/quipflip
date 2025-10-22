"""Async client for the phrase validation worker service."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Tuple

import httpx

from backend.config import get_settings

logger = logging.getLogger(__name__)


class PhraseValidationServiceError(RuntimeError):
    """Raised when the remote phrase validation service cannot be reached."""


class PhraseValidationClient:
    """HTTP client for delegating phrase validation to a worker service."""

    def __init__(self, base_url: str, timeout: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None
        self._lock = asyncio.Lock()

    async def startup(self) -> None:
        """Initialize the underlying HTTP client."""
        async with self._lock:
            if self._client is None:
                logger.info("Connecting to phrase validation service at %s", self._base_url)
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=self._timeout,
                )

    async def shutdown(self) -> None:
        """Close the underlying HTTP client."""
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def _post(self, endpoint: str, payload: dict[str, Any]) -> Tuple[bool, str]:
        client = await self._ensure_client()
        try:
            response = await client.post(endpoint, json=payload)
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network dependent
            logger.error("Phrase validation request failed: %s", exc)
            raise PhraseValidationServiceError("Phrase validation service unavailable") from exc

        data = response.json()
        return bool(data.get("is_valid", False)), str(data.get("error", ""))

    async def validate(self, phrase: str) -> Tuple[bool, str]:
        """Validate a phrase without additional context."""
        return await self._post("/validate", {"phrase": phrase})

    async def validate_prompt_phrase(self, phrase: str, prompt_text: str | None) -> Tuple[bool, str]:
        """Validate a prompt submission against the prompt text."""
        payload = {"phrase": phrase, "prompt_text": prompt_text}
        return await self._post("/validate/prompt", payload)

    async def validate_copy(
        self,
        phrase: str,
        original_phrase: str,
        other_copy_phrase: str | None,
        prompt_text: str | None,
    ) -> Tuple[bool, str]:
        """Validate a copy submission against other phrases."""
        payload = {
            "phrase": phrase,
            "original_phrase": original_phrase,
            "other_copy_phrase": other_copy_phrase,
            "prompt_text": prompt_text,
        }
        return await self._post("/validate/copy", payload)

    async def health_check(self) -> bool:
        """Check if the worker is reachable."""
        client = await self._ensure_client()
        try:
            response = await client.get("/healthz")
            response.raise_for_status()
        except httpx.HTTPError as exc:  # pragma: no cover - network dependent
            logger.error("Phrase validation health check failed: %s", exc)
            return False
        data = response.json()
        return bool(data.get("status") == "ok")


_phrase_validation_client: PhraseValidationClient | None = None


def get_phrase_validation_client() -> PhraseValidationClient:
    """Return the singleton phrase validation client."""
    global _phrase_validation_client
    if _phrase_validation_client is None:
        settings = get_settings()
        _phrase_validation_client = PhraseValidationClient(
            base_url=settings.phrase_validator_url,
            timeout=settings.phrase_validator_timeout,
        )
    return _phrase_validation_client
