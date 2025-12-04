"""Seed ThinkLink prompts from CSV data."""

import asyncio
import logging
import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from backend.config import get_settings
from backend.models.tl import TLPrompt
from backend.services.tl.matching_service import TLMatchingService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


def load_prompts_from_csv() -> list[str]:
    """Load unique prompts from prompt_completions.csv (first column only)."""
    csv_path = Path(__file__).parent / "prompt_completions.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Prompt data file not found at {csv_path}")

    prompts = []
    seen = set()

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            # Skip header row
            next(reader, None)

            for row in reader:
                if row:  # Skip empty rows
                    prompt = row[0].strip()
                    if prompt and prompt not in seen:
                        prompts.append(prompt)
                        seen.add(prompt)

        logger.info(f"Loaded {len(prompts)} unique prompts from CSV")
        return prompts
    except Exception as e:
        logger.error(f"Error reading prompt CSV: {e}")
        raise


async def seed_prompts(db: AsyncSession):
    """Seed ThinkLink prompts from CSV data."""

    # Check if prompts already exist (check count to avoid pgvector deserialization issues)
    from sqlalchemy import func
    stmt = select(func.count(TLPrompt.prompt_id))
    result = await db.execute(stmt)
    count = result.scalar() or 0

    if count > 0:
        logger.info(f"Prompts already exist in database ({count} prompts), skipping seed")
        return

    logger.info("No existing prompts found, seeding from CSV...")

    try:
        # Load prompts from CSV
        prompts = load_prompts_from_csv()

        if not prompts:
            logger.warning("No prompts loaded from CSV")
            return

        # Initialize matching service for embeddings
        matching_service = TLMatchingService()

        created = 0
        skipped = 0

        for prompt_text in prompts:
            try:
                # Check if prompt already exists by text (avoids embedding deserialization)
                stmt = select(func.count(TLPrompt.prompt_id)).where(TLPrompt.text == prompt_text.strip())
                result = await db.execute(stmt)
                if (result.scalar() or 0) > 0:
                    skipped += 1
                    continue

                # Generate embedding
                embedding = await matching_service.generate_embedding(prompt_text)

                # Create prompt
                prompt = TLPrompt(
                    text=prompt_text.strip(),
                    embedding=embedding,
                    is_active=True,
                    ai_seeded=False,  # User-seeded from CSV
                )
                db.add(prompt)
                created += 1

                if created % 50 == 0:
                    logger.info(f"Created {created} prompts so far...")

            except Exception as e:
                logger.warning(f"Failed to seed prompt '{prompt_text[:50]}...': {e}")
                skipped += 1

        await db.commit()
        logger.info(f"✅ Seeding complete: {created} prompts created, {skipped} skipped")

    except Exception as e:
        await db.rollback()
        logger.error(f"❌ Prompt seeding failed: {e}")
        raise


async def main():
    """Main entry point for manual seeding."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed_prompts(session)

    await engine.dispose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
