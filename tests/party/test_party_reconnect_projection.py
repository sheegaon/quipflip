import pytest
from httpx import ASGITransport, AsyncClient
from uuid import uuid4

from backend.services.qf.party_session_service import PartySessionService
from backend.services.qf.party_websocket_manager import PartyWebSocketManager
from backend.services.qf.websocket_notification_service import WebSocketNotificationService


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent_messages: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, message: dict) -> None:
        self.sent_messages.append(message)


@pytest.mark.asyncio
async def test_party_websocket_disconnect_preserves_readiness(db_session, player_factory):
    host = await player_factory()
    party_service = PartySessionService(db_session)
    websocket_manager = PartyWebSocketManager(WebSocketNotificationService())

    session = await party_service.create_session(host_player_id=host.player_id, min_players=1)
    participant = await party_service.get_participant(session.session_id, host.player_id)
    assert participant is not None
    original_ready_at = participant.ready_at

    websocket = FakeWebSocket()
    await websocket_manager.connect(session.session_id, host.player_id, websocket, db_session, context="lobby")
    await db_session.refresh(participant)
    assert participant.connection_status == "connected"

    await websocket_manager.disconnect(session.session_id, host.player_id, db_session, context="lobby")
    await db_session.refresh(participant)

    assert participant.connection_status == "disconnected"
    assert participant.status == "READY"
    assert participant.ready_at == original_ready_at


@pytest.mark.asyncio
async def test_logout_cleanup_preserves_party_membership(db_session, player_factory):
    host = await player_factory()
    player = await player_factory()
    party_service = PartySessionService(db_session)

    session = await party_service.create_session(host_player_id=host.player_id, min_players=1)
    participant = await party_service.add_participant(session.session_id, player.player_id)
    assert participant.status == "JOINED"

    updated_sessions = await party_service.remove_player_from_all_sessions(player.player_id)
    assert updated_sessions == 1

    still_member = await party_service.get_participant(session.session_id, player.player_id)
    assert still_member is not None
    assert still_member.status == "JOINED"
    assert still_member.connection_status == "disconnected"


@pytest.mark.asyncio
async def test_party_phase_advance_atomic_sets_deadline_and_version(db_session, player_factory):
    host = await player_factory()
    party_service = PartySessionService(db_session)

    session = await party_service.create_session(
        host_player_id=host.player_id,
        min_players=1,
        prompts_per_player=1,
        copies_per_player=1,
        votes_per_player=1,
    )

    started_session = await party_service.start_session(session.session_id, host.player_id)
    await db_session.refresh(started_session)
    prompt_deadline = started_session.phase_expires_at
    started_version = started_session.version

    participant = await party_service.get_participant(session.session_id, host.player_id)
    assert participant is not None
    participant.prompts_submitted = 1
    await db_session.commit()

    advanced_session = await party_service.advance_phase_atomic(session.session_id)
    assert advanced_session is not None
    assert advanced_session.current_phase == "COPY"
    assert advanced_session.status == "IN_PROGRESS"
    assert advanced_session.version > started_version
    assert advanced_session.phase_expires_at is not None
    assert advanced_session.phase_expires_at != prompt_deadline


@pytest.mark.asyncio
async def test_party_status_endpoint_is_member_only(test_app):
    async with AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test/qf") as client:
        host_payload = {
            "username": f"party_host_{uuid4().hex[:6]}",
            "email": f"party_host_{uuid4().hex[:6]}@example.com",
            "password": "PartyHost123!",
        }
        outsider_payload = {
            "username": f"party_outsider_{uuid4().hex[:6]}",
            "email": f"party_outsider_{uuid4().hex[:6]}@example.com",
            "password": "PartyOutsider123!",
        }

        host_create = await client.post("/player", json=host_payload)
        outsider_create = await client.post("/player", json=outsider_payload)
        assert host_create.status_code == 201
        assert outsider_create.status_code == 201

        host_token = host_create.json()["access_token"]
        outsider_token = outsider_create.json()["access_token"]

        client.cookies.clear()
        create_response = await client.post(
            "/party/create",
            json={
                "min_players": 2,
                "max_players": 4,
                "prompts_per_player": 1,
                "copies_per_player": 2,
                "votes_per_player": 3,
            },
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert create_response.status_code == 200
        session_id = create_response.json()["session_id"]

        client.cookies.clear()
        outsider_response = await client.get(
            f"/party/{session_id}/status",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert outsider_response.status_code == 403

        client.cookies.clear()
        host_response = await client.get(
            f"/party/{session_id}/state",
            headers={"Authorization": f"Bearer {host_token}"},
        )
        assert host_response.status_code == 200
        data = host_response.json()
        assert data["session_id"] == session_id
        assert data["version"] >= 1
        assert data["phase_expires_at"] is None
        assert data["participants"][0]["connection_status"] == "connected"
