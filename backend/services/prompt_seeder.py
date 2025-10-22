"""Auto-seed prompt library if empty."""
from backend.database import AsyncSessionLocal
from backend.models.prompt import Prompt
from sqlalchemy import select, func, update
import logging

logger = logging.getLogger(__name__)


PROMPTS = [
    # Straightforward (daily life, personal goals, simple emotions)
    ("my deepest desire is to be", "simple"),
    ("success means being", "simple"),
    ("the secret to happiness is", "simple"),
    ("every day I", "simple"),
    ("I feel most alive when I'm", "simple"),
    ("the world needs more", "simple"),
    ("my favorite way to relax is with", "simple"),
    ("a perfect day starts with", "simple"),
    ("I'm most grateful for", "simple"),
    ("my biggest fear is", "simple"),
    ("when I'm stressed, I", "simple"),
    ("the best advice I ever got was", "simple"),
    ("my proudest moment was when I", "simple"),
    ("I laugh the hardest when", "simple"),
    ("my comfort food is", "simple"),
    ("the one thing I can't live without is", "simple"),
    ("on weekends I love to", "simple"),
    ("my guilty pleasure is", "simple"),
    ("I wish I had more time for", "simple"),
    ("the best part of my day is", "simple"),
    ("I feel peaceful when I", "simple"),
    ("my favorite childhood memory involves", "simple"),
    ("the thing that motivates me most is", "simple"),
    ("when I retire, I want to", "simple"),

    # Deep (philosophical, meaningful, introspective)
    ("beauty is fundamentally", "deep"),
    ("the meaning of life is", "deep"),
    ("art should be", "deep"),
    ("freedom means", "deep"),
    ("true wisdom comes from", "deep"),
    ("the essence of friendship is", "deep"),
    ("courage is facing", "deep"),
    ("happiness is ultimately", "deep"),
    ("love is best described as", "deep"),
    ("suffering teaches us about", "deep"),
    ("the purpose of education is to", "deep"),
    ("justice requires", "deep"),
    ("we are defined by our", "deep"),
    ("faith is believing in", "deep"),
    ("mortality reminds us to", "deep"),
    ("compassion begins with", "deep"),
    ("truth is found through", "deep"),
    ("legacy means leaving behind", "deep"),
    ("the human condition is defined by", "deep"),
    ("moral strength comes from", "deep"),
    ("peace is achieved through", "deep"),
    ("identity is shaped by", "deep"),
    ("hope sustains us when we", "deep"),
    ("forgiveness is ultimately about", "deep"),

    # Silly (absurd, humorous, playful nonsense)
    ("the best superpower would be to turn into", "silly"),
    ("if animals could talk, a cat would say", "silly"),
    ("the weirdest invention ever is", "silly"),
    ("my spirit animal is", "silly"),
    ("a zombie's favorite food is", "silly"),
    ("if I were a superhero, my weakness would be", "silly"),
    ("the secret ingredient in magic potions is", "silly"),
    ("aliens probably think humans are", "silly"),
    ("a pirate's worst nightmare is", "silly"),
    ("if dogs ruled the world, they would ban", "silly"),
    ("the strangest thing in my refrigerator is", "silly"),
    ("a vampire's biggest problem is", "silly"),
    ("my imaginary friend is", "silly"),
    ("if trees could move, they would", "silly"),
    ("a unicorn's favorite hobby is", "silly"),
    ("the worst superpower would be", "silly"),
    ("if socks had feelings, they would", "silly"),
    ("a dragon's biggest fear is probably", "silly"),
    ("my evil twin would definitely", "silly"),
    ("if gravity stopped working, I would", "silly"),
    ("a wizard's biggest regret is", "silly"),
    ("the monster under my bed wants", "silly"),
    ("if pizza could talk, it would say", "silly"),
    ("a ninja's biggest embarrassment is", "silly"),

    # Fun/Action (adventures, games, exciting scenarios)
    ("a spy's best gadget is", "fun"),
    ("the ultimate adventure involves", "fun"),
    ("in a fairy tale, the hero always finds", "fun"),
    ("my dream job would be", "fun"),
    ("the key to winning a game is", "fun"),
    ("a robot's daily routine includes", "fun"),
    ("if I could time travel, I'd visit the", "fun"),
    ("the coolest treasure would be", "fun"),
    ("every quest begins with", "fun"),
    ("the ultimate challenge is to", "fun"),
    ("a champion's secret weapon is", "fun"),
    ("the most exciting journey leads to", "fun"),
    ("in a competition, I always", "fun"),
    ("the perfect teammate has", "fun"),
    ("winning requires", "fun"),
    ("the greatest discovery would be finding", "fun"),
    ("every explorer needs", "fun"),
    ("the best strategy is to", "fun"),
    ("a legendary warrior carries", "fun"),
    ("the hidden level contains", "fun"),
    ("the final boss is defeated by", "fun"),
    ("the mystery is solved with", "fun"),
    ("an epic story always includes", "fun"),
    ("the power-up gives you", "fun"),

    # Abstract (conceptual, artistic, sensory, metaphorical)
    ("time feels like", "abstract"),
    ("dreams are made of", "abstract"),
    ("silence can be", "abstract"),
    ("innovation starts with", "abstract"),
    ("the color of joy is", "abstract"),
    ("echoes remind me of", "abstract"),
    ("memory tastes like", "abstract"),
    ("the shape of sadness is", "abstract"),
    ("winter sounds like", "abstract"),
    ("creativity smells like", "abstract"),
    ("the texture of hope is", "abstract"),
    ("music looks like", "abstract"),
    ("tomorrow feels like", "abstract"),
    ("loneliness tastes like", "abstract"),
    ("the weight of words is", "abstract"),
    ("inspiration arrives as", "abstract"),
    ("the rhythm of nature is", "abstract"),
    ("infinity smells like", "abstract"),
    ("the temperature of love is", "abstract"),
    ("chaos sounds like", "abstract"),
    ("the flavor of nostalgia is", "abstract"),
    ("serenity looks like", "abstract"),
    ("the speed of thought is", "abstract"),
    ("wonder feels like", "abstract"),
]


