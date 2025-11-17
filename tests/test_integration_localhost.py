"""
Integration tests for Quipflip API running on localhost.

IMPORTANT: These tests assume the backend is running on http://localhost:8000/qf
To run the server: uvicorn backend.main:app --reload

Run these tests with: pytest tests/test_integration_localhost.py -v
"""
import httpx
import pytest
import time
from typing import Dict, Optional
from backend.version import APP_VERSION

# Base URL for localhost backend
BASE_URL = "http://localhost:8000/qf"
TIMEOUT = 10.0  # seconds

# Counter for unique test users
_player_counter = 0


def create_test_player_data():
    """Generate unique test player registration data."""
    global _player_counter
    _player_counter += 1
    return {
        "username": f"testplayer{_player_counter}_{int(time.time()*1000)}",
        "email": f"testplayer{_player_counter}_{int(time.time()*1000)}@example.com",
        "password": "TestPassword123!"
    }


def create_authenticated_client():
    """Create a new player and return an authenticated client."""
    client = APIClient()
    player_data = create_test_player_data()
    response = client.post("/player", json=player_data)

    if response.status_code != 201:
        raise Exception(f"Failed to create player: {response.status_code} - {response.text}")

    data = response.json()
    access_token = data.get("access_token")

    client.close()

    # Return new client with access token and the player data
    auth_client = APIClient(access_token=access_token)
    return auth_client, data


class APIClient:
    """Helper class for making API requests with authentication."""

    def __init__(self, access_token: Optional[str] = None, api_key: Optional[str] = None):
        self.access_token = access_token
        self.api_key = api_key
        self.client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        if self.api_key:
            return {"X-API-Key": self.api_key}
        return {}

    def get(self, path: str, **kwargs):
        """Make authenticated GET request."""
        return self.client.get(path, headers=self.headers(), **kwargs)

    def post(self, path: str, **kwargs):
        """Make authenticated POST request."""
        return self.client.post(path, headers=self.headers(), **kwargs)

    def close(self):
        """Close the HTTP client."""
        self.client.close()


@pytest.fixture(scope="session")
def verify_server_running():
    """Verify the backend server is running before tests."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if response.status_code != 200:
            pytest.fail(
                f"Server is running but returned status {response.status_code}. "
                "Please ensure the backend is healthy."
            )
    except httpx.ConnectError:
        pytest.fail(
            "Cannot connect to backend server at http://localhost:8000/qf\n"
            "Please start the server with: uvicorn backend.main:app --reload"
        )
    except Exception as e:
        pytest.fail(f"Unexpected error connecting to server: {e}")


class TestHealthEndpoints:
    """Test health check and info endpoints."""

    def test_health_check(self, verify_server_running):
        """Test /health endpoint returns ok status."""
        client = APIClient()
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "database" in data
        assert "redis" in data
        client.close()

    def test_root_endpoint(self, verify_server_running):
        """Test / endpoint returns API info."""
        client = APIClient()
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "version" in data
        assert data["version"] == APP_VERSION
        assert "Quipflip" in data["message"]
        client.close()


class TestPlayerManagement:
    """Test player creation and management."""

    def test_create_player(self, verify_server_running):
        """Test POST /player creates new player with credentials."""
        client = APIClient()
        player_data = create_test_player_data()
        response = client.post("/player", json=player_data)

        assert response.status_code == 201
        data = response.json()
        assert "player_id" in data
        assert "username" in data
        assert data["balance"] == 5000
        assert "access_token" in data
        assert "refresh_token" in data
        client.close()

    def test_get_balance(self, verify_server_running):
        """Test GET /player/balance returns player balance."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # Get balance
        response = auth_client.get("/player/balance")

        assert response.status_code == 200
        data = response.json()
        assert data["balance"] == 5000
        assert data["starting_balance"] == 5000
        assert data["email"].endswith("@example.com")
        assert "created_at" in data
        assert "daily_bonus_available" in data
        assert data["daily_bonus_amount"] == 100
        assert "outstanding_prompts" in data

        auth_client.close()

    def test_balance_requires_auth(self, verify_server_running):
        """Test /player/balance requires authentication."""
        client = APIClient()  # No auth token
        response = client.get("/player/balance")

        assert response.status_code == 401  # Unauthorized
        client.close()

    def test_get_current_round_no_active(self, verify_server_running):
        """Test GET /player/current-round with no active round."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # Check current round
        response = auth_client.get("/player/current-round")

        assert response.status_code == 200
        data = response.json()
        assert data["round_id"] is None
        assert data["round_type"] is None
        assert data["state"] is None

        auth_client.close()

    def test_get_pending_results_empty(self, verify_server_running):
        """Test GET /player/pending-results with no results."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # Check pending results
        response = auth_client.get("/player/pending-results")

        assert response.status_code == 200
        data = response.json()
        assert "pending" in data
        assert isinstance(data["pending"], list)

        auth_client.close()


