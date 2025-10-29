"""Curated username pool for pseudonymous players."""

from __future__ import annotations

# ---- BASE_USERNAMES (curated one-offs; 2–3 words, thematic, readable) ----
BASE_USERNAMES = [
    "Word Whisperer", "Prompt Pirate", "Copy Cat", "Synonym Sage", "Vibe Matcher",
    "Echo Maker", "Original Flavor", "Bluff Master", "Vote Magnet", "Guess Work",
    "Lexicon Legend", "Hidden Twin", "Meaning Seeker", "Quiet Ruse", "Clever Copy",
    "Prompt Muse", "Echo Hunter", "Secret Original", "Wordsmith Wanderer",
    "Thesaurus Thief", "Silent Signal", "Subtle Twin", "Fluent Faker",
    "Prompt Pilot", "Copy Chameleon", "Voting Brain", "Nuance Ninja",
    "Close Cousin", "True Source", "Masked Meaning", "Honest Guess",
    "Deft Decoy", "Prompt Prophet", "Word Diver", "Semantic Sleuth",
    "Shade Match", "Sound Alike", "Idea Echo", "Native Tongue", "Tight Paraphrase",
    "Vote Whisper", "Clue Follower", "Prompt Whisper", "Signal Finder",
    "Sense Maker", "Secret Synonym", "Copy Whisperer", "Word Pooler",
    "Original Signal", "Guess Maestro", "Prompt Puzzler", "Near Neighbor",
    "Meaning Matcher", "Vote Reader", "Quiet Paraphrase", "True Word",
    "Bluff Detector", "Mirror Meaning", "Prompt Voyage",
    "Quip Flipper", "Quip Scribe", "Quip Sleuth", "Prompt Parrot", "Prompt Pundit",
    "Copy Crafter", "Copy Mimic", "Copy Maven", "Echo Artisan", "Echo Analyst",
    "Signal Sifter", "Signal Whisperer", "Signal Shade", "Clue Crafter", "Clue Weaver",
    "Context Whisperer", "Context Coder", "Context Reader", "Nuance Finder",
    "Nuance Tuner", "Meaning Tinker", "Meaning Miner", "Phrase Forger", "Phrase Phantom",
    "Phrase Smith", "Paraphrase Pro", "Paraphrase Pilot", "Alias Artist", "Analog Adept",
    "Shadow Twin", "Shadow Stylist", "Mirror Twin", "Distant Cousin", "Close Call",
    "Source Sleuth", "Origin Oracle", "Hint Herald", "Hint Hunter", "Tone Matcher",
    "Style Matcher", "Style Shadow", "Word Wrangler", "Lexicon Lancer", "Lexicon Lore",
    "Semantic Scout", "Semantic Stylist", "Syntax Stylist", "Schema Sleuth",
    "Voter Whisper", "Vote Sleuth", "Vote Voyager", "Vote Oracle", "Prompt Pathfinder",
    "Prompt Ranger", "Prompt Cartographer", "Copy Conjurer", "Copy Cartographer",
    "Meaning Mapper", "Meaning Courier", "Idea Cartographer", "Idea Ranger",
    "Context Cartographer", "Echo Cartographer", "Signal Cartographer",
    "Prompt Vanguard", "Echo Sentinel", "Signal Oracle", "Nuance Navigator",
    "Whisper Weaver", "Syntax Spy", "Prompt Marshal", "Whisper Sentinel",
    "Meaning Keeper", "Echo Keeper", "Prompt Keeper", "Idea Ranger",
    "Round Reader", "Round Riddler", "Round Whisperer", "Tie Breaker",
    "False Friend", "True Twin", "Almost Original", "Near Miss", "Dead Ringer",
    "Tell Tale", "Blind Taste", "Cold Read", "Close Read", "Deep Reader",
    "Light Paraphrase", "Soft Copy", "Hard Guess", "Clean Guess", "Quick Paraphrase"
]

# ---- PREFIXES (de-duplicated) ----
PREFIXES = [
    "Word", "Prompt", "Echo", "Vote", "Clue", "Signal", "Meaning", "Lexicon",
    "Nuance", "Context", "Phrase", "Syntax", "Semantic", "Story", "Copy",
    "Shadow", "Mirror", "Insight", "Idea", "Riddle", "Puzzle", "Cipher",
    "Whisper", "Metaphor", "Hint", "Shade", "Voice", "Concept", "Trace",
    "Origin", "Aura", "Pulse", "Frame",
    "Quip", "Source", "Tone", "Style", "Vector", "Pattern", "Thread",
    "Version", "Gesture", "Motive", "Paraphrase", "Analog",
    "Alias", "Sense", "Filter", "Reading", "Marker", "Tag", "Glyph",
    "Accent", "Cadence", "Register", "Echoes", "Primer", "Kernel",
    "Cue", "Spark", "Seed", "Key", "Lead", "Link", "Match", "Twin",
    "Ghost", "Mask", "Mimic", "Forge", "Draft", "Edit", "Shift", "Swap",
    "Twist", "Blend", "Merge", "Mix", "Spin", "Flip",
    "Mood", "Rhythm", "Tempo", "Beat", "Meter", "Flow", "Diction", "Lexis", "Gloss",
    "Intent", "Theme", "Topic", "Lens", "Angle", "Aspect",
    "Schema", "Format", "Template", "Model", "Form", "Mold", "Shell", "Skin",
    "Noise", "Delta", "Drift", "Sample", "Sketch", "Gist",
    "Mark", "Stamp", "Rune", "Handle", "Token", "Toggle", "Probe", "Query", "Poll",
    "Judge", "Guess", "Bet", "Tell", "Read", "Knack",
]