async def sync_prompts_with_database():
    """Synchronize prompts between file and database.

    This runs on application startup and:
    1. Adds any prompts from the file that don't exist in the database
    2. Sets enabled=True for prompts that exist in the file
    3. Sets enabled=False for prompts in database that aren't in the file
    
    Safe to run multiple times - idempotent operation.
    """
    try:
        async with AsyncSessionLocal() as db:
            # Get all existing prompts from database
            result = await db.execute(select(Prompt.text, Prompt.category, Prompt.enabled))
            existing_prompts = {(row.text, row.category): row.enabled for row in result}
            
            # Convert file prompts to set for comparison
            file_prompts = set(PROMPTS)
            
            # Track changes
            added_count = 0
            enabled_count = 0
            disabled_count = 0
            
            # Add missing prompts from file to database
            for text, category in file_prompts:
                if (text, category) not in existing_prompts:
                    prompt = Prompt(
                        text=text,
                        category=category,
                        enabled=True
                    )
                    db.add(prompt)
                    added_count += 1
                    logger.info(f"Adding new prompt: '{text[:50]}...' ({category})")
                elif not existing_prompts[(text, category)]:
                    # Re-enable prompt that was previously disabled
                    await db.execute(
                        update(Prompt)
                        .where(Prompt.text == text, Prompt.category == category)
                        .values(enabled=True)
                    )
                    enabled_count += 1
                    logger.info(f"Re-enabling prompt: '{text[:50]}...' ({category})")
            
            # Disable prompts in database that aren't in file
            for (text, category), currently_enabled in existing_prompts.items():
                if (text, category) not in file_prompts and currently_enabled:
                    await db.execute(
                        update(Prompt)
                        .where(Prompt.text == text, Prompt.category == category)
                        .values(enabled=False)
                    )
                    disabled_count += 1
                    logger.info(f"Disabling prompt: '{text[:50]}...' ({category})")
            
            await db.commit()
            
            # Log summary
            if added_count > 0 or enabled_count > 0 or disabled_count > 0:
                logger.info(f"✓ Prompt sync complete: {added_count} added, {enabled_count} re-enabled, {disabled_count} disabled")
            else:
                logger.info("✓ Prompt library already in sync")
            
            # Show current statistics
            result = await db.execute(
                select(
                    Prompt.category, 
                    func.count(Prompt.prompt_id).label('total'),
                    func.sum(func.cast(Prompt.enabled, func.INTEGER)).label('enabled')
                )
                .group_by(Prompt.category)
                .order_by(Prompt.category)
            )
            
            logger.info("Current prompt library status:")
            total_prompts = 0
            total_enabled = 0
            for category, total, enabled in result:
                enabled = enabled or 0  # Handle None case
                total_prompts += total
                total_enabled += enabled
                logger.info(f"  {category}: {enabled}/{total} enabled")
            logger.info(f"  TOTAL: {total_enabled}/{total_prompts} prompts enabled")

    except Exception as e:
        logger.error(f"Failed to sync prompts: {e}")
        raise
