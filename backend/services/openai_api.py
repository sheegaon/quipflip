"""
Helper for interacting with the OpenAI API.

Provides copy phrase generation with error handling and fallback logic
for the Think Alike AI backup system.
"""

import os

try:
    from openai import AsyncOpenAI, OpenAIError
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OpenAIError = Exception  # type: ignore

from .prompt_builder import build_copy_prompt

__all__ = ["OpenAIError", "generate_copy"]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


class OpenAIAPIError(RuntimeError):
    """Raised when the OpenAI API cannot be contacted or returns an error."""


async def generate_copy(
        original_phrase: str,
        model: str = "gpt-5-nano",
        timeout: int = 30,
) -> str:
    """
    Generate a copy phrase using OpenAI API.

    Args:
        original_phrase: The original phrase to create a copy of
        prompt_text: The prompt text for context
        model: OpenAI model to use (default: gpt-5-nano)
        timeout: Request timeout in seconds

    Returns:
        The generated copy phrase as a string

    Raises:
        OpenAIAPIError: If API key is missing or API call fails
    """
    if AsyncOpenAI is None:
        raise OpenAIAPIError("openai package not installed. Install with: pip install openai")

    if not OPENAI_API_KEY:
        raise OpenAIAPIError("OPENAI_API_KEY environment variable must be set")

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout)
        prompt = build_copy_prompt(original_phrase)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are playing a creative word game."},
                {"role": "user", "content": prompt}
            ],
            max_completion_tokens=50
        )

        if not response.choices:
            raise OpenAIAPIError("OpenAI API returned no choices")

        output_text = response.choices[0].message.content
        if not output_text:
            raise OpenAIAPIError("OpenAI API returned empty response")

        # Clean and return the generated phrase
        return output_text.strip()

    except OpenAIError as exc:
        raise OpenAIAPIError(f"OpenAI API error: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, OpenAIAPIError):
            raise
        raise OpenAIAPIError(f"Failed to contact OpenAI API: {exc}") from exc
