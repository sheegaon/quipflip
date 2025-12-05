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
    csv_path = Path(__file__).parent.parent.parent / "data" / "prompt_completions.csv"

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
    """Seed ThinkLink prompts from CSV data, adding any new prompts."""

    logger.info("Checking for new prompts to seed from CSV...")

    try:
        # Load unique prompts from CSV
        prompts_from_csv = load_prompts_from_csv()

        if not prompts_from_csv:
            logger.warning("No prompts to process from CSV file.")
            return

        # Fetch all existing prompt texts from the database
        stmt = select(TLPrompt.text)
        result = await db.execute(stmt)
        existing_prompts = {row[0] for row in result}
        logger.info(f"Found {len(existing_prompts)} existing prompts in the database.")

        # Initialize matching service for embeddings
        matching_service = TLMatchingService()

        created_count = 0
        
        prompts_to_create = []
        for prompt_text in prompts_from_csv:
            if prompt_text not in existing_prompts:
                prompts_to_create.append(prompt_text)
        
        skipped_count = len(prompts_from_csv) - len(prompts_to_create)

        if not prompts_to_create:
            logger.info("No new prompts found in CSV. Database is up to date.")
            return
            
        logger.info(f"Found {len(prompts_to_create)} new prompts to add.")

        for prompt_text in prompts_to_create:
            try:
                embedding = await matching_service.generate_embedding(prompt_text)
                prompt = TLPrompt(
                    text=prompt_text,
                    embedding=embedding,
                    is_active=True,
                    ai_seeded=False,  # User-seeded from CSV
                )
                db.add(prompt)
                created_count += 1

                if created_count > 0 and created_count % 50 == 0:
                    logger.info(f"Prepared {created_count} new prompts for insertion...")

            except Exception as e:
                logger.warning(f"Failed to create embedding for prompt '{prompt_text[:50]}...': {e}")
                # We will skip this prompt and continue with others

        await db.commit()
        logger.info(
            f"✅ Seeding complete: {created_count} new prompts created. {skipped_count} prompts from CSV existed.")

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
