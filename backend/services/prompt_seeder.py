"""Auto-seed prompt library if empty."""
from backend.database import AsyncSessionLocal
from backend.models.prompt import Prompt
from sqlalchemy import select, func, update
import logging
import csv
from pathlib import Path

logger = logging.getLogger(__name__)


def load_prompts_from_csv():
    """Load prompts from CSV file in backend/data/prompts.csv"""
    current_dir = Path(__file__).parent.parent  # Go up from services/ to backend/
    csv_path = current_dir / "data" / "prompts.csv"
    
    prompts = []
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                prompts.append((row['text'], row['category']))
        logger.info(f"Loaded {len(prompts)} prompts from {csv_path}")
        return prompts
    except FileNotFoundError:
        logger.error(f"Prompts CSV file not found at {csv_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading prompts CSV: {e}")
        raise


async def sync_prompts_with_database():
    """Synchronize prompts between CSV file and database.

    This runs on application startup and:
    1. Loads prompts from backend/data/prompts.csv
    2. Adds any prompts from the CSV that don't exist in the database
    3. Sets enabled=True for prompts that exist in the CSV
    4. Sets enabled=False for prompts in database that aren't in the CSV
    
    Safe to run multiple times - idempotent operation.
    """
    try:
        # Load prompts from CSV file
        file_prompts_list = load_prompts_from_csv()
        
        async with AsyncSessionLocal() as db:
            # Get all existing prompts from database
            result = await db.execute(select(Prompt.text, Prompt.category, Prompt.enabled))
            existing_prompts = {(row.text, row.category): row.enabled for row in result}
            
            # Convert file prompts to set for comparison
            file_prompts = set(file_prompts_list)
            
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
