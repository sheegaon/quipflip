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

__all__ = [
    "OpenAIError",
    "OpenAIAPIError",
    "generate_response",
    "generate_embedding",
    "moderate_text",
]

settings = get_settings()


class OpenAIAPIError(RuntimeError):
    """Raised when the OpenAI API cannot be contacted or returns an error."""


async def generate_response(
        prompt: str,
        model: str = "gpt-5-nano",
        timeout: int = 120,
) -> str:
    """
    Generate a response using OpenAI API.

    Args:
        prompt: Prompt to send to the OpenAI API
        model: OpenAI model to use (default: gpt-5-nano)
        timeout: Request timeout in seconds

    Returns:
        The generated string

    Raises:
        OpenAIAPIError: If API key is missing or API call fails
    """
    if AsyncOpenAI is None:
        raise OpenAIAPIError("openai package not installed. Install with: pip install openai")

    if not settings.openai_api_key:
        raise OpenAIAPIError("OPENAI_API_KEY environment variable must be set")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "Play a creative word game."},
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
                           f"Prompt: '{prompt}', "
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


async def generate_embedding(
        input_text: str,
        model: str | None = None,
        timeout: int = 30,
) -> list[float]:
    """Generate a sentence embedding using the OpenAI API."""

    if AsyncOpenAI is None:
        raise OpenAIAPIError("openai package not installed. Install with: pip install openai")

    model_name = model or settings.embedding_model

    if not settings.openai_api_key:
        raise OpenAIAPIError("OPENAI_API_KEY environment variable must be set")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)

        response = await client.embeddings.create(
            model=model_name,
            input=[input_text],
        )

        if not response.data:
            raise OpenAIAPIError("OpenAI API returned no embedding data")

        embedding = response.data[0].embedding
        if not embedding:
            raise OpenAIAPIError("OpenAI API returned empty embedding vector")

        return embedding

    except OpenAIError as exc:
        raise OpenAIAPIError(f"OpenAI API error: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, OpenAIAPIError):
            raise
        raise OpenAIAPIError(f"Failed to contact OpenAI API: {exc}") from exc


async def moderate_text(input_text: str, timeout: int = 10) -> bool:
    """Run OpenAI's moderation endpoint against the provided text.

    Args:
        input_text: Text to moderate.
        timeout: Request timeout in seconds.

    Returns:
        True if the text is not flagged by the moderation endpoint; False otherwise.

    Raises:
        OpenAIAPIError: If the moderation request cannot be completed.
    """

    if AsyncOpenAI is None:
        raise OpenAIAPIError("openai package not installed. Install with: pip install openai")

    if not settings.openai_api_key:
        raise OpenAIAPIError("OPENAI_API_KEY environment variable must be set")

    try:
        client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=timeout)
        response = await client.moderations.create(
            model="omni-moderation-latest",
            input=input_text,
        )

        if not response.results:
            raise OpenAIAPIError("OpenAI API returned no moderation results")

        result = response.results[0]
        return not getattr(result, "flagged", False)

    except OpenAIError as exc:
        raise OpenAIAPIError(f"OpenAI API error: {exc}") from exc
    except Exception as exc:
        if isinstance(exc, OpenAIAPIError):
            raise
        raise OpenAIAPIError(f"Failed to contact OpenAI API: {exc}") from exc
