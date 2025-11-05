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


def build_hint_prompt(original_phrase: str, prompt_text: str, existing_hints: list[str] | None = None) -> str:
    """
    Build structured prompt for generating diverse copy hints.

    Args:
        original_phrase: The original phrase that players must imitate
        prompt_text: The prompt text that produced the original phrase
        existing_hints: Hints that have already been generated (to avoid duplicates)

    Returns:
        A formatted prompt string for AI hint generation
    """
    common_words_placeholder = "{common_words}"

    hints_section = ""
    diversity_guidance = ""
    if existing_hints:
        formatted_hints = "\n".join(f"- {hint}" for hint in existing_hints)
        word_counts = [len(hint.split()) for hint in existing_hints]
        hints_section = f"""

Existing hints already shared (do NOT repeat or lightly modify these):
{formatted_hints}

Your new hint MUST be substantially different from the above."""

        # Provide specific diversity guidance
        diversity_strategies = [
            "Try using a different word count",
            "Explore a different semantic angle (if previous hints were direct, try metaphorical; if formal, try casual)",
            "Vary the sentence structure or emphasis",
            "Use synonyms for key concepts rather than the same words",
        ]
        diversity_guidance = "\n- ".join(diversity_strategies)
        diversity_guidance = f"\n\nDiversity strategies to consider:\n- {diversity_guidance}"

    base_prompt = f"""You are assisting a player in a word game where they must create a convincing copy of an original phrase.

Original phrase: "{original_phrase}"
Prompt context: "{prompt_text}"

Game rules:
- 1-15 characters per word
- 2-5 words total, 4-100 characters total
- Letters and spaces only (no numbers, punctuation, or symbols)
- Each word must be dictionary-valid
- Avoid reusing long words (4+ letters) from the original phrase unless they are in this allowed common list: [{common_words_placeholder}]

Creative goals:
- Offer a phrase that feels like a natural alternative the original author could plausibly have written
- Make it feel authentic yet distinct from other options
{diversity_guidance}
{hints_section}

Return exactly ONE new hint phrase. Do not add numbering, explanations, or quotation marks."""

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