class TestRoundAvailability:
    """Test round availability checks."""

    def test_get_available_rounds(self, verify_server_running):
        """Test GET /rounds/available returns round status."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # Get availability
        response = auth_client.get("/rounds/available")

        assert response.status_code == 200
        data = response.json()
        assert "can_prompt" in data
        assert "can_copy" in data
        assert "can_vote" in data
        assert "prompts_waiting" in data
        assert "phrasesets_waiting" in data
        assert "copy_discount_active" in data
        assert "copy_cost" in data
        assert "current_round_id" in data

        auth_client.close()


class TestPromptRoundFlow:
    """Test prompt round creation and submission."""

    def test_start_prompt_round(self, verify_server_running):
        """Test POST /rounds/prompt creates new round."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # Start prompt round
        response = auth_client.post("/rounds/prompt", json={})

        assert response.status_code == 200
        data = response.json()
        assert "round_id" in data
        assert "prompt_text" in data
        assert "expires_at" in data
        assert data["cost"] == 100

        # Balance should be deducted
        balance_response = auth_client.get("/player/balance")
        assert balance_response.json()["balance"] == 4900

        auth_client.close()

    def test_submit_prompt_word(self, verify_server_running):
        """Test POST /rounds/{round_id}/submit for prompt round."""
        # Create authenticated client and start prompt round
        auth_client, player_data = create_authenticated_client()

        prompt_response = auth_client.post("/rounds/prompt", json={})
        round_id = prompt_response.json()["round_id"]

        # Submit phrase (must be 2-5 words)
        submit_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "beautiful day"}
        )

        assert submit_response.status_code == 200
        data = submit_response.json()
        assert data["success"] is True
        assert data["phrase"] == "BEAUTIFUL DAY"

        # Current round should be cleared
        current_response = auth_client.get("/player/current-round")
        current_data = current_response.json()
        assert current_data["round_id"] is None

        auth_client.close()

    def test_submit_invalid_word(self, verify_server_running):
        """Test submitting invalid word fails."""
        # Create authenticated client and start prompt round
        auth_client, player_data = create_authenticated_client()

        prompt_response = auth_client.post("/rounds/prompt", json={})
        round_id = prompt_response.json()["round_id"]

        # Submit invalid phrase (contains numbers - validation error)
        submit_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "zzzzzzzzzzz123"}
        )

        assert submit_response.status_code == 422  # Changed from 400 to 422 for validation errors

        auth_client.close()

    def test_cannot_start_second_round(self, verify_server_running):
        """Test player cannot start second round while one is active."""
        # Create authenticated client and start prompt round
        auth_client, player_data = create_authenticated_client()

        auth_client.post("/rounds/prompt", json={})

        # Try to start another round
        second_response = auth_client.post("/rounds/prompt", json={})

        assert second_response.status_code == 400
        data = second_response.json()
        assert "already" in data["detail"].lower() or "active" in data["detail"].lower()

        auth_client.close()

    def test_insufficient_balance_for_prompt(self, verify_server_running):
        """Test cannot start prompt with insufficient balance."""
        # This test would require draining balance first
        # For now, we'll skip detailed implementation
        # as it requires multiple rounds
        pass


