"""
Helper for interacting with the OpenAI API.

Provides copy phrase generation with error handling and fallback logic
for the Think Alike AI backup system.
"""

from backend.config import get_settings

try:
    from openai import AsyncOpenAI, OpenAIError
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OpenAIError = Exception  # type: ignore

from .prompt_builder import build_copy_prompt

__all__ = ["OpenAIError", "generate_copy"]

settings = get_settings()


class OpenAIAPIError(RuntimeError):
    """Raised when the OpenAI API cannot be contacted or returns an error."""


async def generate_copy(
        original_phrase: str,
        model: str = "gpt-5-nano",
        timeout: int = 30,
        existing_copy_phrase: str = None,
) -> str:
    """
    Generate a copy phrase using OpenAI API.

    Args:
        original_phrase: The original phrase to create a copy of
        model: OpenAI model to use (default: gpt-5-nano)
        timeout: Request timeout in seconds
        existing_copy_phrase: Another copy phrase already submitted (if any)

    Returns:
        The generated copy phrase as a string

    Raises:
        OpenAIAPIError: If API key is missing or API call fails
    """
    if AsyncOpenAI is None:
        raise OpenAIAPIError("openai package not installed. Install with: pip install openai")

    if not settings.openai_api_key:
        raise OpenAIAPIError("OPENAI_API_KEY environment variable must be set")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
        prompt = build_copy_prompt(original_phrase, existing_copy_phrase)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are playing a creative word game."},
                {"role": "user", "content": prompt}
            ])

        if not response.choices:
            raise OpenAIAPIError("OpenAI API returned no choices")

        choice = response.choices[0]
        if not choice.message:
            raise OpenAIAPIError("OpenAI API returned choice without message")

        output_text = choice.message.content
        if not output_text or not output_text.strip():
            # Log additional debugging info
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"OpenAI returned empty content. Model: {model}, "
                           f"Finish reason: {choice.finish_reason}, "
                           f"Original phrase: '{original_phrase}', "
                           f"Response: {response}")
            raise OpenAIAPIError("OpenAI API returned empty response content")

        # Clean and return the generated phrase
        cleaned_phrase = output_text.strip()
        if not cleaned_phrase:
            raise OpenAIAPIError("OpenAI API returned only whitespace")

        return cleaned_phrase

    except OpenAIError as exc:
        raise OpenAIAPIError(f"OpenAI API error: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, OpenAIAPIError):
            raise
        raise OpenAIAPIError(f"Failed to contact OpenAI API: {exc}") from exc