# ---- SUFFIXES (de-duplicated) ----
SUFFIXES = [
    "Voyager", "Ranger", "Scout", "Pioneer", "Navigator", "Pathfinder", "Seeker",
    "Watcher", "Keeper", "Tracker", "Sleuth", "Sentinel", "Guardian", "Herald",
    "Courier", "Pilot", "Captain", "Tracer", "Explorer", "Runner", "Wanderer",
    "Weaver", "Mapper", "Surveyor", "Cartographer", "Warden", "Marshal", "Oracle",
    "Harbor", "Harbinger", "Detective", "Agent", "Delegate",
    "Reader", "Matcher", "Analyst", "Architect", "Artisan", "Binder", "Broker",
    "Calibrator", "Caster", "Chaser", "Cipher", "Crafter", "Decoder", "Finder",
    "Forger", "Gleaner", "Grader", "Guesser", "Harvester", "Liaison",
    "Referee", "Resolver", "Reviser", "Sampler", "Shaper", "Spotter",
    "Tuner", "Weigher", "Maker", "Smith", "Molder", "Spinner", "Mixer", "Blender",
    "Twister", "Shifter", "Switcher", "Swapper", "Editor", "Redactor", "Rewriter", "Stylizer",
    "Chooser", "Picker", "Voter", "Judge", "Juror", "Arbiter", "Umpire",
    "Sifter", "Sorter", "Ranker", "Scorer", "Rater",
    "Refiner", "Polisher", "Aligner", "Joiner", "Linker", "Bridger",
    "Mimic", "Cloner", "Copyist", "Parrot", "Repeater", "Comparer", "Decider",
    "Sage", "Ninja", "Wizard", "Guru", "Maestro", "Ace", "Pro", "Buff", "Fan",
]


# ---- THREE_WORD_SUFFIXES (expanded & de-duplicated) ----
THREE_WORD_SUFFIXES = [
    "Trail Guide", "Signal Guide", "Echo Guide", "Round Scout", "Word Guide",
    "Vector Scout", "Pattern Seeker", "Prompt Guide", "Prompt Runner",
    "Meaning Guide", "Signal Runner", "Idea Scout", "Syntax Runner",
    "Signal Watch", "Echo Watch", "Whisper Guide", "Clue Guide",
    "Vote Guide", "Prompt Watch", "Copy Guide", "Copy Runner", "Voter Scout",
    "Phrase Scout", "Style Scout", "Tone Scout", "Context Guide", "Nuance Guide",
    "Clue Runner", "Idea Runner", "Meaning Watch", "Echo Runner", "Word Watch",
    "Prompt Scout", "Signal Scout", "Quip Guide", "Quip Runner", "Quip Watch",
    "Trail Watch", "Trail Scout", "Trail Runner", "Trail Finder", "Trail Seeker",
    "Signal Seeker", "Signal Finder", "Signal Reader", "Echo Seeker", "Echo Finder", "Echo Reader",
    "Prompt Seeker", "Prompt Finder", "Prompt Reader",
    "Copy Scout", "Copy Watch", "Copy Seeker", "Copy Finder", "Copy Reader",
    "Voter Guide", "Voter Watch", "Voter Runner", "Voter Finder", "Voter Reader",
    "Vote Runner", "Vote Seeker", "Vote Finder", "Vote Reader",
    "Clue Scout", "Clue Watch", "Clue Finder", "Clue Seeker", "Clue Reader",
    "Phrase Guide", "Phrase Watch", "Phrase Runner", "Phrase Finder",
    "Style Guide", "Style Watch", "Style Reader", "Tone Guide", "Tone Watch", "Tone Reader",
    "Context Scout", "Context Watch", "Context Runner", "Context Finder",
    "Nuance Scout", "Nuance Watch", "Nuance Reader", "Nuance Runner",
    "Syntax Guide", "Syntax Scout", "Syntax Watch", "Syntax Finder",
    "Vector Guide", "Vector Runner", "Pattern Guide", "Pattern Runner", "Pattern Watch",
    "Quip Scout", "Quip Finder", "Word Scout", "Word Runner", "Word Finder",
    "Idea Guide", "Idea Watch", "Idea Reader", "Idea Finder", "Meaning Reader", "Meaning Finder",
]


def _normalize(name: str) -> str:
    """Collapse extra whitespace and ensure consistent spacing."""
    return " ".join(name.split())


def _build_username_pool() -> list[str]:
    """Construct a deterministic list of themed usernames."""
    seen: set[str] = set()
    pool: list[str] = []

    def add(name: str) -> None:
        normalized = _normalize(name)
        if not normalized or normalized in seen or len(normalized) > 28:
            return
        seen.add(normalized)
        pool.append(normalized)

    for name in BASE_USERNAMES:
        add(name)

    for prefix in PREFIXES:
        for suffix in SUFFIXES:
            add(f"{prefix} {suffix}")

    for prefix in PREFIXES:
        for suffix in THREE_WORD_SUFFIXES:
            if prefix not in suffix:
                add(f"{prefix} {suffix}")

    return pool


USERNAME_POOL = _build_username_pool()