class TestCopyRoundFlow:
    """Test copy round functionality."""

    def test_no_prompts_available(self, verify_server_running):
        """Test POST /rounds/copy fails when no prompts available."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # 
        response = auth_client.post("/rounds/copy", json={})

        # Should fail if no prompts are available
        # (may pass if other tests have added prompts to queue)
        # We'll check the response structure either way
        if response.status_code == 400:
            assert "available" in response.json()["detail"].lower()
        elif response.status_code == 200:
            # Copy round started successfully
            data = response.json()
            assert "round_id" in data
            assert "original_phrase" in data  # Changed from original_word to original_phrase
            assert "cost" in data

        auth_client.close()

    def test_copy_round_with_prompt(self, verify_server_running):
        """Test complete copy round flow."""
        # Create first player and submit prompt
        p1_client, player1_data = create_authenticated_client()
        prompt_response = p1_client.post("/rounds/prompt", json={})
        round1_id = prompt_response.json()["round_id"]

        # Submit prompt phrase (must be 2-5 words)
        p1_client.post(
            f"/rounds/{round1_id}/submit",
            json={"phrase": "happy times"}
        )

        # Create second player for copy round
        p2_client, player2_data = create_authenticated_client()

        # Small delay to ensure prompt is in queue
        time.sleep(0.5)

        # Start copy round
        copy_response = p2_client.post("/rounds/copy", json={})

        if copy_response.status_code == 200:
            data = copy_response.json()
            assert "round_id" in data
            assert "original_phrase" in data  # Changed from original_word to original_phrase
            original_phrase = data["original_phrase"]
            copy_round_id = data["round_id"]

            # Submit different phrase (must be 2-5 words)
            submit_response = p2_client.post(
                f"/rounds/{copy_round_id}/submit",
                json={"phrase": "joyful moments"}
            )
            assert submit_response.status_code == 200

        # Cleanup


class TestVoteRoundFlow:
    """Test vote round functionality."""

    def test_no_phrasesets_available(self, verify_server_running):
        """Test POST /rounds/vote when no phrasesets ready."""
        # Create authenticated client
        auth_client, player_data = create_authenticated_client()

        # 
        response = auth_client.post("/rounds/vote", json={})

        # May fail if no complete phrasesets exist
        if response.status_code == 400:
            assert "available" in response.json()["detail"].lower()
        elif response.status_code == 200:
            # Vote round started successfully
            data = response.json()
            assert "round_id" in data
            assert "phraseset_id" in data
            assert "phrases" in data
            assert len(data["phrases"]) == 3

        auth_client.close()


class TestCompleteGameFlow:
    """Test complete game flow with multiple players."""

    def test_full_game_cycle(self, verify_server_running):
        """Test complete game: prompt -> 2 copies -> votes."""
        # Create prompt player
        p1, prompt_player = create_authenticated_client()

        # Start and submit prompt
        prompt_round = p1.post("/rounds/prompt", json={}).json()
        p1.post(
            f"/rounds/{prompt_round['round_id']}/submit",
            json={"phrase": "peaceful morning"}
        )

        # Create first copy player
        c1, copy1_player = create_authenticated_client()

        time.sleep(0.5)  # Ensure prompt is in queue

        # First copy round
        copy1_round = c1.post("/rounds/copy", json={})
        if copy1_round.status_code == 200:
            c1_data = copy1_round.json()
            c1.post(
                f"/rounds/{c1_data['round_id']}/submit",
                json={"phrase": "calm waters"}
            )

            # Create second copy player
            c2, copy2_player = create_authenticated_client()

            time.sleep(0.5)

            # Second copy round
            copy2_round = c2.post("/rounds/copy", json={})
            if copy2_round.status_code == 200:
                c2_data = copy2_round.json()
                c2.post(
                    f"/rounds/{c2_data['round_id']}/submit",
                    json={"phrase": "serene landscape"}
                )

                # Create voter
                v1, voter_player = create_authenticated_client()

                time.sleep(0.5)

                # Start vote round
                vote_round = v1.post("/rounds/vote", json={})
                if vote_round.status_code == 200:
                    vote_data = vote_round.json()
                    assert len(vote_data["phrases"]) == 3  # Changed from words to phrases

                    # Submit vote (changed endpoint and field names)
                    vote_submit = v1.post(
                        f"/phrasesets/{vote_data['phraseset_id']}/vote",
                        json={"phrase": vote_data["phrases"][0]}
                    )

                    if vote_submit.status_code == 200:
                        vote_result = vote_submit.json()
                        assert "correct" in vote_result
                        assert "payout" in vote_result
                        assert "original_phrase" in vote_result  # Changed from original_word to original_phrase

                v1.close()

            c2.close()

        # Cleanup
        p1.close()
        c1.close()


class TestEdgeCases:
    """Test edge cases and error conditions."""

    def test_invalid_api_key(self, verify_server_running):
        """Test requests with invalid API key."""
        client = APIClient("invalid-key-12345")
        response = client.get("/player/balance")

        assert response.status_code == 401
        client.close()

    def test_get_nonexistent_round(self, verify_server_running):
        """Test GET /rounds/{round_id} with invalid ID."""
        client = APIClient()
        auth_client, player_data = create_authenticated_client()

        response = auth_client.get("/rounds/00000000-0000-0000-0000-000000000000")

        assert response.status_code == 404

        client.close()
        auth_client.close()

    def test_submit_word_to_wrong_round(self, verify_server_running):
        """Test submitting word to round not owned by player."""
        # Create two players
        p1, player1 = create_authenticated_client()
        p2, player2 = create_authenticated_client()

        # Player 1 starts round
        round_data = p1.post("/rounds/prompt", json={}).json()
        round_id = round_data["round_id"]

        # Player 2 tries to submit to player 1's round
        response = p2.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "test"}
        )

        assert response.status_code in [404, 422]  # 404 for not found or 422 for validation

        # Cleanup
        p1.close()
        p2.close()

    def test_word_too_short(self, verify_server_running):
        """Test submitting single-letter word (too short)."""
        client = APIClient()
        auth_client, player_data = create_authenticated_client()

        prompt_response = auth_client.post("/rounds/prompt", json={})
        round_id = prompt_response.json()["round_id"]

        # Submit single letter
        submit_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "a"}
        )

        assert submit_response.status_code == 422  # Changed from 400 to 422 for validation errors

        client.close()
        auth_client.close()

    def test_word_too_long(self, verify_server_running):
        """Test submitting word that's too long (>100 chars)."""
        client = APIClient()
        auth_client, player_data = create_authenticated_client()

        prompt_response = auth_client.post("/rounds/prompt", json={})
        round_id = prompt_response.json()["round_id"]

        # Submit phrase longer than 100 characters
        submit_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "verylongwordthatexceedslimit" * 5}  # 145 chars
        )

        assert submit_response.status_code == 422  # Changed from 400 to 422 for validation errors

        client.close()
        auth_client.close()


