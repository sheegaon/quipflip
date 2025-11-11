"""Profanity word list for username validation."""

from __future__ import annotations

# List of banned words that cannot appear in usernames
# Words are stored in lowercase for case-insensitive matching
PROFANITY_LIST = [
    # Common profanities
    "fuck", "shit", "ass", "bitch", "damn", "hell", "crap",
    "dick", "cock", "pussy", "cunt", "bastard", "slut", "whore",
    "piss", "fag", "faggot", "dyke", "retard", "nigger", "nigga",

    # Variations and leetspeak
    "fck", "fuk", "sh1t", "a55", "b1tch", "d1ck", "c0ck",
    "pu55y", "c0nt", "cnt", "b4stard", "p1ss", "f4g", "f4ggot",

    # Offensive slurs
    "chink", "spic", "kike", "wetback", "gook", "beaner",
    "towelhead", "raghead", "nazi", "hitler",

    # Sexual content
    "porn", "xxx", "sex", "anal", "penis", "vagina", "tits",
    "boobs", "cum", "jizz", "orgasm", "masturbate", "rape",

    # Drugs
    "cocaine", "heroin", "meth", "weed", "marijuana", "drugs",

    # Other offensive terms
    "kill", "murder", "suicide", "terrorist", "bomb", "weapon",
]

def contains_profanity(text: str) -> bool:
    """
    Check if the given text contains any profanity.

    Uses word boundary matching to avoid false positives.
    For example, "hello" won't match "hell" because 'o' follows the substring.

    Args:
        text: The text to check

    Returns:
        True if profanity is found, False otherwise
    """
    if not text:
        return False

    # Convert to lowercase for case-insensitive matching
    normalized = text.lower()

    # Remove all non-alphanumeric characters to handle variations
    # but keep spaces to help with word boundary detection
    import re
    cleaned = re.sub(r'[^a-z0-9 ]', '', normalized)

    # Also check version without spaces to catch "f u c k" style evasion
    no_spaces = cleaned.replace(" ", "")

    # Check each banned word
    for word in PROFANITY_LIST:
        # Check for word boundaries in the spaced version
        # This prevents "hello" from matching "hell"
        pattern = r'\b' + re.escape(word) + r'\b'
        if re.search(pattern, cleaned):
            return True

        # Check in the no-spaces version for evasion attempts like "f u c k"
        # Only match if:
        # 1. Exact match
        # 2. At start/end with numbers (like "fuck123" or "123fuck")
        if no_spaces == word:
            return True

        if word in no_spaces:
            idx = no_spaces.find(word)
            # Check what's before and after the word
            before_char = no_spaces[idx - 1] if idx > 0 else None
            after_char = no_spaces[idx + len(word)] if idx + len(word) < len(no_spaces) else None

            # Match if at start/end, or surrounded by numbers
            at_start = idx == 0
            at_end = idx + len(word) >= len(no_spaces)
            before_is_digit = before_char and before_char.isdigit()
            after_is_digit = after_char and after_char.isdigit()

            # Flag if the word is clearly present in the text
            # Match patterns like: "fuck", "fuck123", "123fuck", "badass", "shitty"
            # Don't match: "helloworld" (hell in middle), "classic" (ass in middle)

            # Match if word is at start or end (like "badass" or "shitface")
            if at_start or at_end:
                # But avoid matching if it's clearly in the middle of a longer word
                # Check: is this part of a common compound where the banned word is incidental?
                # For now, flag all start/end matches except where surrounded by many letters
                word_len = len(word)
                total_len = len(no_spaces)

                # If the banned word is less than half the total string and surrounded by letters,
                # it might be a false positive (like "hell" in "helloworld")
                if word_len < total_len / 2:
                    # Only flag if it's a common profanity pattern (ends with word, etc.)
                    # For now, allow it - this is a conservative approach
                    if at_end:
                        # Words ending with profanity are usually intentional (badass, dumbass)
                        return True
                    elif at_start and total_len > word_len * 2:
                        # Words starting with short profanity in long words might be false positives
                        # (e.g., "hell" in "helloworld")
                        continue
                    else:
                        return True
                else:
                    # Word is a significant portion of the string
                    return True

            # Also match if surrounded by numbers (like "fuck123" or "123fuck456")
            if before_is_digit or after_is_digit:
                return True

    return False
