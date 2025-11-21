import pytest
import uuid
from datetime import datetime, UTC, timedelta
from unittest.mock import patch, AsyncMock, MagicMock

from sqlalchemy import select

from backend.services.ai.ai_service import AIService, AI_PLAYER_EMAIL_DOMAIN
from backend.services.qf.party_session_service import PartySessionService
from backend.models.qf.player import QFPlayer
from backend.models.qf.party_participant import PartyParticipant
from backend.models.qf.party_session import PartySession
from backend.models.qf.vote import Vote
from backend.models.qf.phraseset import Phraseset
from backend.models.qf.phraseset_activity import PhrasesetActivity
from backend.utils.model_registry import GameType
from backend.config import get_settings

@pytest.fixture
def ai_service(db_session):
    return AIService(db_session)

@pytest.fixture
def party_service(db_session):
    return PartySessionService(db_session)

@pytest.mark.asyncio
class TestAIPlayerPooling:
    
    async def test_party_player_pooling(self, db_session, party_service, player_factory):
        """Test that AI party players are reused when available."""
        host = await player_factory()
        
        # 1. Create first session and add AI player
        session1 = await party_service.create_session(host.player_id)
        ai_participant1 = await party_service.add_ai_player(
            session1.session_id, host.player_id, GameType.QF
        )
        ai_player_id = ai_participant1.player_id
        
        # Verify it's an AI player
        player1 = await db_session.get(QFPlayer, ai_player_id)
        assert player1.email.endswith(AI_PLAYER_EMAIL_DOMAIN)
        assert "ai_party" in player1.email
        
        # 2. Create second session and add AI player (should be NEW because first is busy)
        session2 = await party_service.create_session(host.player_id)
        ai_participant2 = await party_service.add_ai_player(
            session2.session_id, host.player_id, GameType.QF
        )
        assert ai_participant2.player_id != ai_player_id
        
        # 3. End first session (delete it)
        # This frees up the first AI player
        await party_service._delete_empty_session(session1.session_id)
        
        # 4. Create third session and add AI player (should REUSE first player)
        session3 = await party_service.create_session(host.player_id)
        ai_participant3 = await party_service.add_ai_player(
            session3.session_id, host.player_id, GameType.QF
        )
        
        assert ai_participant3.player_id == ai_player_id
        
    async def test_voter_pooling(self, db_session, ai_service, player_factory):
        """Test that AI voters are reused but don't vote twice on same phraseset."""
        
        # Setup settings to force backup
        with patch("backend.services.ai.ai_service.get_settings") as mock_settings:
            settings = mock_settings.return_value
            settings.ai_backup_delay_minutes = 0
            settings.ai_backup_batch_size = 10
            settings.openai_api_key = "sk-test"
            settings.use_phrase_validator_api = False
            
            # Mock vote generation to avoid API calls
            ai_service.generate_vote_choice = AsyncMock(return_value="PHRASE")
            
            # Mock VoteService.submit_system_vote to avoid DB side effects and focus on pooling
            with patch("backend.services.VoteService.submit_system_vote", new_callable=AsyncMock) as mock_submit:
                # Return a dummy vote object so run_backup_cycle continues successfully
                mock_vote = MagicMock(spec=Vote)
                mock_vote.voted_phrase = "PHRASE"
                mock_vote.correct = True
                mock_vote.payout = 10
                mock_submit.return_value = mock_vote
                
                # Create a phraseset that needs votes
                prompter = await player_factory()
                
                # Helper to create phraseset
                async def create_waiting_phraseset():
                    # Create dummy rounds
                    from backend.models.qf.round import Round
                    
                    # Need a player for rounds
                    round_player = await player_factory()
                    
                    prompt_round = Round(
                        round_id=uuid.uuid4(), 
                        player_id=round_player.player_id,
                        round_type="prompt", 
                        status="completed", 
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        cost=0
                    )
                    copy_round_1 = Round(
                        round_id=uuid.uuid4(), 
                        player_id=round_player.player_id,
                        round_type="copy", 
                        status="completed", 
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        cost=0
                    )
                    copy_round_2 = Round(
                        round_id=uuid.uuid4(), 
                        player_id=round_player.player_id,
                        round_type="copy", 
                        status="completed", 
                        created_at=datetime.now(UTC),
                        expires_at=datetime.now(UTC) + timedelta(hours=1),
                        cost=0
                    )
                    
                    db_session.add_all([prompt_round, copy_round_1, copy_round_2])
                    
                    phraseset_id = uuid.uuid4()
                    phraseset = Phraseset(
                        phraseset_id=phraseset_id,
                        prompt_round_id=prompt_round.round_id,
                        copy_round_1_id=copy_round_1.round_id,
                        copy_round_2_id=copy_round_2.round_id,
                        prompt_text="Prompt",
                        original_phrase="Original",
                        copy_phrase_1="Copy1",
                        copy_phrase_2="Copy2",
                        status="open",
                        created_at=datetime.now(UTC) - timedelta(minutes=10),
                        vote_count=0,
                        total_pool=100,
                        vote_contributions=0,
                        vote_payouts_paid=0,
                        system_contribution=0
                    )
                    
                    # Add a human vote so it's eligible for AI backup
                    human = await player_factory()
                    vote = Vote(
                        vote_id=uuid.uuid4(),
                        phraseset_id=phraseset_id,
                        player_id=human.player_id,
                        voted_phrase="Original",
                        correct=True,
                        payout=10,
                        created_at=datetime.now(UTC) - timedelta(minutes=5)
                    )
                    
                    db_session.add(phraseset)
                    db_session.add(vote)
                    await db_session.commit()
                    return phraseset

                phraseset1 = await create_waiting_phraseset()
                
                # Debug DB state
                players = await db_session.execute(select(QFPlayer))
                print("\nDEBUG: Players:")
                for p in players.scalars().all():
                    print(f"  {p.player_id} - {p.email}")
                    
                votes = await db_session.execute(select(Vote))
                print("\nDEBUG: Votes:")
                for v in votes.scalars().all():
                    print(f"  {v.vote_id} - {v.player_id} - {v.phraseset_id}")
                
                phrasesets = await db_session.execute(select(Phraseset))
                print("\nDEBUG: Phrasesets:")
                for p in phrasesets.scalars().all():
                    print(f"  {p.phraseset_id} - {p.status} - {p.created_at}")

                # Debug subquery
                human_vote_phrasesets_subquery = (
                    select(Vote.phraseset_id)
                    .join(QFPlayer, QFPlayer.player_id == Vote.player_id)
                    .where(~QFPlayer.email.like(f"%{AI_PLAYER_EMAIL_DOMAIN}"))
                    .distinct()
                )
                subquery_result = await db_session.execute(human_vote_phrasesets_subquery)
                print(f"\nDEBUG: Subquery result: {subquery_result.scalars().all()}")

                # 1. Run backup cycle - should create new AI voter
                await ai_service.run_backup_cycle()
                
                assert mock_submit.call_count == 1
                # Get the player passed to submit_system_vote
                call_args1 = mock_submit.call_args
                player1 = call_args1.kwargs['player']
                assert "ai_voter" in player1.email
                ai_voter_id_1 = player1.player_id
                
                # Simulate that this player voted by creating a Vote record in DB
                # (run_backup_cycle would do this via vote_service, but we mocked it)
                vote1 = Vote(
                    vote_id=uuid.uuid4(),
                    phraseset_id=phraseset1.phraseset_id,
                    player_id=ai_voter_id_1,
                    voted_phrase="PHRASE",
                    correct=True,
                    payout=10,
                    created_at=datetime.now(UTC)
                )
                db_session.add(vote1)
                await db_session.commit()
                
                # 2. Create another phraseset
                phraseset2 = await create_waiting_phraseset()
                
                # 3. Run backup cycle - should REUSE the same AI voter
                await ai_service.run_backup_cycle()
                
                assert mock_submit.call_count == 2
                call_args2 = mock_submit.call_args
                player2 = call_args2.kwargs['player']
                assert player2.player_id == ai_voter_id_1
                
                # Simulate vote for phraseset2
                vote2 = Vote(
                    vote_id=uuid.uuid4(),
                    phraseset_id=phraseset2.phraseset_id,
                    player_id=ai_voter_id_1,
                    voted_phrase="PHRASE",
                    correct=True,
                    payout=10,
                    created_at=datetime.now(UTC)
                )
                db_session.add(vote2)
                await db_session.commit()
                
                # 4. Run backup cycle AGAIN on phraseset1
                # We need to ensure phraseset1 is picked up again.
                # It needs to pass the filters.
                # Filter 1: status open/closing (True)
                # Filter 2: created_at <= cutoff (True)
                # Filter 3: in human_vote_phrasesets_subquery (True)
                # Filter 4: No recent activity > cutoff (now).
                # We just added a vote at 'now'. So it has recent activity.
                # We need to backdate the activity (vote) we just added.
                
                await db_session.execute(
                    PhrasesetActivity.__table__.update()
                    .where(PhrasesetActivity.phraseset_id == phraseset1.phraseset_id)
                    .values(created_at=datetime.now(UTC) - timedelta(hours=1))
                )
                # Also backdate the Vote we manually added, although filtering uses PhrasesetActivity?
                # Wait, the code filters using PhrasesetActivity table.
                # But we only added a Vote object. Does that create PhrasesetActivity?
                # No, we mocked VoteService.
                # So PhrasesetActivity table is empty for the AI vote unless we add it.
                # If it's empty, then "no recent activity" check passes!
                # So phraseset1 SHOULD be picked up again immediately.
                
                # However, we need to make sure we don't pick the SAME player.
                # The code queries for a player who has NOT voted on this phraseset.
                # We added the Vote record for ai_voter_id_1 on phraseset1.
                # So that player should be excluded.
                # It should find NO available players (since we only have 1 AI voter so far).
                # So it should create a NEW AI voter.
                
                await ai_service.run_backup_cycle()
                
                assert mock_submit.call_count == 3
                call_args3 = mock_submit.call_args
                player3 = call_args3.kwargs['player']
                assert player3.player_id != ai_voter_id_1
                assert "ai_voter" in player3.email
