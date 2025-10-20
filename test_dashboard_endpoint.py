#!/usr/bin/env python3
"""Test the dashboard endpoint for errors."""
import sys
sys.path.insert(0, '/Users/tfish/PycharmProjects/quipflip')

import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from backend.database import get_db
from backend.routers.player import get_dashboard_data
from backend.models.player import Player
from backend.config import get_settings

async def test_dashboard():
    settings = get_settings()
    engine = create_async_engine(settings.database_url, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get first player
        from sqlalchemy import select
        result = await session.execute(select(Player).limit(1))
        player = result.scalar_one_or_none()

        if not player:
            print("No players found in database")
            return

        print(f"\nTesting dashboard endpoint for player: {player.username}")

        try:
            # Call the dashboard endpoint
            dashboard_data = await get_dashboard_data(player=player, db=session)
            print("\n✅ Dashboard endpoint succeeded!")
            print(f"Player balance: {dashboard_data.player.balance}")
            print(f"Pending results: {len(dashboard_data.pending_results)}")
            print(f"Round availability: {dashboard_data.round_availability}")
        except Exception as e:
            print(f"\n❌ Dashboard endpoint failed with error:")
            print(f"Type: {type(e).__name__}")
            print(f"Message: {str(e)}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_dashboard())
