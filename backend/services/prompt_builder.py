"""
Shared prompt building utilities for AI copy generation.

This module provides reusable prompt construction logic used by both
Gemini and OpenAI AI providers, eliminating code duplication.
"""


def build_copy_prompt(original_phrase: str) -> str:
    """
    Build structured prompt for Think Alike gameplay copy generation.

    Args:
        original_phrase: The original phrase that was submitted for the prompt

    Returns:
        A formatted prompt string for AI copy generation
    """
    return f"""Given an original phrase for a prompt (which you do not know),
create a similar but different phrase.

Rules:
- 1-15 characters per word
- 1-5 words total
- Letters and spaces only
- Must pass dictionary validation
- Should be similar enough to be believable as the original
- Do NOT copy or lightly modify (e.g., pluralize) any words from the original phrase which are 4 or more letters long

Original phrase: "{original_phrase}"

Generate ONE alternative phrase only:"""


def build_vote_prompt(prompt_text: str, phrases: list[str]) -> str:
    """
    Build structured prompt for AI vote generation.

    Args:
        prompt_text: The prompt that the phrases were created for
        phrases: List of 3 phrases (1 original, 2 copies)

    Returns:
        A formatted prompt string for AI vote generation
    """
    phrases_formatted = "\n".join([f"{i+1}. {phrase}" for i, phrase in enumerate(phrases)])

    return f"""You are playing a word game where you need to identify the original phrase.

Given a prompt and three phrases, one phrase is the ORIGINAL that was submitted by a player,
and two phrases are COPIES created by other players trying to mimic the original.

Your task: Identify which phrase is most likely the ORIGINAL.

Prompt: "{prompt_text}"

Phrases:
{phrases_formatted}

Consider:
- The original is often more natural and straightforward
- Copies may try too hard or be slightly awkward
- The original usually best matches the prompt intent

Respond with ONLY the number (1, 2, or 3) of the phrase you believe is the original."""
