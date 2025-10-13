"""
Helper utilities for localhost integration tests.

Provides common functionality for test setup, teardown, and data generation.
"""
import httpx
import random
import string
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

BASE_URL = "http://localhost:8000"
TIMEOUT = 10.0


@dataclass
class Player:
    """Player data container."""
    player_id: str
    api_key: str
    balance: int

    @classmethod
    def from_response(cls, data: dict) -> 'Player':
        """Create Player from API response."""
        return cls(
            player_id=data["player_id"],
            api_key=data["api_key"],
            balance=data.get("balance", 1000)
        )


class APIClient:
    """Enhanced HTTP client for WordPool API."""

    def __init__(self, api_key: Optional[str] = None, base_url: str = BASE_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.Client(base_url=base_url, timeout=TIMEOUT)

    def headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers

    def get(self, path: str, **kwargs):
        """Make authenticated GET request."""
        return self.client.get(path, headers=self.headers(), **kwargs)

    def post(self, path: str, **kwargs):
        """Make authenticated POST request."""
        return self.client.post(path, headers=self.headers(), **kwargs)

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


class PlayerFactory:
    """Factory for creating test players."""

    @staticmethod
    def create_player() -> Tuple[Player, APIClient]:
        """
        Create a new player and return player data with authenticated client.

        Returns:
            Tuple of (Player, APIClient)
        """
        with APIClient() as client:
            response = client.post("/player")
            if response.status_code != 201:
                raise Exception(f"Failed to create player: {response.status_code}")

            player = Player.from_response(response.json())

        # Return new authenticated client
        auth_client = APIClient(api_key=player.api_key)
        return player, auth_client

    @staticmethod
    def create_players(count: int) -> List[Tuple[Player, APIClient]]:
        """
        Create multiple players.

        Args:
            count: Number of players to create

        Returns:
            List of (Player, APIClient) tuples
        """
        return [PlayerFactory.create_player() for _ in range(count)]


class GameFlowHelper:
    """Helper for common game flow operations."""

    @staticmethod
    def start_prompt_round(client: APIClient) -> dict:
        """Start a prompt round and return response data."""
        response = client.post("/rounds/prompt", json={})
        if response.status_code != 200:
            raise Exception(f"Failed to start prompt: {response.status_code} - {response.text}")
        return response.json()

    @staticmethod
    def submit_word(client: APIClient, round_id: str, word: str) -> dict:
        """Submit word/phrase to a round."""
        response = client.post(f"/rounds/{round_id}/submit", json={"phrase": word})
        if response.status_code != 200:
            raise Exception(f"Failed to submit word: {response.status_code} - {response.text}")
        return response.json()

    @staticmethod
    def complete_prompt_round(client: APIClient, word: str) -> Tuple[str, dict]:
        """
        Start and complete a prompt round.

        Returns:
            Tuple of (round_id, submission_response)
        """
        prompt_data = GameFlowHelper.start_prompt_round(client)
        round_id = prompt_data["round_id"]
        submit_data = GameFlowHelper.submit_word(client, round_id, word)
        return round_id, submit_data

    @staticmethod
    def start_copy_round(client: APIClient) -> dict:
        """Start a copy round and return response data."""
        response = client.post("/rounds/copy", json={})
        if response.status_code != 200:
            raise Exception(f"Failed to start copy: {response.status_code} - {response.text}")
        return response.json()

    @staticmethod
    def complete_copy_round(client: APIClient, word: str) -> Tuple[str, dict]:
        """
        Start and complete a copy round.

        Returns:
            Tuple of (round_id, submission_response)
        """
        copy_data = GameFlowHelper.start_copy_round(client)
        round_id = copy_data["round_id"]
        submit_data = GameFlowHelper.submit_word(client, round_id, word)
        return round_id, submit_data

    @staticmethod
    def start_vote_round(client: APIClient) -> dict:
        """Start a vote round and return response data."""
        response = client.post("/rounds/vote", json={})
        if response.status_code != 200:
            raise Exception(f"Failed to start vote: {response.status_code} - {response.text}")
        return response.json()

    @staticmethod
    def submit_vote(client: APIClient, wordset_id: str, word: str) -> dict:
        """Submit vote for a phraseset."""
        # Changed endpoint from wordsets to phrasesets
        response = client.post(f"/phrasesets/{wordset_id}/vote", json={"phrase": word})
        if response.status_code != 200:
            raise Exception(f"Failed to vote: {response.status_code} - {response.text}")
        return response.json()

    @staticmethod
    def complete_vote_round(client: APIClient, word: str) -> Tuple[str, dict]:
        """
        Start and complete a vote round.

        Returns:
            Tuple of (phraseset_id, vote_response)
        """
        vote_data = GameFlowHelper.start_vote_round(client)
        phraseset_id = vote_data["phraseset_id"]  # Changed from wordset_id to phraseset_id
        submit_data = GameFlowHelper.submit_vote(client, phraseset_id, word)
        return phraseset_id, submit_data


class WordGenerator:
    """Generate valid test words."""

    # Common valid words for testing
    WORDS = [
        "happy", "joyful", "peaceful", "calm", "serene",
        "bright", "shining", "glowing", "radiant", "brilliant",
        "beautiful", "wonderful", "amazing", "fantastic", "incredible",
        "creative", "clever", "smart", "wise", "insightful",
        "strong", "brave", "bold", "fierce", "mighty",
        "gentle", "kind", "caring", "loving", "tender",
        "quick", "fast", "rapid", "swift", "speedy",
        "quiet", "silent", "hushed", "still", "tranquil",
    ]

    @staticmethod
    def get_word() -> str:
        """Get a random valid word."""
        return random.choice(WordGenerator.WORDS)

    @staticmethod
    def get_words(count: int, unique: bool = True) -> List[str]:
        """
        Get multiple words.

        Args:
            count: Number of words to return
            unique: If True, ensure all words are different

        Returns:
            List of words
        """
        if unique and count > len(WordGenerator.WORDS):
            raise ValueError(f"Cannot generate {count} unique words (max: {len(WordGenerator.WORDS)})")

        if unique:
            return random.sample(WordGenerator.WORDS, count)
        else:
            return [random.choice(WordGenerator.WORDS) for _ in range(count)]

    @staticmethod
    def get_invalid_word(reason: str = "short") -> str:
        """
        Get an invalid word for testing error cases.

        Args:
            reason: Type of invalid word ('short', 'long', 'numbers', 'special')

        Returns:
            Invalid word string
        """
        if reason == "short":
            return "x"
        elif reason == "long":
            return "verylongwordthatexceedsmaximumlength"
        elif reason == "numbers":
            return "test123"
        elif reason == "special":
            return "test-word"
        else:
            return "x"


class AssertionHelper:
    """Common assertions for API responses."""

    @staticmethod
    def assert_round_response(data: dict, round_type: str):
        """Assert common round response fields."""
        assert "round_id" in data, "Missing round_id"
        assert "expires_at" in data, "Missing expires_at"

        # Vote rounds don't include cost in response
        if round_type != "vote":
            assert "cost" in data, "Missing cost"

        if round_type == "prompt":
            assert "prompt_text" in data, "Missing prompt_text"
        elif round_type == "copy":
            assert "original_phrase" in data, "Missing original_phrase"  # Changed from original_word
        elif round_type == "vote":
            assert "phraseset_id" in data, "Missing phraseset_id"  # Changed from wordset_id
            assert "phrases" in data, "Missing phrases"  # Changed from words
            assert len(data["phrases"]) == 3, "Vote should have 3 phrases"

    @staticmethod
    def assert_balance_response(data: dict):
        """Assert balance response structure."""
        assert "balance" in data
        assert "starting_balance" in data
        assert "daily_bonus_available" in data
        assert "daily_bonus_amount" in data
        assert "outstanding_prompts" in data
        assert data["starting_balance"] == 1000

    @staticmethod
    def assert_error_response(response: httpx.Response, expected_status: int):
        """Assert error response format."""
        assert response.status_code == expected_status
        data = response.json()
        assert "detail" in data, "Error response should have 'detail' field"

    @staticmethod
    def assert_vote_result(data: dict):
        """Assert vote result structure."""
        assert "correct" in data
        assert isinstance(data["correct"], bool)
        assert "payout" in data
        assert "original_phrase" in data  # Changed from original_word to original_phrase
        assert "your_choice" in data


def cleanup_clients(*clients: APIClient):
    """Close multiple API clients."""
    for client in clients:
        if client:
            client.close()


def verify_server_is_running() -> bool:
    """
    Check if the backend server is running.

    Returns:
        True if server is running and healthy, False otherwise
    """
    try:
        with APIClient() as client:
            response = client.get("/health")
            return response.status_code == 200
    except Exception:
        return False


def get_server_info() -> dict:
    """
    Get server information from root endpoint.

    Returns:
        Server info dict
    """
    with APIClient() as client:
        response = client.get("/")
        return response.json() if response.status_code == 200 else {}


def wait_for_server(timeout: int = 10, interval: float = 0.5) -> bool:
    """
    Wait for server to become available.

    Args:
        timeout: Maximum seconds to wait
        interval: Check interval in seconds

    Returns:
        True if server became available, False if timeout
    """
    import time
    elapsed = 0
    while elapsed < timeout:
        if verify_server_is_running():
            return True
        time.sleep(interval)
        elapsed += interval
    return False
