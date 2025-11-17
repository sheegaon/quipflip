"""
Stress and load tests for Quipflip API on localhost.

These tests simulate high-load scenarios and edge cases.
IMPORTANT: Backend must be running on http://localhost:8000/qf

Run with: pytest tests/test_stress_localhost.py -v
"""
import httpx
import pytest
import concurrent.futures
import time
from typing import List, Dict

BASE_URL = "http://localhost:8000/qf"
TIMEOUT = 30.0

# Counter for unique test users
_player_counter = 0


def create_test_player_data():
    """Generate unique test player registration data."""
    global _player_counter
    _player_counter += 1
    return {
        "username": f"stresstest{_player_counter}_{int(time.time()*1000)}",
        "email": f"stresstest{_player_counter}_{int(time.time()*1000)}@example.com",
        "password": "TestPassword123!"
    }


def create_authenticated_client():
    """Create a new player and return an authenticated client."""
    client = TestClient()
    player_data = create_test_player_data()
    response = client.post("/player", json=player_data)

    if response.status_code != 201:
        raise Exception(f"Failed to create player: {response.status_code} - {response.text}")

    data = response.json()
    access_token = data.get("access_token")

    client.close()

    # Return new client with access token and the player data
    auth_client = TestClient(access_token=access_token)
    return auth_client, data


class TestClient:
    """Helper class for making API requests."""

    def __init__(self, access_token: str = None, api_key: str = None):
        self.access_token = access_token
        self.api_key = api_key
        self.client = httpx.Client(base_url=BASE_URL, timeout=TIMEOUT)

    def headers(self) -> Dict[str, str]:
        if self.access_token:
            return {"Authorization": f"Bearer {self.access_token}"}
        if self.api_key:
            return {"X-API-Key": self.api_key}
        return {}

    def get(self, path: str, **kwargs):
        return self.client.get(path, headers=self.headers(), **kwargs)

    def post(self, path: str, **kwargs):
        return self.client.post(path, headers=self.headers(), **kwargs)

    def close(self):
        self.client.close()


@pytest.fixture(scope="session")
def verify_server_running():
    """Verify backend is running."""
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=5.0)
        if response.status_code != 200:
            pytest.fail(f"Server unhealthy: {response.status_code}")
    except httpx.ConnectError:
        pytest.fail(
            "Cannot connect to http://localhost:8000/qf\n"
            "Start server: uvicorn backend.main:app --reload"
        )


class TestHighVolumePlayerCreation:
    """Test creating many players rapidly."""

    def test_create_100_players(self, verify_server_running):
        """Create 100 players in quick succession."""
        players = []
        clients = []

        start_time = time.time()

        for i in range(100):
            client, player_data = create_authenticated_client()
            players.append(player_data)
            clients.append(client)

        end_time = time.time()
        duration = end_time - start_time

        print(f"\nCreated 100 players in {duration:.2f} seconds")
        print(f"Average: {duration/100:.3f} seconds per player")

        # Verify all players have unique IDs and access tokens
        player_ids = [p["player_id"] for p in players]
        access_tokens = [p["access_token"] for p in players]

        assert len(set(player_ids)) == 100, "Duplicate player IDs found"
        assert len(set(access_tokens)) == 100, "Duplicate access tokens found"

        # Cleanup
        for client in clients:
            client.close()


class TestConcurrentRounds:
    """Test concurrent round operations."""

    def test_concurrent_prompt_rounds(self, verify_server_running):
        """Test multiple players starting prompt rounds simultaneously."""
        num_players = 20

        # Create players
        players = []
        for _ in range(num_players):
            client, player_data = create_authenticated_client()
            players.append((client, player_data))

        # Start prompt rounds concurrently
        def start_prompt(access_token):
            client = TestClient(access_token=access_token)
            try:
                response = client.post("/rounds/prompt", json={})
                return response.status_code, response.json()
            finally:
                client.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(start_prompt, player_data["access_token"])
                for client, player_data in players
            ]
            results = [future.result() for future in futures]

        # All should succeed
        success_count = sum(1 for status, _ in results if status == 200)
        print(f"\n{success_count}/{num_players} prompt rounds started successfully")

        assert success_count == num_players

        # Cleanup
        for client, _ in players:
            client.close()

    def test_concurrent_balance_checks(self, verify_server_running):
        """Test concurrent balance check requests."""
        # Create player
        auth_client, player_data = create_authenticated_client()
        access_token = player_data["access_token"]

        # Make 50 concurrent balance requests
        def check_balance():
            client = TestClient(access_token=access_token)
            try:
                response = client.get("/player/balance")
                return response.status_code, response.json()
            finally:
                client.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(check_balance) for _ in range(50)]
            results = [future.result() for future in futures]

        # All should succeed with same balance
        assert all(status == 200 for status, _ in results)
        balances = [data["balance"] for _, data in results]
        assert all(b == balances[0] for b in balances), "Balance inconsistency detected"

        auth_client.close()


class TestRateLimiting:
    """Test rate limiting behavior."""

    def test_rapid_requests(self, verify_server_running):
        """Test making many requests rapidly."""
        auth_client, player_data = create_authenticated_client()

        # Make 150 rapid requests (rate limit is 100/min)
        responses = []
        start_time = time.time()

        for i in range(150):
            response = auth_client.get("/player/balance")
            responses.append(response.status_code)

        end_time = time.time()
        duration = end_time - start_time

        # Count rate limited responses (429)
        rate_limited = sum(1 for status in responses if status == 429)
        successful = sum(1 for status in responses if status == 200)

        print(f"\nMade 150 requests in {duration:.2f} seconds")
        print(f"Successful: {successful}, Rate limited: {rate_limited}")

        # Note: Rate limiting may or may not be enabled
        # This test documents behavior rather than asserting specific limits

        auth_client.close()


