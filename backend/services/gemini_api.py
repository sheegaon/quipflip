"""
Helper for interacting with the Gemini generative API.

Provides structured gameplay decisions with error handling and fallback logic
for the Think Alike bot system.
"""

import sys
from backend.config import get_settings

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

from .prompt_builder import build_copy_prompt

__all__ = ["GeminiError", "generate", "generate_copy"]

settings = get_settings()


class GeminiError(RuntimeError):
    """Raised when the Gemini API cannot be contacted or returns an error."""


async def generate_copy(
        original_phrase: str,
        model: str = "gemini-2.5-flash-lite",
        timeout: int = 30,
        existing_copy_phrase: str = None,
) -> str:
    """
    Generate a copy phrase using Gemini API.

    Args:
        original_phrase: The original phrase to create a copy of
        model: Gemini model to use (default: gemini-2.5-flash-lite)
        timeout: Request timeout in seconds (currently unused, reserved for future)
        existing_copy_phrase: Another copy phrase already submitted (if any)

    Returns:
        The generated copy phrase as a string

    Raises:
        GeminiError: If API key is missing or API call fails
    """
    if genai is None:
        raise GeminiError("google-genai package not installed. Install with: pip install google-genai")

    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY environment variable must be set")

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        prompt = build_copy_prompt(original_phrase, existing_copy_phrase)

        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        output_text = ""
        for chunk in client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        ):
            if chunk.text is not None:
                output_text += chunk.text

        if not output_text:
            raise GeminiError("Gemini API returned empty response")

        # Clean and return the generated phrase
        return output_text.strip()

    except Exception as exc:
        if isinstance(exc, GeminiError):
            raise
        raise GeminiError(f"Failed to contact Gemini API: {exc}") from exc


def generate(input_text: str) -> str:
    """Legacy interface for backwards compatibility."""
    if not settings.gemini_api_key:
        raise GeminiError("GEMINI_API_KEY environment variable must be set")

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        model = "gemini-2.5-flash-lite"
        contents = [
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=input_text)],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        )

        output_text = ""
        for chunk in client.models.generate_content_stream(
                model=model,
                contents=contents,
                config=generate_content_config,
        ):
            if chunk.text is not None:
                output_text += chunk.text

        return output_text

    except Exception as exc:
        raise GeminiError(f"Failed to generate content: {exc}") from exc


if __name__ == "__main__":
    if len(sys.argv) > 1:
        result = generate(sys.argv[1])
        print(result)
    else:
        print("Usage: python gemini_api.py <input_text>")