class TestDataConsistency:
    """Test data consistency across operations."""

    def test_balance_consistency_after_round(self, verify_server_running):
        """Test balance is correctly updated after round operations."""
        client = APIClient()
        auth_client, player_data = create_authenticated_client()


        # Check initial balance
        balance1 = auth_client.get("/player/balance").json()["balance"]
        assert balance1 == 5000

        # Start prompt round
        auth_client.post("/rounds/prompt", json={})

        # Check balance deducted
        balance2 = auth_client.get("/player/balance").json()["balance"]
        assert balance2 == 4900

        client.close()
        auth_client.close()

    def test_outstanding_prompts_tracking(self, verify_server_running):
        """Test outstanding_prompts counter is accurate."""
        client = APIClient()
        auth_client, player_data = create_authenticated_client()


        # Check initial outstanding prompts
        balance_data = auth_client.get("/player/balance").json()
        initial_count = balance_data["outstanding_prompts"]

        # Start and submit prompt round
        prompt_response = auth_client.post("/rounds/prompt", json={})
        round_id = prompt_response.json()["round_id"]
        auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "wonderful day"}
        )

        # Check outstanding prompts increased
        balance_data2 = auth_client.get("/player/balance").json()
        assert balance_data2["outstanding_prompts"] >= initial_count

        client.close()
        auth_client.close()


class TestConcurrency:
    """Test concurrent operations and race conditions."""

    def test_multiple_players_can_play_simultaneously(self, verify_server_running):
        """Test multiple players can have active rounds at same time."""
        auth_clients = []

        # Create 3 players
        for _ in range(3):
            auth_client, player_data = create_authenticated_client()
            auth_clients.append(auth_client)

        # Each player starts a prompt round
        for auth_client in auth_clients:
            response = auth_client.post("/rounds/prompt", json={})
            assert response.status_code == 200

        # All should have active rounds
        for auth_client in auth_clients:
            current = auth_client.get("/player/current-round").json()
            assert current["round_id"] is not None
            assert current["round_type"] == "prompt"

        # Cleanup
        for auth_client in auth_clients:
            auth_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Quipflip Integration Tests")
    print("=" * 60)
    print("\nThese tests assume the backend is running on http://localhost:8000/qf")
    print("To start the server: uvicorn backend.main:app --reload")
    print("\nRun tests with: pytest tests/test_integration_localhost.py -v")
    print("=" * 60)
