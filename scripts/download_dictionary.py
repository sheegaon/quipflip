"""
Download OWL2 Word List.

For MVP, we'll use a sample dictionary. In production, download from:
https://github.com/scrabblewords/scrabblewords/blob/main/words/North-American/OWL2-Playability.txt
or similar source.
"""
import os


def create_sample_dictionary():
    """Create a sample dictionary for development."""
    # Sample words for testing (in production, download full OWL2 list)
    sample_words = [
        # Common words
        "HELLO", "WORLD", "FAMOUS", "POPULAR", "WEALTHY", "HAPPY", "SAD",
        "LOVE", "HATE", "GOOD", "BAD", "BIG", "SMALL", "FAST", "SLOW",
        "HOT", "COLD", "NEW", "OLD", "HIGH", "LOW", "LONG", "SHORT",
        "EASY", "HARD", "RICH", "POOR", "YOUNG", "WISE", "STRONG", "WEAK",
        # Test words from docs
        "ACTOR", "EXPLORER", "CONTENTMENT", "ADVENTURE", "KINDNESS",
        "INNOVATION", "COMPASSION", "LAUGHTER", "COFFEE", "SUNRISE",
        "EXERCISE", "SILENCE", "BOOK", "MUSIC", "WALK", "FRIEND",
        # Game-related
        "PANCAKE", "INVISIBLE", "FLYING", "TALKING", "FEED", "NAP",
        "WORSHIP", "SCRATCH", "TOASTER", "UMBRELLA", "ROBOT", "HAT",
        "SLOTH", "EAGLE", "UNICORN", "POTATO", "BRAINS", "PIZZA",
        "CANDY", "SALAD", "KRYPTONITE", "CHOCOLATE", "TICKLES",
        "FROG", "SPARKLE", "SALT", "WEIRD", "NOISY", "CUTE", "DELICIOUS",
        # More common words
        "THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN",
        "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM",
        "HOW", "ITS", "MAY", "NEW", "NOW", "ONLY", "SEE", "TIME", "TWO",
        "WAY", "WHO", "OIL", "USE", "WORD", "THAN", "CALL", "FIND",
        "GIVE", "HAND", "KIND", "LAST", "MADE", "MAKE", "MANY", "MOST",
        "NAME", "OVER", "PART", "PLACE", "SAME", "TELL", "THAT", "THEM",
        "THEN", "THESE", "THIS", "TURN", "VERY", "WANT", "WELL", "WHAT",
        "WHEN", "WITH", "WORK", "YEAR", "ABOUT", "AFTER", "AGAIN",
        "BECAUSE", "BEFORE", "COULD", "EVERY", "FIRST", "FOUND",
        "GREAT", "HOUSE", "LARGE", "LATER", "LEARN", "LEAVE", "LIVE",
        "NEVER", "OTHER", "PEOPLE", "PLACE", "POINT", "RIGHT", "SEEMS",
        "SHOULD", "SMALL", "SOUND", "STILL", "STUDY", "THEIR", "THERE",
        "THESE", "THING", "THINK", "THREE", "THROUGH", "UNDER", "UNTIL",
        "WHERE", "WHICH", "WHILE", "WRITE", "WOULD", "YEARS",
    ]

    # Create data directory
    data_dir = os.path.join(os.path.dirname(__file__), "../phrase_validation_worker/data")
    os.makedirs(data_dir, exist_ok=True)

    # Write to file
    output_path = os.path.join(data_dir, "dictionary.txt")
    with open(output_path, "w") as f:
        for word in sorted(set(sample_words)):
            f.write(f"{word.upper()}\n")

    print(f"Created sample dictionary with {len(set(sample_words))} words at: {output_path}")
    print("NOTE: This is a sample dictionary. In production, download the full word list.")


if __name__ == "__main__":
    create_sample_dictionary()
