"""Auto-seed prompt library if empty."""
from backend.database import AsyncSessionLocal
from backend.models.prompt import Prompt
from sqlalchemy import select, func, update, case
import logging
import csv
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)


def get_current_season():
    """Determine current season based on month with overlap periods.
    
    Returns the appropriate seasonal category suffix:
    - Sep-Dec: fall
    - Dec-Mar: winter  
    - Mar-Jun: spring
    - Jun-Sep: summer
    """
    month = datetime.now().month
    
    if month in [9, 10, 11, 12]:  # Sep-Dec
        return "fall"
    elif month in [12, 1, 2, 3]:  # Dec-Mar
        return "winter"
    elif month in [3, 4, 5, 6]:  # Mar-Jun
        return "spring"
    elif month in [6, 7, 8, 9]:  # Jun-Sep
        return "summer"
    
    # Fallback (shouldn't happen)
    return "fall"


def load_prompts_from_csv():
    """Load prompts from CSV file in backend/data/prompts.csv, filtering seasonal prompts by current season"""
    current_dir = Path(__file__).parent.parent  # Go up from services/ to backend/
    csv_path = current_dir / "data" / "prompts.csv"
    
    current_season = get_current_season()
    prompts = []
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                category = row['category']
                
                # Handle seasonal filtering
                if category.startswith('seasonal_'):
                    # Extract season from category (e.g., "seasonal_fall" -> "fall")
                    prompt_season = category.replace('seasonal_', '')
                    if prompt_season == current_season:
                        # Include seasonal prompt for current season, but use "seasonal" as category
                        prompts.append((row['text'], 'seasonal'))
                    # Skip seasonal prompts not for current season
                elif category == 'seasonal':
                    # Generic seasonal prompts are always included
                    prompts.append((row['text'], category))
                else:
                    # Non-seasonal prompts are always included
                    prompts.append((row['text'], category))
        
        logger.info(f"Loaded {len(prompts)} prompts from {csv_path} (current season: {current_season})")
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
    1. Loads prompts from backend/data/prompts.csv (filtered by current season)
    2. Adds any prompts from the CSV that don't exist in the database
    3. Sets enabled=True for prompts that exist in the CSV
    4. Sets enabled=False for prompts in database that aren't in the CSV
    
    Safe to run multiple times - idempotent operation.
    """
    try:
        # Load prompts from CSV file (with seasonal filtering)
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
                logger.info(
                    f"Prompt sync complete: {added_count} added, {enabled_count} re-enabled, {disabled_count} disabled")
            else:
                logger.info("Prompt library already in sync")
            
            # Show current statistics
            result = await db.execute(
                select(
                    Prompt.category, 
                    func.count(Prompt.prompt_id).label('total'),
                    func.sum(case((Prompt.enabled == True, 1), else_=0)).label('enabled')
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
            logger.info(f"Sync summary: {total_enabled}/{total_prompts} prompts enabled")

    except Exception as e:
        logger.error(f"Failed to sync prompts: {e}")
        raise
