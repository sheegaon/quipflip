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
    base_prompt = f"""Create 5 phrases meaning roughly the same thing as the original phrase.

**Original phrase: "{original_phrase}"**
""" + """
Rules:
- 1-15 characters per word
- 2-5 words per phrase, 4-100 characters per phrase
- Letters and spaces only
- Each word must pass dictionary validation
- Each phrase should be similar enough to be believable as the original
- Words which are 4 or more letters long, except common words: [{common_words}], are known as *significant words*
- Do NOT use the same significant word in more than two phrases"""

    if existing_copy_phrase:
        base_prompt += f"""
- **IMPORTANT: Another player already submitted this copy: "{existing_copy_phrase}"**"""
        base_prompt += """
- Do NOT use or lightly modify (e.g., pluralize) any significant words from either the original phrase or 
  the submitted copy phrase"""
    else:
        base_prompt += """
- Do NOT use or lightly modify (e.g., pluralize) any significant words from the original phrase"""

    base_prompt += f"""

Generate FIVE alternative phrases, separated by semicolons (;):"""

    return base_prompt


def build_vote_prompt(prompt_text: str, phrases: list[str], seed: int) -> str:
    """
    Build structured prompt for AI vote generation.

    Args:
        prompt_text: The prompt that the phrases were created for
        phrases: List of 3 phrases (1 original, 2 copies)
        seed: Seed for randomization to ensure consistent output

    Returns:
        A formatted prompt string for AI vote generation
    """
    random.seed(seed)
    phrases_formatted = "\n".join([f"{i+1}. {phrase}" for i, phrase in enumerate(phrases)])
    considerations = [
        "- The original is often more natural and straightforward",
        "- Copies may try too hard or be slightly awkward",
        "- The original usually best matches the prompt intent",
        "- Look for subtle differences in word choice and phrasing",
        "- Consider the length and complexity of each phrase",
        "- Each copy may be riffing off a different idea from the original",
    ]
    chosen_considerations = list(set(random.sample(considerations, 4)))  # Shuffle considerations for variety
    chosen_considerations = ''.join([f"\n{c}" for c in chosen_considerations])

    return f"""You are playing a game where you need to identify the original phrase.
Given a prompt and three phrases, one phrase is the ORIGINAL that was submitted by a player, and two phrases are FAKES
created by other players trying to mimic the original without knowing the prompt.

Your task: Identify which phrase is most likely the ORIGINAL.

Prompt: "{prompt_text}"

Consider:{chosen_considerations}

Phrases:
{phrases_formatted}

Respond with ONLY the number (1, 2, or 3) of the phrase you believe is the original."""


def build_backronym_prompt(word: str, count: int = 5) -> str:
    """
    Build structured prompt for Initial Reaction backronym generation.

    Args:
        word: The target word (e.g., "FROG", "CAT")
        count: Number of backronym options to generate (default: 5)

    Returns:
        A formatted prompt string for AI backronym generation
    """
    word_upper = word.upper()
    letter_count = len(word_upper)

    prompt = f"""Generate clever, funny backronyms for the word: {word_upper}

A backronym is an acronym where each letter of the word starts a different word to create a phrase or sentence.

For example:
- FROG = "Frequently Roaming Over Green"
- CAT = "Curious Adventure Traveler"

Rules:
- Generate exactly {count} backronym options
- Each option must have exactly {letter_count} words (one word per letter)
- Each word should be 2-15 characters (letters only, A-Z)
- Backronyms should be funny, clever, or meaningful
- Each word must be a valid English dictionary word
- Format: comma-separated list of backronym options, each option with words separated by spaces

Example format:
First Option, Second Option, Third Option

Generate {count} unique backronym options for {word_upper}:"""

    return prompt


def build_party_prompt_generation(prompt_text: str) -> str:
    """
    Build structured prompt for Party Mode prompt round phrase generation.

    Args:
        prompt_text: The prompt to respond to

    Returns:
        A formatted prompt string for AI phrase generation
    """
    return f"""Generate a creative, short phrase that responds to the following prompt.

**Prompt: "{prompt_text}"**
""" + """
Rules:
- 1-15 characters per word
- 2-5 words, 4-100 characters in total
- Letters and spaces only
- Each word must pass dictionary validation
- Make it clever, funny, or creative
- Should directly complete the prompt sentence
- Words which are 4 or more letters long, except common words: [{common_words}], are known as *significant words*
- Do NOT use or lightly modify (e.g., pluralize) any significant words from the prompt

Generate ONE phrase that best responds to the prompt. Do not include quotes or explanation, just the phrase itself."""


def build_backronym_vote_prompt(word: str, backronyms: list[str]) -> str:
    """
    Build structured prompt for AI vote generation in Initial Reaction.

    Args:
        word: The target word
        backronyms: List of backronym options (already formatted as word arrays)

    Returns:
        A formatted prompt string for AI voting on backronyms
    """
    word_upper = word.upper()
    backronyms_formatted = "\n".join(
        [f"{i+1}. {' '.join(b) if isinstance(b, list) else b}" for i, b in enumerate(backronyms)]
    )

    considerations = [
        "- Which backronym is the most creative or clever?",
        "- Which one is the funniest?",
        "- Which one flows most naturally when spoken?",
        "- Which one best captures the essence of the word?",
        "- Which one is most memorable?",
    ]
    chosen_considerations = random.sample(considerations, k=2)
    chosen_considerations = ''.join([f"\n{c}" for c in chosen_considerations])

    return f"""You are playing Initial Reaction, a word game where players create backronyms.

A backronym for a word is an acronym where each letter starts a word to create a phrase.

Your task: Choose the BEST (most creative, funny, or clever) backronym for the word {word_upper}.

Consider:{chosen_considerations}

Backronym options:
{backronyms_formatted}

Respond with ONLY the number (1, 2, 3, 4, or 5) of the best backronym."""
