#!/usr/bin/env python3
"""
Migration script to fix orphaned captions by assigning them to the system player.

This script updates all MM captions that have author_player_id = NULL to use
the special system player ID, making them identifiable as seeded/system content.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, update

from backend.config import get_settings
from backend.models.mm.caption import MMCaption

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Special UUID for system/seeded content - must match the one used in seeding and vote service
SYSTEM_PLAYER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def fix_orphaned_captions():
    """Update all captions with NULL author_player_id to use the system player ID."""
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # First, check how many orphaned captions exist
        stmt = select(MMCaption).where(MMCaption.author_player_id.is_(None))
        result = await session.execute(stmt)
        orphaned_captions = list(result.scalars().all())
        
        if not orphaned_captions:
            logger.info("No orphaned captions found - nothing to fix!")
            return

        logger.info(f"Found {len(orphaned_captions)} orphaned captions to fix")
        
        # Update them to use the system player ID
        stmt = update(MMCaption).where(
            MMCaption.author_player_id.is_(None)
        ).values(
            author_player_id=SYSTEM_PLAYER_ID
        )
        
        result = await session.execute(stmt)
        updated_count = result.rowcount
        
        await session.commit()
        logger.info(f"Successfully updated {updated_count} captions to use system player ID")
        
        # Verify the fix
        stmt = select(MMCaption).where(MMCaption.author_player_id.is_(None))
        result = await session.execute(stmt)
        remaining_orphaned = len(list(result.scalars().all()))
        
        if remaining_orphaned == 0:
            logger.info("✅ All orphaned captions have been fixed!")
        else:
            logger.warning(f"⚠️  {remaining_orphaned} orphaned captions still remain")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(fix_orphaned_captions())