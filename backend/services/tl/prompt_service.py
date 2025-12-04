"""ThinkLink prompt service.

Manages prompt corpus, seeding, and selection for rounds.
"""
import logging
import random
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from backend.models.tl import TLPrompt, TLAnswer
from backend.services.tl.matching_service import TLMatchingService

logger = logging.getLogger(__name__)


class TLPromptService:
    """Service for prompt management and selection."""

    def __init__(self, matching_service: TLMatchingService | None = None):
        """Initialize prompt service.

        Args:
            matching_service: MatchingService for embedding generation
        """
        self.matching = matching_service or TLMatchingService()

    async def get_random_active_prompt(
        self,
        db: AsyncSession,
    ) -> Optional[TLPrompt]:
        """Select a random active prompt (weighted by corpus size).

        Prefer prompts with fuller answer corpus for better semantic space.

        Args:
            db: Database session

        Returns:
            TLPrompt or None if no active prompts available
        """
        from sqlalchemy.orm import load_only

        try:
            logger.info("🎲 Selecting random active prompt...")

            # Get all active prompts with answer counts
            # Use load_only to avoid loading embedding column (pgvector deserialization issue)
            result = await db.execute(
                select(TLPrompt, func.count(TLAnswer.answer_id).label('answer_count'))
                .options(load_only(TLPrompt.prompt_id, TLPrompt.text, TLPrompt.is_active, TLPrompt.ai_seeded, TLPrompt.created_at))
                .outerjoin(TLAnswer)
                .where(TLPrompt.is_active == True)
                .group_by(TLPrompt.prompt_id)
            )
            rows = result.all()

            if not rows:
                logger.warning("⚠️  No active prompts available")
                return None

            # Extract prompts and answer counts
            prompts_with_counts = [(row[0], row[1]) for row in rows]

            # Weighted selection by answer count (prefer fuller corpuses)
            prompts = [p for p, _ in prompts_with_counts]
            weights = [count for _, count in prompts_with_counts]
            # Ensure weights are positive (use 1 as minimum to allow selection)
            weights = [max(1, w) for w in weights]
            selected_prompt = random.choices(prompts, weights=weights, k=1)[0]
            logger.info(
                f"✅ Selected prompt: '{selected_prompt.text[:50]}...' "
                f"(id={selected_prompt.prompt_id})"
            )
            return selected_prompt
        except Exception as e:
            logger.error(f"❌ Prompt selection failed: {e}")
            return None

    async def seed_prompts_from_list(
        self,
        db: AsyncSession,
        prompt_texts: List[str],
    ) -> Tuple[int, int]:
        """Seed prompts from a list of text strings.

        Args:
            db: Database session
            prompt_texts: List of prompt text strings

        Returns:
            (created_count, skipped_count)
        """
        try:
            logger.info(f"🌱 Seeding {len(prompt_texts)} prompts...")

            created = 0
            skipped = 0

            for text in prompt_texts:
                try:
                    # Check if prompt already exists
                    result = await db.execute(
                        select(TLPrompt).where(TLPrompt.text == text.strip())
                    )
                    existing = result.scalars().first()

                    if existing:
                        logger.debug(f"⏭️  Skipping existing prompt: '{text[:50]}...'")
                        skipped += 1
                        continue

                    # Generate embedding for on-topic validation
                    embedding = await self.matching.generate_embedding(text)

                    # Create prompt
                    prompt = TLPrompt(
                        text=text.strip(),
                        embedding=embedding,
                        is_active=True,
                        ai_seeded=False,
                    )
                    db.add(prompt)
                    created += 1
                    logger.debug(f"✅ Created prompt: '{text[:50]}...'")

                except Exception as e:
                    logger.warning(f"⚠️  Failed to seed prompt '{text[:50]}...': {e}")
                    skipped += 1

            await db.flush()
            logger.debug(f"✅ Seeding complete: {created} created, {skipped} skipped")
            return created, skipped
        except Exception as e:
            logger.error(f"❌ Prompt seeding failed: {e}")
            return 0, len(prompt_texts)

    async def count_active_prompts(
        self,
        db: AsyncSession,
    ) -> int:
        """Get count of active prompts.

        Args:
            db: Database session

        Returns:
            Number of active prompts
        """
        try:
            result = await db.execute(
                select(func.count(TLPrompt.prompt_id)).where(TLPrompt.is_active == True)
            )
            count = result.scalar() or 0
            return count
        except Exception as e:
            logger.error(f"❌ Count active prompts failed: {e}")
            return 0

    async def get_prompt_by_id(
        self,
        db: AsyncSession,
        prompt_id: str,
    ) -> Optional[TLPrompt]:
        """Get a prompt by ID.

        Args:
            db: Database session
            prompt_id: Prompt ID

        Returns:
            TLPrompt or None
        """
        from sqlalchemy.orm import load_only

        try:
            # Use load_only to avoid loading embedding column (pgvector deserialization issue)
            result = await db.execute(
                select(TLPrompt)
                .options(load_only(TLPrompt.prompt_id, TLPrompt.text, TLPrompt.is_active, TLPrompt.ai_seeded, TLPrompt.created_at))
                .where(TLPrompt.prompt_id == prompt_id)
            )
            return result.scalars().first()
        except Exception as e:
            logger.error(f"❌ Get prompt failed: {e}")
            return None

    async def get_active_answers_for_prompt(
        self,
        db: AsyncSession,
        prompt_id: str,
        limit: int = 1000,
    ) -> List[TLAnswer]:
        """Get active answers for a prompt (for snapshot building).

        Args:
            db: Database session
            prompt_id: Prompt ID
            limit: Maximum answers to return (corpus cap)

        Returns:
            List of TLAnswer objects
        """
        try:
            result = await db.execute(
                select(TLAnswer)
                .where(
                    TLAnswer.prompt_id == prompt_id,
                    TLAnswer.is_active == True
                )
                .limit(limit)
            )
            answers = result.scalars().all()
            logger.debug(
                f"📊 Retrieved {len(answers)} active answers for prompt {prompt_id}"
            )
            return answers
        except Exception as e:
            logger.error(f"❌ Get active answers failed: {e}")
            return []
