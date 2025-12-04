"""Seed ThinkLink answers from CSV completions.

Seeds the phrase_1 through phrase_10 columns as answers for each prompt.
"""

import asyncio
import logging
import csv
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, func

from backend.config import get_settings
from backend.models.tl import TLPrompt, TLAnswer
from backend.services.tl.matching_service import TLMatchingService
from backend.services.tl.clustering_service import TLClusteringService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()


def load_completions_from_csv() -> dict[str, list[str]]:
    """Load prompt -> completions mapping from prompt_completions.csv."""
    csv_path = Path(__file__).parent / "prompt_completions.csv"

    if not csv_path.exists():
        raise FileNotFoundError(f"Prompt data file not found at {csv_path}")

    completions_map = {}

    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for row in reader:
                prompt = row['prompt'].strip()
                if not prompt:
                    continue

                # Collect all phrase columns
                completions = []
                for i in range(1, 11):
                    phrase_key = f'phrase_{i}'
                    if phrase_key in row and row[phrase_key].strip():
                        completions.append(row[phrase_key].strip())

                if completions:
                    completions_map[prompt] = completions

        logger.info(f"Loaded completions for {len(completions_map)} prompts from CSV")
        return completions_map
    except Exception as e:
        logger.error(f"Error reading prompt CSV: {e}")
        raise


async def seed_answers(db: AsyncSession, force: bool = False):
    """Seed ThinkLink answers from CSV completions.

    Runs on every startup to add any new completions from the CSV.
    Skips answers that already exist (by prompt_id + text).

    Args:
        db: Database session
        force: If True, re-generate embeddings for existing answers (not typically needed)
    """
    logger.info("Checking for new ThinkLink answers to seed from CSV...")

    try:
        # Load completions
        completions_map = load_completions_from_csv()

        if not completions_map:
            logger.warning("No completions loaded from CSV")
            return

        # Initialize services
        matching_service = TLMatchingService()
        clustering_service = TLClusteringService(matching_service)

        created = 0
        skipped = 0

        for prompt_text, completions in completions_map.items():
            # Find the prompt in database
            result = await db.execute(
                select(TLPrompt).where(TLPrompt.text == prompt_text)
            )
            prompt = result.scalars().first()

            if not prompt:
                logger.debug(f"Prompt not found: '{prompt_text[:50]}...', skipping completions")
                skipped += len(completions)
                continue

            prompt_id = str(prompt.prompt_id)

            for completion_text in completions:
                try:
                    # Check if answer already exists
                    result = await db.execute(
                        select(func.count(TLAnswer.answer_id)).where(
                            TLAnswer.prompt_id == prompt_id,
                            TLAnswer.text == completion_text
                        )
                    )
                    if (result.scalar() or 0) > 0:
                        skipped += 1
                        continue

                    # Generate embedding
                    embedding = await matching_service.generate_embedding(completion_text)

                    # Create answer
                    answer = TLAnswer(
                        prompt_id=prompt_id,
                        text=completion_text,
                        embedding=embedding,
                        is_active=True,
                        answer_players_count=1,  # Start with 1 to give some weight
                    )
                    db.add(answer)
                    await db.flush()

                    # Assign to cluster
                    cluster_id = await clustering_service.assign_cluster(
                        db,
                        prompt_id,
                        embedding,
                        str(answer.answer_id),
                    )
                    answer.cluster_id = cluster_id
                    await db.flush()

                    created += 1

                    if created % 50 == 0:
                        logger.info(f"Created {created} answers so far...")

                except Exception as e:
                    logger.warning(f"Failed to seed answer '{completion_text[:30]}...': {e}")
                    skipped += 1

        await db.commit()
        if created > 0:
            logger.info(f"ThinkLink answer seeding complete: {created} new answers created, {skipped} already existed")
        else:
            logger.info(f"ThinkLink answers already up to date ({skipped} answers exist)")

    except Exception as e:
        await db.rollback()
        logger.error(f"Answer seeding failed: {e}")
        raise


async def main():
    """Main entry point for manual seeding."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed_answers(session, force=False)

    await engine.dispose()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
