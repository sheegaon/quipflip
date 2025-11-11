"""Profanity word list for username validation."""

from __future__ import annotations
import re

# List of banned words that cannot appear in usernames
# Words are stored in lowercase for case-insensitive matching
PROFANITY_LIST = [
    # Common profanities
    "fuck", "shit", "ass", "bitch", "damn", "hell", "crap",
    "dick", "cock", "pussy", "cunt", "bastard", "slut", "whore",
    "piss", "fag", "faggot", "dyke", "retard", "nigger", "nigga",
    "twat", "bollocks", "bugger", "wanker", "arsehole", "scum",
    "tosser", "prick", "minger", "numpty", "badass", "douche",
    "jackass",

    # Variations and leetspeak
    "fck", "fuk", "sh1t", "a55", "b1tch", "d1ck", "c0ck",
    "pu55y", "c0nt", "cnt", "b4stard", "p1ss", "f4g", "f4ggot",
    "r3tard", "n1gger", "n1gga", "tw4t",

    # Offensive slurs
    "chink", "spic", "kike", "wetback", "gook", "beaner",
    "towelhead", "raghead", "nazi", "hitler",
    "jihad", "infidel",

    # Sexual content
    "porn", "xxx", "sex", "anal", "penis", "vagina", "tits",
    "boobs", "cum", "jizz", "orgasm", "masturbate", "rape",
    "slutty", "horny", "bdsm", "fetish",

    # Drugs
    "cocaine", "heroin", "meth", "weed", "marijuana", "drugs",
    "lsd", "acid", "ecstasy", "pcp", "crack",
    "opiate", "opioid", "fentanyl", "shrooms", "mdma",

    # Other offensive terms
    "kill", "murder", "suicide", "terrorist", "bomb", "weapon", "assault",
]


def contains_profanity(text: str) -> bool:
    """
    Check if the given text contains any profanity.

    Uses word boundary matching as the primary check, with additional checks
    for common evasion patterns. Prioritizes simplicity and avoiding false
    positives over catching every possible variation.

    Args:
        text: The text to check

    Returns:
        True if profanity is found, False otherwise
    """
    if not text:
        return False

    import re

    # Convert to lowercase for case-insensitive matching
    normalized = text.lower()

    # Remove all non-alphanumeric characters but keep spaces
    cleaned = re.sub(r'[^a-z0-9 ]', '', normalized)

    # Also check version without spaces to catch "f u c k" style evasion
    no_spaces = cleaned.replace(" ", "")

    # Check each banned word
    for word in PROFANITY_LIST:
        # Primary check: word boundaries in the spaced version
        # This handles most cases correctly and avoids false positives
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, cleaned):
            return True

        # Exact match in no-spaces version (catches "f u c k")
        if no_spaces == word:
            return True

        # Check for profanity with digits or at the end of compound words
        # Use finditer to check ALL occurrences, not just the first
        if word in no_spaces:
            for match in re.finditer(re.escape(word), no_spaces):
                idx = match.start()
                word_end = match.end()

                # Check what's before and after
                before_char = no_spaces[idx - 1] if idx > 0 else None
                after_char = no_spaces[word_end] if word_end < len(no_spaces) else None

                at_end = (word_end >= len(no_spaces))
                before_is_digit = (before_char is not None and before_char.isdigit())
                after_is_digit = (after_char is not None and after_char.isdigit())

                # Simple heuristic: flag if at end or adjacent to digits
                # This catches "badass", "fuck123", "123fuck" etc.
                # but avoids "shitake", "classic", "assistant"
                if at_end or before_is_digit or after_is_digit:
                    return True

    return False
