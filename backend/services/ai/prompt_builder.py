"""
Shared prompt building utilities for AI copy generation.

This module provides reusable prompt construction logic used by both
Gemini and OpenAI AI providers, eliminating code duplication.
"""

import random


def build_copy_prompt(original_phrase: str, existing_copy_phrase: str = None) -> str:
    """
    Build structured prompt for Think Alike gameplay copy generation.

    Args:
        original_phrase: The original phrase that was submitted for the prompt
        existing_copy_phrase: Another copy phrase already submitted (if any)

    Returns:
        A formatted prompt string for AI copy generation
    """
    base_prompt = """Create a phrase meaning roughly the same thing as the original phrase.

**Original phrase: "{original_phrase}"**

Rules:
- 1-15 characters per word
- 2-5 words total, 4-100 characters total
- Letters and spaces only
- Each word must pass dictionary validation
- Phrase should be similar enough to be believable as the original"""

    if existing_copy_phrase:
        base_prompt += f"""
- **IMPORTANT: Another player already submitted this copy: "{existing_copy_phrase}"**"""
        base_prompt += """
- Do NOT use or lightly modify (e.g., pluralize) any words from either the original phrase or the existing copy phrase
  which are 4 or more letters long, except common words {common_words}"""
    else:
        base_prompt += """
- Do NOT use or lightly modify (e.g., pluralize) any words from the original phrase which are 4 or more letters long, 
  except common words: [{common_words}]"""

    base_prompt += f"""

Generate ONE alternative phrase only:"""

    return base_prompt


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
    considerations = [
        "- The original is often more natural and straightforward",
        "- Copies may try too hard or be slightly awkward",
        "- The original usually best matches the prompt intent",
        "- Look for subtle differences in word choice and phrasing",
        "- Consider the length and complexity of each phrase",
    ]
    chosen_considerations = list(set(random.choices(considerations, k=2)))  # Shuffle considerations for variety
    chosen_considerations = ''.join([f"\n{c}" for c in chosen_considerations])

    return f"""You are playing a word game where you need to identify the original phrase.

Given a prompt and three phrases, one phrase is the ORIGINAL that was submitted by a player, and two phrases are COPIES created by other players trying to mimic the original.

Your task: Identify which phrase is most likely the ORIGINAL.

Prompt: "{prompt_text}"

Consider:{chosen_considerations}

Phrases:
{phrases_formatted}

Respond with ONLY the number (1, 2, or 3) of the phrase you believe is the original."""
