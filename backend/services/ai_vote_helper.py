"""
AI voting helper for generating votes using AI providers.

This module provides AI-powered vote generation to help determine
which phrase in a phraseset is the original.
"""

import os
import random

from .prompt_builder import build_vote_prompt

try:
    from openai import AsyncOpenAI, OpenAIError
except ImportError:
    AsyncOpenAI = None  # type: ignore
    OpenAIError = Exception  # type: ignore

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore

__all__ = ["AIVoteError", "generate_vote_choice"]

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class AIVoteError(RuntimeError):
    """Raised when AI vote generation fails."""


async def generate_vote_choice_openai(
        prompt_text: str,
        phrases: list[str],
        model: str = "gpt-5-nano",
        timeout: int = 30,
) -> int:
    """
    Generate a vote choice using OpenAI API.

    Args:
        prompt_text: The prompt text
        phrases: List of 3 phrases to choose from
        model: OpenAI model to use
        timeout: Request timeout in seconds

    Returns:
        Index (0-2) of the chosen phrase

    Raises:
        AIVoteError: If generation fails
    """
    if AsyncOpenAI is None:
        raise AIVoteError("openai package not installed. Install with: pip install openai")

    if not OPENAI_API_KEY:
        raise AIVoteError("OPENAI_API_KEY environment variable must be set")

    if len(phrases) != 3:
        raise AIVoteError(f"Expected 3 phrases, got {len(phrases)}")

    try:
        client = AsyncOpenAI(api_key=OPENAI_API_KEY, timeout=timeout)
        prompt = build_vote_prompt(prompt_text, phrases)

        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert at identifying original vs copied phrases in word games."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=10,
            temperature=0.7,
        )

        if not response.choices:
            raise AIVoteError("OpenAI API returned no choices")

        output_text = response.choices[0].message.content
        if not output_text:
            raise AIVoteError("OpenAI API returned empty response")

        # Parse the choice (should be 1, 2, or 3)
        choice = int(output_text.strip())
        if choice < 1 or choice > 3:
            raise AIVoteError(f"Invalid choice: {choice}")

        # Convert to 0-based index
        return choice - 1

    except OpenAIError as exc:
        raise AIVoteError(f"OpenAI API error: {exc}") from exc
    except ValueError as exc:
        # If parsing failed, return random choice
        return random.randint(0, 2)
    except Exception as exc:
        if isinstance(exc, AIVoteError):
            raise
        raise AIVoteError(f"Failed to contact OpenAI API: {exc}") from exc


async def generate_vote_choice_gemini(
        prompt_text: str,
        phrases: list[str],
        model: str = "gemini-2.5-flash-lite",
        timeout: int = 30,
) -> int:
    """
    Generate a vote choice using Gemini API.

    Args:
        prompt_text: The prompt text
        phrases: List of 3 phrases to choose from
        model: Gemini model to use
        timeout: Request timeout in seconds (currently unused)

    Returns:
        Index (0-2) of the chosen phrase

    Raises:
        AIVoteError: If generation fails
    """
    if genai is None:
        raise AIVoteError("google-genai package not installed. Install with: pip install google-genai")

    if not GEMINI_API_KEY:
        raise AIVoteError("GEMINI_API_KEY environment variable must be set")

    if len(phrases) != 3:
        raise AIVoteError(f"Expected 3 phrases, got {len(phrases)}")

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        prompt = build_vote_prompt(prompt_text, phrases)

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
            raise AIVoteError("Gemini API returned empty response")

        # Parse the choice (should be 1, 2, or 3)
        choice = int(output_text.strip())
        if choice < 1 or choice > 3:
            raise AIVoteError(f"Invalid choice: {choice}")

        # Convert to 0-based index
        return choice - 1

    except ValueError as exc:
        # If parsing failed, return random choice
        return random.randint(0, 2)
    except Exception as exc:
        if isinstance(exc, AIVoteError):
            raise
        raise AIVoteError(f"Failed to contact Gemini API: {exc}") from exc


async def generate_vote_choice(
        prompt_text: str,
        phrases: list[str],
        provider: str = "openai",
        openai_model: str = "gpt-5-nano",
        gemini_model: str = "gemini-2.5-flash-lite",
        timeout: int = 30,
) -> int:
    """
    Generate a vote choice using the specified AI provider.

    Args:
        prompt_text: The prompt text
        phrases: List of 3 phrases to choose from
        provider: "openai" or "gemini"
        openai_model: OpenAI model to use
        gemini_model: Gemini model to use
        timeout: Request timeout in seconds

    Returns:
        Index (0-2) of the chosen phrase

    Raises:
        AIVoteError: If generation fails
    """
    if provider.lower() == "openai":
        return await generate_vote_choice_openai(
            prompt_text=prompt_text,
            phrases=phrases,
            model=openai_model,
            timeout=timeout,
        )
    elif provider.lower() == "gemini":
        return await generate_vote_choice_gemini(
            prompt_text=prompt_text,
            phrases=phrases,
            model=gemini_model,
            timeout=timeout,
        )
    else:
        raise AIVoteError(f"Unknown provider: {provider}. Use 'openai' or 'gemini'")