class TestQueueStress:
    """Test queue system under load."""

    def test_queue_many_prompts(self, verify_server_running):
        """Test adding many prompts to queue."""
        word_list = [
            "beautiful", "wonderful", "amazing", "fantastic", "incredible",
            "peaceful", "joyful", "happy", "excited", "grateful",
            "creative", "brilliant", "clever", "smart", "wise",
            "strong", "brave", "bold", "fierce", "mighty"
        ]

        # Create 20 players and submit prompts
        for i in range(20):
            auth_client, player_data = create_authenticated_client()
            prompt_round = auth_client.post("/rounds/prompt", json={})

            if prompt_round.status_code == 200:
                round_id = prompt_round.json()["round_id"]
                word = word_list[i % len(word_list)]
                auth_client.post(
                    f"/rounds/{round_id}/submit",
                    json={"phrase": word}
                )

            auth_client.close()

        # Check queue status
        auth_check, check_player = create_authenticated_client()

        availability = auth_check.get("/rounds/available").json()
        prompts_waiting = availability["prompts_waiting"]

        print(f"\n{prompts_waiting} prompts in queue after stress test")

        assert prompts_waiting > 0, "No prompts in queue"

        auth_check.close()


class TestDatabaseConsistency:
    """Test database consistency under concurrent operations."""

    def test_sequential_transaction_consistency(self, verify_server_running):
        """Test balance consistency with sequential operations."""
        # Create player
        auth_client, player_data = create_authenticated_client()
        initial_balance = player_data["balance"]

        # Start a prompt round
        round_response = auth_client.post("/rounds/prompt", json={})
        assert round_response.status_code == 200

        round_id = round_response.json()["round_id"]

        # Check balance was deducted
        balance_response = auth_client.get("/player/balance")
        assert balance_response.status_code == 200
        new_balance = balance_response.json()["balance"]

        expected_balance = initial_balance - 100  # One round at $100
        assert new_balance == expected_balance, \
            f"Balance mismatch: expected {expected_balance}, got {new_balance}"

        # Submit phrase to complete the round
        submit_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "happy"}
        )
        assert submit_response.status_code == 200

        # Verify can't start another round while one is active would be tested elsewhere
        # This test focuses on transaction consistency

        auth_client.close()


class TestLongRunningOperations:
    """Test system behavior with long-running scenarios."""

    def test_sequential_rounds(self, verify_server_running):
        """Test player completing many rounds sequentially."""
        auth_client, player_data = create_authenticated_client()

        words = [
            "happy", "joyful", "peaceful", "calm", "serene",
            "bright", "shining", "glowing", "radiant", "brilliant"
        ]

        successful_rounds = 0

        # Try to complete 10 sequential prompt rounds
        for i in range(min(10, len(words))):
            # Check if we have enough balance
            balance = auth_client.get("/player/balance").json()["balance"]
            if balance < 100:
                print(f"\nInsufficient balance after {i} rounds")
                break

            # Start round
            round_response = auth_client.post("/rounds/prompt", json={})
            if round_response.status_code != 200:
                print(f"\nCould not start round {i+1}: {round_response.status_code}")
                break

            round_id = round_response.json()["round_id"]

            # Submit phrase
            submit_response = auth_client.post(
                f"/rounds/{round_id}/submit",
                json={"phrase": words[i]}
            )

            if submit_response.status_code == 200:
                successful_rounds += 1
            else:
                print(f"\nSubmission failed: {submit_response.status_code}")
                break

            # Small delay between rounds
            time.sleep(0.1)

        print(f"\nCompleted {successful_rounds} sequential rounds")

        assert successful_rounds >= 9, "Should complete at least 9 rounds with $1000"

        auth_client.close()


class TestErrorRecovery:
    """Test system recovery from error conditions."""

    def test_recovery_from_invalid_submissions(self, verify_server_running):
        """Test system handles invalid submissions gracefully."""
        auth_client, player_data = create_authenticated_client()

        # Start prompt round
        round_response = auth_client.post("/rounds/prompt", json={})
        round_id = round_response.json()["round_id"]

        # Try multiple invalid submissions
        invalid_phrases = [
            "x",  # too short
            "verylongwordthatistoobig" * 10,  # too long (>100 chars)
            "test123",  # numbers
            "test-word",  # hyphen
        ]

        for phrase in invalid_phrases:
            response = auth_client.post(
                f"/rounds/{round_id}/submit",
                json={"phrase": phrase}
            )
            assert response.status_code == 422  # Changed from 400 to 422 for validation errors

        # Valid submission should still work
        valid_response = auth_client.post(
            f"/rounds/{round_id}/submit",
            json={"phrase": "happy"}
        )
        assert valid_response.status_code == 200

        auth_client.close()


if __name__ == "__main__":
    print("=" * 60)
    print("Quipflip Stress Tests")
    print("=" * 60)
    print("\nBackend must be running on http://localhost:8000/qf")
    print("Start: uvicorn backend.main:app --reload")
    print("\nRun: pytest tests/test_stress_localhost.py -v -s")
    print("=" * 60)
