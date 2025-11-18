from uuid import UUID
import logging
from sqlalchemy.exc import SQLAlchemyError

from backend.models.qf.round import Round

logger = logging.getLogger(__name__)


async def generate_ai_copies_background(prompt_round_id: UUID) -> None:
    """Generate AI copies without blocking the prompt submission response."""

    from backend.database import AsyncSessionLocal
    from backend.services import AIService, AICopyError
    from backend.utils import lock_client

    # Use distributed lock to prevent duplicate AI generation for the same prompt
    lock_name = f"ai_copy_generation:{prompt_round_id}"
    
    try:
        with lock_client.lock(lock_name, timeout=30):
            async with AsyncSessionLocal() as background_db:
                ai_service = AIService(background_db)

                try:
                    prompt_round = await background_db.get(Round, prompt_round_id)
                    if not prompt_round:
                        logger.warning(f"Prompt round {prompt_round_id} not found for background AI copy generation")
                        return

                    # Check if AI copies have already been generated for this prompt
                    from backend.models.qf.ai_phrase_cache import QFAIPhraseCache
                    from sqlalchemy import select
                    
                    result = await background_db.execute(
                        select(QFAIPhraseCache)
                        .where(QFAIPhraseCache.prompt_round_id == prompt_round_id)
                    )
                    existing_cache = result.scalar_one_or_none()
                    
                    if existing_cache:
                        logger.info(f"AI copies already generated for prompt round {prompt_round_id}, skipping")
                        return

                    await ai_service.generate_and_cache_phrases(prompt_round)
                    logger.info(f"Generated and cached AI copies for prompt round {prompt_round_id} (background)")
                except AICopyError as exc:
                    logger.warning(f"Failed to generate AI copies for prompt round {prompt_round_id}: {exc}",
                                   exc_info=True)
                except SQLAlchemyError as exc:
                    await background_db.rollback()
                    logger.warning(f"Database error while caching AI copies for prompt round {prompt_round_id}: {exc}",
                                   exc_info=True)
                except Exception as exc:  # Catch-all to avoid unhandled background task errors
                    logger.warning(
                        f"Unexpected error during AI copy generation for prompt round {prompt_round_id}: {exc}",
                        exc_info=True)
    except TimeoutError:
        logger.warning(f"Could not acquire lock for AI copy generation of prompt round {prompt_round_id}, "
                       f"another process may be handling it")
    except Exception as exc:
        logger.error(f"Error acquiring lock for AI copy generation of prompt round {prompt_round_id}: {exc}",
                     exc_info=True)
