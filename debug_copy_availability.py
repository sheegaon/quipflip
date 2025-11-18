#!/usr/bin/env python3
"""
Test script to debug copy round availability issues.
This script checks the database state and round availability logic.
"""

import asyncio
from backend.database import AsyncSessionLocal
from backend.services import RoundService
from backend.services import PlayerService
from sqlalchemy import func, select, text
from datetime import datetime, timezone


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f" {title}")
    print(f"{'=' * 60}")


async def debug_copy_availability():
    """Debug copy round availability issues"""
    print("🔍 Copy Round Availability Debug Script")
    print(f"⏰ Current time: {datetime.now(timezone.utc)}")

    # Get database session using AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        round_service = RoundService(db)
        player_service = PlayerService(db)

        try:
            print_section("DATABASE STATE")

            # Count total rounds by type using raw SQL to avoid import issues
            total_prompts_result = await db.execute(text("SELECT COUNT(*) FROM rounds WHERE round_type = 'prompt'"))
            total_prompts = total_prompts_result.scalar()

            total_copies_result = await db.execute(text("SELECT COUNT(*) FROM rounds WHERE round_type = 'copy'"))
            total_copies = total_copies_result.scalar()

            total_votes_result = await db.execute(text("SELECT COUNT(*) FROM rounds WHERE round_type = 'vote'"))
            total_votes = total_votes_result.scalar()

            total_phrasesets_result = await db.execute(text("SELECT COUNT(*) FROM phrasesets"))
            total_phrasesets = total_phrasesets_result.scalar()

            print(f"📊 Total Rounds:")
            print(f"   Prompt rounds: {total_prompts}")
            print(f"   Copy rounds: {total_copies}")
            print(f"   Vote rounds: {total_votes}")
            print(f"   Phraseset: {total_phrasesets}")

            print_section("PROMPT ROUNDS WAITING FOR COPIES")

            # Get players first to test availability for each
            players_result = await db.execute(text("SELECT player_id, username, balance FROM players"))
            players = players_result.fetchall()

            if players:
                # Test get_available_prompts_count for the first player as an example
                first_player = players[0]
                available_count = await round_service.get_available_prompts_count(first_player.player_id)
                print(f"🎯 Available prompts count (from service for {first_player.username}): {available_count}")
            else:
                print("❌ No players found to test availability count")

            # Manual query to see what prompts are waiting - use raw SQL
            prompts_waiting_result = await db.execute(text("""
                SELECT r.round_id, r.player_id, r.status, r.created_at, r.expires_at, r.submitted_phrase, p.username
                FROM rounds r
                LEFT JOIN phrasesets ps ON ps.prompt_round_id = r.round_id
                LEFT JOIN players p ON p.player_id = r.player_id
                WHERE r.round_type = 'prompt'
                AND r.status = 'submitted'
                AND ps.phraseset_id IS NULL
            """))
            prompts_waiting = prompts_waiting_result.fetchall()

            print(f"📝 Prompts waiting for copies (manual query): {len(prompts_waiting)}")

            if prompts_waiting:
                print("\n   Details of waiting prompts:")
                for prompt in prompts_waiting[:5]:  # Show first 5
                    print(f"   - ID: {prompt.round_id}")
                    print(f"     Player: {prompt.username}")
                    print(f"     Status: {prompt.status}")
                    print(f"     Created: {prompt.created_at}")
                    print(f"     Expired: {prompt.expires_at}")
                    if prompt.submitted_phrase:
                        print(f"     Phrase: {prompt.submitted_phrase[:50]}...")
                    print()

            print_section("ALL PROMPT ROUNDS")

            # Show all prompt rounds and their status
            all_prompts_result = await db.execute(text("""
                SELECT r.round_id, r.player_id, r.status, r.created_at, r.expires_at, r.submitted_phrase, 
                       p.username, ps.phraseset_id
                FROM rounds r
                LEFT JOIN players p ON p.player_id = r.player_id
                LEFT JOIN phrasesets ps ON ps.prompt_round_id = r.round_id
                WHERE r.round_type = 'prompt'
                ORDER BY r.created_at DESC
                LIMIT 10
            """))
            all_prompts = all_prompts_result.fetchall()

            print(f"📋 Recent prompt rounds (last 10):")

            for prompt in all_prompts:
                has_phraseset = bool(prompt.phraseset_id)
                status = "Has phraseset" if has_phraseset else "No phraseset"
                if not prompt.submitted_phrase:
                    status = "Not submitted"
                elif prompt.expires_at:
                    # Handle timezone-aware datetime comparison
                    try:
                        if isinstance(prompt.expires_at, str):
                            from datetime import datetime as dt
                            expires_at = dt.fromisoformat(prompt.expires_at.replace('Z', '+00:00'))
                        else:
                            expires_at = prompt.expires_at
                            # Ensure timezone awareness
                            if expires_at.tzinfo is None:
                                expires_at = expires_at.replace(tzinfo=timezone.utc)
                        
                        current_time = datetime.now(timezone.utc)
                        if expires_at >= current_time:
                            status = "Still active"
                    except Exception:
                        # If datetime comparison fails, just skip the status check
                        pass

                print(f"   - ID: {prompt.round_id} | Player: {prompt.username}")
                print(f"     Status: {status} (DB status: {prompt.status})")
                print(f"     Created: {prompt.created_at}")
                print(f"     Expires: {prompt.expires_at}")
                if prompt.submitted_phrase:
                    print(f"     Phrase: {prompt.submitted_phrase[:50]}...")
                print()

            print_section("PHRASESETS")

            # Check phrasesets and their source prompts
            phrasesets_result = await db.execute(text("""
                SELECT phraseset_id, prompt_round_id, status, created_at
                FROM phrasesets
                ORDER BY created_at DESC
                LIMIT 5
            """))
            phrasesets = phrasesets_result.fetchall()

            print(f"📦 Recent phrasesets (last 5):")

            for phraseset in phrasesets:
                print(f"   - ID: {phraseset.phraseset_id}")
                print(f"     Prompt ID: {phraseset.prompt_round_id}")
                print(f"     Status: {phraseset.status}")
                print(f"     Created: {phraseset.created_at}")
                print()

            print_section("PLAYERS")

            print(f"👥 Players ({len(players)}):")

            for player in players:
                prompt_count_result = await db.execute(text("""
                    SELECT COUNT(*) FROM rounds 
                    WHERE player_id = :player_id AND round_type = 'prompt'
                """), {"player_id": player.player_id})
                prompt_count = prompt_count_result.scalar()

                copy_count_result = await db.execute(text("""
                    SELECT COUNT(*) FROM rounds 
                    WHERE player_id = :player_id AND round_type = 'copy'
                """), {"player_id": player.player_id})
                copy_count = copy_count_result.scalar()

                vote_count_result = await db.execute(text("""
                    SELECT COUNT(*) FROM rounds 
                    WHERE player_id = :player_id AND round_type = 'vote'
                """), {"player_id": player.player_id})
                vote_count = vote_count_result.scalar()

                print(f"   - {player.username} (ID: {player.player_id})")
                print(f"     Prompts: {prompt_count} | Copies: {copy_count} | Votes: {vote_count}")
                print(f"     Balance: {player.balance}")
                print()

            print_section("ROUND AVAILABILITY CHECK")

            # Test round availability for each player
            for player in players:
                print(f"🎮 Round availability for {player.username}:")

                try:
                    availability = await round_service.get_round_availability(player.player_id)
                    print(f"   Can prompt: {availability.can_prompt}")
                    print(f"   Can copy: {availability.can_copy}")
                    print(f"   Can vote: {availability.can_vote}")
                    print(f"   Prompts waiting: {availability.prompts_waiting}")
                    print(f"   PhraseSets waiting: {availability.phrasesets_waiting}")
                    print(f"   Copy cost: {availability.copy_cost}")
                    print()
                except Exception as e:
                    print(f"   ❌ Error getting availability: {e}")
                    import traceback
                    traceback.print_exc()
                    print()

            print_section("MANUAL COPY AVAILABILITY CHECK")

            # Manual check of copy availability logic
            now = datetime.now(timezone.utc)

            # Check if there are prompts that should be available for copying
            eligible_prompts_result = await db.execute(text("""
                SELECT r.round_id, r.player_id, r.submitted_phrase, r.expires_at, p.username, ps.phraseset_id
                FROM rounds r
                LEFT JOIN players p ON p.player_id = r.player_id
                LEFT JOIN phrasesets ps ON ps.prompt_round_id = r.round_id
                WHERE r.round_type = 'prompt'
                AND r.submitted_phrase IS NOT NULL
                AND r.expires_at < :now
            """), {"now": now})
            eligible_prompts = eligible_prompts_result.fetchall()

            print(f"🔍 Total submitted & expired prompts: {len(eligible_prompts)}")

            prompts_without_phrasesets = []
            prompts_with_phrasesets = []

            for prompt in eligible_prompts:
                if prompt.phraseset_id:
                    prompts_with_phrasesets.append(prompt)
                else:
                    prompts_without_phrasesets.append(prompt)

            print(f"📝 Prompts without phrasesets (should be available for copy): {len(prompts_without_phrasesets)}")
            print(f"📦 Prompts with phrasesets (already copied): {len(prompts_with_phrasesets)}")

            if prompts_without_phrasesets:
                print("\n   Prompts that should be available for copying:")
                for prompt in prompts_without_phrasesets[:3]:
                    phrase_preview = prompt.submitted_phrase[:30] + "..." if prompt.submitted_phrase else "No phrase"
                    print(f"   - Round {prompt.round_id}: '{phrase_preview}'")
                    print(f"     By: {prompt.username}")
                    print(f"     Expired: {prompt.expires_at}")

            print_section("COPY COST CALCULATION")

            # Test copy cost calculation for each player
            for player in players:
                try:
                    # Check if the method exists and is callable
                    if hasattr(round_service, '_calculate_copy_cost'):
                        copy_cost = await round_service._calculate_copy_cost(player.player_id)
                        print(f"💰 {player.username}: Copy cost = {copy_cost}")
                    else:
                        print(f"💰 {player.username}: _calculate_copy_cost method not available")
                except Exception as e:
                    print(f"❌ Error calculating copy cost for {player.username}: {e}")

        except Exception as e:
            print(f"❌ Error during debug: {e}")
            import traceback
            traceback.print_exc()


def main():
    """Run the async debug function"""
    asyncio.run(debug_copy_availability())


if __name__ == "__main__":
    main()
