# Quipflip Localhost Integration Tests

Comprehensive test suite for testing the Quipflip backend API running on localhost.

## Overview

This test suite assumes the backend server is **already running** on `http://localhost:8000/qf` and performs integration tests against the live API endpoints.

## Prerequisites

### 1. Start the Backend Server

```bash
# From project root
uvicorn backend.main:app --reload
```

The server should be running at http://localhost:8000/qf

### 2. Install Test Dependencies

All required dependencies should already be in `requirements.txt`:

```bash
pip install -r requirements.txt
```

Required packages:
- `pytest` - Test framework
- `httpx` - HTTP client for API requests
- `pytest-asyncio` - Async test support

## Test Files

### Core Integration Tests

**`test_integration_localhost.py`** - Main integration test suite
- Health check and info endpoints
- Player creation and management
- API key rotation
- Round availability checks
- Prompt round flow (creation and submission)
- Copy round flow
- Vote round flow
- Complete game flow (prompt → copies → votes)
- Edge cases and error conditions
- Data consistency checks
- Concurrent player operations

**Test Categories:**
- `TestHealthEndpoints` - Server health and status
- `TestPlayerManagement` - Player accounts and authentication
- `TestRoundAvailability` - Round queue status
- `TestPromptRoundFlow` - Prompt round lifecycle
- `TestCopyRoundFlow` - Copy round lifecycle
- `TestVoteRoundFlow` - Voting lifecycle
- `TestCompleteGameFlow` - End-to-end game scenarios
- `TestEdgeCases` - Error handling and validation
- `TestDataConsistency` - Balance and transaction tracking
- `TestConcurrency` - Multiple concurrent players

### Stress & Load Tests

**`test_stress_localhost.py`** - Performance and stress testing
- High-volume player creation (100+ players)
- Concurrent round operations
- Rate limiting behavior
- Queue system under load
- Database consistency under concurrent operations
- Long-running sequential operations
- Error recovery scenarios

**Test Categories:**
- `TestHighVolumePlayerCreation` - Bulk player creation
- `TestConcurrentRounds` - Simultaneous operations
- `TestRateLimiting` - Rate limit testing
- `TestQueueStress` - Queue capacity testing
- `TestDatabaseConsistency` - Concurrent transaction safety
- `TestLongRunningOperations` - Sequential game progression
- `TestErrorRecovery` - Graceful error handling

### Real-World Scenarios

**`test_game_scenarios_localhost.py`** - Realistic game flow testing
- Single player journey
- Two-player interactions
- Complete phraseset creation (3 players)
- Multiple voters on same phraseset
- Balance tracking accuracy
- Queue dynamics and copy discounts
- Edge cases and error scenarios

**Test Categories:**
- `TestSinglePlayerJourney` - New player experience
- `TestTwoPlayerInteraction` - Player-to-player scenarios
- `TestThreePlayerWordset` - Full wordset creation
- `TestVotingScenarios` - Voting behavior
- `TestEdgeCasesAndErrors` - Error handling
- `TestBalanceTracking` - Financial accuracy
- `TestQueueDynamics` - Queue system behavior

### Helper Utilities

**`helpers_localhost.py`** - Test utilities and helpers
- `APIClient` - Enhanced HTTP client with authentication
- `Player` - Player data container
- `PlayerFactory` - Create test players easily
- `GameFlowHelper` - Common game operations (start/submit rounds)
- `WordGenerator` - Generate valid/invalid test words
- `AssertionHelper` - Common assertion patterns
- Utility functions for cleanup and server verification

## Running Tests

### Run All Localhost Tests

```bash
# From project root
pytest tests/test_integration_localhost.py tests/test_stress_localhost.py tests/test_game_scenarios_localhost.py -v
```

### Run Specific Test File

```bash
# Integration tests only
pytest tests/test_integration_localhost.py -v

# Stress tests only
pytest tests/test_stress_localhost.py -v

# Scenario tests only
pytest tests/test_game_scenarios_localhost.py -v
```

### Run Specific Test Class

```bash
# Test only player management
pytest tests/test_integration_localhost.py::TestPlayerManagement -v

# Test only voting scenarios
pytest tests/test_game_scenarios_localhost.py::TestVotingScenarios -v
```

### Run Specific Test Method

```bash
# Test single specific test
pytest tests/test_integration_localhost.py::TestPlayerManagement::test_create_player -v
```

### Run with Output Capture

```bash
# Show print statements during tests
pytest tests/test_stress_localhost.py -v -s

# Show detailed test output
pytest tests/test_integration_localhost.py -vv
```

### Run with Coverage

```bash
# Run with coverage report (requires pytest-cov)
pip install pytest-cov
pytest tests/test_integration_localhost.py --cov=backend --cov-report=html
```

## Test Patterns

### Using Helper Utilities

```python
from helpers_localhost import PlayerFactory, GameFlowHelper, WordGenerator

# Create a player easily
player, client = PlayerFactory.create_player()

# Complete a full prompt round
word = WordGenerator.get_word()
round_id, result = GameFlowHelper.complete_prompt_round(client, word)

# Clean up
client.close()
```

