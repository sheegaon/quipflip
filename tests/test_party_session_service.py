import pytest

from backend.services.qf.party_session_service import (
    PartySessionService,
    AlreadyInAnotherSessionError,
)


@pytest.mark.asyncio
async def test_player_cannot_join_multiple_parties(db_session, player_factory):
    party_service = PartySessionService(db_session)

    host_one = await player_factory()
    host_two = await player_factory()
    participant = await player_factory()

    session_one = await party_service.create_session(host_player_id=host_one.player_id)
    session_two = await party_service.create_session(host_player_id=host_two.player_id)

    await party_service.add_participant(session_one.session_id, participant.player_id)

    with pytest.raises(AlreadyInAnotherSessionError):
        await party_service.add_participant(session_two.session_id, participant.player_id)
