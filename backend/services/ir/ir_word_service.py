"""IR Word Service - Random word generation for backronym sets."""

import logging
import random
from datetime import datetime, UTC, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import get_settings
from backend.models.ir.ir_ai_phrase_cache import IRAIPhraseCache

logger = logging.getLogger(__name__)


class IRWordError(RuntimeError):
    """Raised when word service fails."""


class IRWordService:
    """Service for generating and caching random words for backronym sets."""

    # Common 3-5 letter words (curated for backronym fun)
    # This can be expanded or loaded from a dictionary file
    WORD_LIST = [
        # 3-letter words
        "CAT", "DOG", "BAT", "RAT", "HAT", "MAT", "SAT", "FAT", "PAT", "LAT",
        "BIT", "HIT", "SIT", "PIT", "WIT", "FIT", "KIT", "LIT",
        "BOX", "FOX", "SOX", "POX",
        "BUS", "PUS", "MUS",
        "COP", "HOP", "MOP", "TOP", "POP", "SOP",
        "ART", "OAR", "OAT", "EAR", "ERA", "ORE",
        "AIR", "ARM", "ARC", "ARK", "ARK",
        "BAN", "CAN", "FAN", "MAN", "PAN", "RAN", "TAN", "VAN", "WAN",
        "BED", "FED", "LED", "RED", "WED",
        "BIG", "DIG", "FIG", "GIG", "JIG", "PIG", "RIG", "WIG",
        "BUN", "DUN", "FUN", "GUN", "NUN", "PUN", "RUN", "SUN",
        "CUP", "PUP", "SUP",
        "CUT", "GUT", "HUT", "JUT", "NUT", "PUT", "RUT", "TUT",
        "DAM", "HAM", "JAM", "RAM", "YAM",
        "DAY", "GAY", "HAY", "JAY", "LAY", "MAY", "PAY", "RAY", "SAY", "WAY",
        # 4-letter words
        "ABLE", "BACK", "BALL", "BAND", "BANK", "BASE", "BATH", "BEAD",
        "BEAM", "BEAN", "BEAR", "BEAT", "BEEN", "BELL", "BELT", "BEND",
        "BENT", "BEST", "BIKE", "BILL", "BIND", "BIRD", "BITE", "BLOW",
        "BLUE", "BOAT", "BODY", "BOIL", "BOLT", "BOMB", "BOND", "BONE",
        "BOOK", "BOOT", "BORE", "BORN", "BOSS", "BOTH", "BOWL", "BURN",
        "BUSH", "BUSY", "BUZZ", "CAGE", "CAKE", "CALF", "CALL", "CALM",
        "CAME", "CAMP", "CANE", "CARE", "CARD", "CARE", "CART", "CASE",
        "CASH", "CAST", "CAVE", "CENT", "CHAT", "CHOP", "CITY", "CLAY",
        "CLIP", "CLUB", "COAL", "COAT", "CODE", "COLD", "COME", "CONE",
        "COOK", "COOL", "COPE", "COPY", "CORD", "CORE", "CORK", "CORN",
        "COST", "COZY", "CRAB", "CREW", "CROP", "CROW", "CUBE", "CURB",
        "CURE", "CURL", "CUTE", "DAMP", "DARE", "DARK", "DASH", "DATE",
        "DAWN", "DEAD", "DEAF", "DEAL", "DEAR", "DECK", "DEEP", "DENT",
        "DESK", "DIAL", "DIET", "DIME", "DINE", "DIRE", "DIRT", "DISH",
        "DIVE", "DOCK", "DOES", "DOME", "DONE", "DOOR", "DOSE", "DOWN",
        "DRAB", "DRAG", "DAMP", "DRAW", "DREAD", "DREAM", "DRESS", "DREW",
        "DRIP", "DROP", "DRUG", "DRUM", "DUCK", "DULL", "DUMB", "DUMP",
        "DUNE", "DUNK", "DUSK", "DUTY", "DYED", "DYER", "EACH", "EARL",
        "EARN", "EASE", "EAST", "EASY", "ECHO", "EDGE", "EDIT", "ELSE",
        # 5-letter words
        "ABOUT", "ABUSE", "ADAPT", "ADMIT", "ADOPT", "ADULT", "AFTER",
        "AGAIN", "AGENT", "AGREE", "AHEAD", "ALARM", "ALBUM", "ALERT",
        "ALIEN", "ALIGN", "ALIKE", "ALIVE", "ALLOW", "ALONE", "ALONG",
        "ALTER", "ANGEL", "ANGER", "ANGLE", "ANGRY", "APART", "APPLE",
        "APPLY", "ARENA", "ARGUE", "ARISE", "ARMOR", "AROMA", "AROSE",
        "ARRAY", "ARROW", "ASIDE", "ASSET", "ATLAS", "AUDIO", "AUDIT",
        "AVOID", "AWAKE", "AWARD", "AWARE", "BADLY", "BAGEL", "BAKER",
        "BASIN", "BASIS", "BEACH", "BEARD", "BEAST", "BEIGE", "BEING",
        "BELLY", "BELOW", "BENCH", "BERRY", "BIRTH", "BLACK", "BLADE",
        "BLAME", "BLANK", "BLAST", "BLAZE", "BLEAK", "BLEED", "BLEND",
        "BLESS", "BLIND", "BLINK", "BLISS", "BLOCK", "BLOOD", "BLOOM",
        "BLOWN", "BOARD", "BOAST", "BOOST", "BOOTH", "BOUND", "BRAIN",
        "BRAKE", "BRAND", "BRASS", "BRAVE", "BREAD", "BREAK", "BREED",
        "BRICK", "BRIDE", "BRIEF", "BRING", "BRINK", "BRISK", "BROAD",
        "BROKE", "BROOK", "BROOM", "BROWN", "BUILD", "BUILT", "BURST",
        "BUYER", "CABLE", "CALIF", "CAMEL", "CANAL", "CANDY", "CANOE",
        "CARGO", "CARRY", "CARVE", "CATCH", "CASTE", "CAUSE", "CEDAR",
        "CHAIN", "CHAIR", "CHALK", "CHAMP", "CHANT", "CHAOS", "CHARM",
        "CHART", "CHASE", "CHEAP", "CHEAT", "CHECK", "CHEEK", "CHEER",
        "CHESS", "CHEST", "CHEW", "CHICK", "CHIEF", "CHILD", "CHILL",
        "CHIMNEY", "CHINA", "CHOIR", "CHORD", "CHORE", "CHOSE", "CHUNK",
    ]

    def __init__(self, db: AsyncSession):
        """Initialize IR word service.

        Args:
            db: Database session
        """
        self.db = db
        self.settings = get_settings()
        self._word_cache = None
        self._last_word = None
        self._last_word_time = None

    async def get_random_word(self) -> str:
        """Get a random word for a backronym set.

        Words are cached to avoid near-duplicates in short timeframes.

        Returns:
            str: A random 3-5 letter word

        Raises:
            IRWordError: If word generation fails
        """
        try:
            # Avoid getting same word twice in quick succession
            current_time = datetime.now(UTC)
            if (
                self._last_word
                and self._last_word_time
                and (current_time - self._last_word_time) < timedelta(seconds=10)
            ):
                # Return different word from recent picks
                word = random.choice(self.WORD_LIST)
                while word == self._last_word:
                    word = random.choice(self.WORD_LIST)
            else:
                word = random.choice(self.WORD_LIST)

            self._last_word = word
            self._last_word_time = current_time

            logger.debug(f"Generated random word: {word}")
            return word

        except Exception as e:
            raise IRWordError(f"Failed to generate random word: {str(e)}") from e

    async def is_word_recently_used(self, word: str, minutes: int = 30) -> bool:
        """Check if word has been used recently.

        Args:
            word: Word to check
            minutes: Look back window in minutes

        Returns:
            bool: True if word was used recently
        """
        try:
            lookback_time = datetime.now(UTC) - timedelta(minutes=minutes)
            stmt = select(IRAIPhraseCache).where(
                (IRAIPhraseCache.word == word.upper())
                & (IRAIPhraseCache.created_at >= lookback_time)
            )
            result = await self.db.execute(stmt)
            return result.scalars().first() is not None

        except Exception as e:
            logger.warning(f"Error checking recent word usage: {e}")
            return False

    async def cache_word_usage(self, word: str) -> None:
        """Cache word usage for duplicate prevention.

        Args:
            word: Word to cache
        """
        try:
            # Just record in AI phrase cache (can reuse for word tracking)
            cache_entry = IRAIPhraseCache(
                word=word.upper(),
                generated_phrases=[],
                created_at=datetime.now(UTC),
            )
            self.db.add(cache_entry)
            await self.db.commit()
        except Exception as e:
            logger.warning(f"Error caching word usage: {e}")
            await self.db.rollback()