### Testing Error Cases

```python
from helpers_localhost import WordGenerator, AssertionHelper

# Test invalid word submission
invalid_word = WordGenerator.get_invalid_word("short")
response = client.post(f"/rounds/{round_id}/submit", json={"word": invalid_word})
AssertionHelper.assert_error_response(response, 400)
```

### Testing Concurrent Operations

```python
import concurrent.futures

def start_round(api_key):
    client = APIClient(api_key)
    return client.post("/rounds/prompt", json={})

# Run multiple operations concurrently
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = [executor.submit(start_round, key) for key in api_keys]
    results = [future.result() for future in futures]
```

## Expected Test Results

### Successful Test Run

When all tests pass, you should see:
```
============================= test session starts ==============================
collected 50 items

tests/test_integration_localhost.py::TestHealthEndpoints::test_health_check PASSED
tests/test_integration_localhost.py::TestHealthEndpoints::test_root_endpoint PASSED
tests/test_integration_localhost.py::TestPlayerManagement::test_create_player PASSED
...

============================== 50 passed in 15.23s ==============================
```

### Common Test Failures

**Server Not Running**
```
Cannot connect to backend server at http://localhost:8000/qf
Please start the server with: uvicorn backend.main:app --reload
```
→ Start the backend server

**Server Unhealthy**
```
Server is running but returned status 500
```
→ Check server logs and database connection

**No Prompts/Wordsets Available**
```
No prompts available
```
→ This is expected if queue is empty; tests handle this gracefully

## Test Data Considerations

### Database State

- Tests create real data in the database
- Each test creates new players (no cleanup to preserve data integrity)
- Tests are designed to work with existing data in queues
- For a clean slate, restart the server with a fresh database

### Test Isolation

- Each test creates its own player(s)
- Tests do not interfere with each other
- Safe to run in parallel with pytest-xdist (if installed)

### Queue Dependencies

Some tests depend on queue state:
- **Copy round tests** require prompts in queue
- **Vote round tests** require complete phrasesets
- Tests handle missing queue items gracefully (skip or create necessary setup)

## Performance Benchmarks

Expected performance on localhost:

- **Player creation**: ~50-100 ms per player
- **Round start**: ~50-150 ms
- **Word submission**: ~100-200 ms
- **100 players**: ~5-10 seconds
- **Complete game flow**: ~1-2 seconds

*Note: Times vary based on system performance and database speed*

## Debugging Tests

### Verbose Output

```bash
# Show all output including print statements
pytest tests/test_integration_localhost.py -vv -s
```

### Run Single Test for Debugging

```bash
# Run one test with full output
pytest tests/test_integration_localhost.py::TestPlayerManagement::test_create_player -vv -s
```

### Check Server Logs

While running tests, monitor server logs:
```bash
# Server terminal will show all API requests
# Look for errors or unexpected behavior
```

### Using pytest Markers (Optional)

You can add custom markers to run subsets:

```python
@pytest.mark.slow
def test_long_running():
    ...

# Run only fast tests
pytest -v -m "not slow"
```

## Troubleshooting

### Tests Fail Due to Balance Issues

Some tests require sufficient balance. If tests fail after many rounds:
- Restart server with fresh database
- Tests create new players for each scenario

### Connection Timeouts

If tests timeout:
- Check server is responsive: `curl http://localhost:8000/qf/health`
- Increase timeout in test files (TIMEOUT constant)
- Check system resources (database, Redis)

### Inconsistent Test Results

If tests pass/fail randomly:
- Check for race conditions in concurrent tests
- Ensure adequate sleep delays between operations
- Verify database transaction isolation

### Rate Limiting

If you hit rate limits:
- Tests respect rate limits (100 req/min)
- Add delays between test runs
- Restart server to reset rate limits

## Continuous Integration

### CI Configuration Example

```yaml
# .github/workflows/integration-tests.yml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: alembic upgrade head
      - run: uvicorn backend.main:app &
      - run: sleep 5  # Wait for server
      - run: pytest tests/test_integration_localhost.py -v
```

## Contributing

When adding new tests:

1. Follow existing patterns in test files
2. Use helper utilities from `helpers_localhost.py`
3. Add descriptive docstrings
4. Handle graceful failures (no prompts, no phrasesets, etc.)
5. Clean up resources (close clients)
6. Test both success and failure cases

## Additional Resources

- **API Documentation**: [docs/API.md](../docs/API.md)
- **Architecture**: [docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md)
- **Game Rules**: [README.md](../README.md)
- **Backend Tests**: [tests/test_game_flow.py](test_game_flow.py) (unit tests)

## Quick Start Checklist

- [ ] Start backend server: `uvicorn backend.main:app --reload`
- [ ] Verify health: `curl http://localhost:8000/qf/health`
- [ ] Run tests: `pytest tests/test_integration_localhost.py -v`
- [ ] Check results and server logs
- [ ] Optional: Run stress tests for performance analysis

---

**Happy Testing! 🧪**

For questions or issues, refer to the main project documentation or check server logs for debugging information.
