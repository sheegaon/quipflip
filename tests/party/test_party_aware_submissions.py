import pytest
from uuid import uuid4
from backend.models.qf.round import Round
from backend.models.qf.party_round import PartyRound
from backend.services.qf.party_coordination_service import PartyCoordinationService
from backend.services.qf.party_session_service import PartySessionService
from backend.services.qf.round_service import RoundService
from backend.services import TransactionService

@pytest.mark.asyncio
async def test_normal_submission_without_party_context(db_session, player_factory):
    """Verify normal submissions still work when not in party mode."""
    player = await player_factory()
    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)

    # Seed prompts
    from backend.models.qf.prompt import Prompt
    prompt = Prompt(prompt_id=uuid4(), text="Normal Mode Prompt", category="test")
    db_session.add(prompt)
    await db_session.commit()

    # Create normal round
    round_obj = await round_service.start_prompt_round(player, transaction_service)
    assert round_obj.party_round_id is None

    # Submit phrase (avoid reusing words from prompt)
    result = await round_service.submit_prompt_phrase(round_obj.round_id, "unique answer", player, transaction_service)
    
    # Verify result is Round object (normal service returns Round)
    assert isinstance(result, Round)
    assert result.submitted_phrase == "UNIQUE ANSWER"

@pytest.mark.asyncio
async def test_party_submission_increments_progress(db_session, player_factory):
    """Verify party submissions increment participant progress."""
    host = await player_factory()
    party_service = PartySessionService(db_session)
    coordination_service = PartyCoordinationService(db_session)
    transaction_service = TransactionService(db_session)

    # Create party session
    session = await party_service.create_session(host_player_id=host.player_id, min_players=1)
    
    # Start session (needs min players, so we set min=1 for test)
    await party_service.start_session(session.session_id, host.player_id)

    # Seed prompts
    from backend.models.qf.prompt import Prompt
    prompt = Prompt(prompt_id=uuid4(), text="Party Mode Prompt", category="test")
    db_session.add(prompt)
    await db_session.commit()

    # Start party prompt round
    round_obj, party_round_id = await coordination_service.start_party_prompt_round(
        session_id=session.session_id,
        player=host,
        transaction_service=transaction_service
    )

    # Verify party_round_id is set
    assert round_obj.party_round_id == party_round_id

    # Submit phrase
    result = await coordination_service.submit_party_prompt(
        session_id=session.session_id,
        player=host,
        round_id=round_obj.round_id,
        phrase="fun answer",
        transaction_service=transaction_service
    )

    # Verify progress incremented
    participant = await party_service.get_participant(session.session_id, host.player_id)
    assert participant.prompts_submitted == 1
    assert result['success'] is True

@pytest.mark.asyncio
async def test_party_phase_advancement_automatic(db_session, player_factory):
    """Verify phase advances when all players submit."""
    host = await player_factory()
    player2 = await player_factory()
    
    party_service = PartySessionService(db_session)
    coordination_service = PartyCoordinationService(db_session)
    transaction_service = TransactionService(db_session)

    # Create party session with 2 players, 1 prompt each
    session = await party_service.create_session(
        host_player_id=host.player_id, 
        min_players=2,
        prompts_per_player=1
    )
    await party_service.add_participant(session.session_id, player2.player_id)
    
    # Start session
    await party_service.start_session(session.session_id, host.player_id)

    # Seed prompts
    from backend.models.qf.prompt import Prompt
    prompt1 = Prompt(prompt_id=uuid4(), text="Phase Test Prompt One", category="test")
    prompt2 = Prompt(prompt_id=uuid4(), text="Phase Test Prompt Two", category="test")
    db_session.add_all([prompt1, prompt2])
    await db_session.commit()

    # Player 1 submits
    round1, _ = await coordination_service.start_party_prompt_round(
        session_id=session.session_id,
        player=host,
        transaction_service=transaction_service
    )
    await coordination_service.submit_party_prompt(
        session_id=session.session_id,
        player=host,
        round_id=round1.round_id,
        phrase="first answer",
        transaction_service=transaction_service
    )
    
    # Check phase (should still be PROMPT)
    session = await party_service.get_session_by_id(session.session_id)
    assert session.current_phase == 'PROMPT'

    # Player 2 submits
    round2, _ = await coordination_service.start_party_prompt_round(
        session_id=session.session_id,
        player=player2,
        transaction_service=transaction_service
    )
    await coordination_service.submit_party_prompt(
        session_id=session.session_id,
        player=player2,
        round_id=round2.round_id,
        phrase="second answer",
        transaction_service=transaction_service
    )

    # Verify phase advanced to COPY
    session = await party_service.get_session_by_id(session.session_id)
    assert session.current_phase == 'COPY'
