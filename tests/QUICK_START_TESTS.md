# Quick Start: Localhost Integration Tests

Fast guide to running Quipflip integration tests.

## Prerequisites

**1. Start the backend server:**
```bash
uvicorn backend.main:app --reload
```

**2. Verify server is running:**
```bash
curl http://localhost:8000/qf/health
```

Expected response:
```json
{"status": "ok", "database": "connected", "redis": "memory"}
```

## Run Tests - Choose Your Method

### Method 1: Bash Script (Recommended for Unix/Mac)
```bash
# Run all tests
./run_localhost_tests.sh all

# Run specific test suite
./run_localhost_tests.sh integration
./run_localhost_tests.sh scenarios
./run_localhost_tests.sh stress

# Quick test (skip stress tests)
./run_localhost_tests.sh quick

# With verbose output
./run_localhost_tests.sh integration -s
```

### Method 2: Python Script (Cross-platform)
```bash
# Run all tests
python run_localhost_tests.py all

# Run specific test suite
python run_localhost_tests.py integration
python run_localhost_tests.py scenarios
python run_localhost_tests.py stress

# Quick test
python run_localhost_tests.py quick

# With verbose output
python run_localhost_tests.py integration -s
```

### Method 3: Direct pytest
```bash
# Run all integration tests
pytest tests/test_integration_localhost.py -v

# Run all scenario tests
pytest tests/test_game_scenarios_localhost.py -v

# Run all stress tests
pytest tests/test_stress_localhost.py -v

# Run specific test class
pytest tests/test_integration_localhost.py::TestPlayerManagement -v

# Run specific test
pytest tests/test_integration_localhost.py::TestPlayerManagement::test_create_player -v
```

## Test Files Overview

| File | Description | Tests |
|------|-------------|-------|
| `test_integration_localhost.py` | Core API integration tests | 35+ tests |
| `test_game_scenarios_localhost.py` | Real-world game flows | 25+ tests |
| `test_stress_localhost.py` | Load and performance tests | 10+ tests |
| `helpers_localhost.py` | Test utilities and helpers | N/A |

## What Gets Tested

### Core Features ✅
- Player creation & authentication
- API key rotation
- Balance tracking
- Daily bonus system
- Round creation (Prompt/Copy/Vote)
- Word submission & validation
- Complete game flows
- Queue management
- Copy discount system

### Edge Cases ✅
- Invalid inputs (short/long words, special chars)
- Insufficient balance
- Expired rounds
- Duplicate votes
- Concurrent operations
- One-round-at-a-time enforcement
- Cannot copy own prompt

### Performance ✅
- 100+ player creation
- Concurrent round operations
- Rate limiting
- Database consistency
- Long-running operations

## Expected Results

**Successful run:**
```
============================= test session starts ==============================
tests/test_integration_localhost.py::TestHealthEndpoints::test_health_check PASSED
tests/test_integration_localhost.py::TestPlayerManagement::test_create_player PASSED
...
============================== 50 passed in 15.23s ==============================
```

**If server not running:**
```
Cannot connect to backend server at http://localhost:8000/qf
Please start the server with: uvicorn backend.main:app --reload
```

## Troubleshooting

### Server Won't Start
```bash
# Check if port 8000 is in use
lsof -i :8000

# Kill process if needed
kill -9 <PID>

# Start server
uvicorn backend.main:app --reload
```

### Tests Fail
1. Check server logs in the terminal running uvicorn
2. Verify database is connected: `curl http://localhost:8000/qf/health`
3. Try restarting the server
4. Run tests with verbose output: `-vv -s`

### Database Issues
```bash
# Re-run migrations
alembic upgrade head

# Restart server with clean database
rm quipflip.db
alembic upgrade head
uvicorn backend.main:app --reload
```

## Common Commands

```bash
# Health check only
./run_localhost_tests.sh health

# Show all output including prints
pytest tests/test_integration_localhost.py -v -s

# Stop after first failure
pytest tests/test_integration_localhost.py --maxfail=1

# Run tests matching pattern
pytest tests/test_integration_localhost.py -k "player" -v

# Very verbose
pytest tests/test_integration_localhost.py -vv
```

## Test Data

- Tests create **real players** in the database
- Each test creates **new players** (no cleanup to preserve integrity)
- Tests **do not interfere** with each other
- Safe to run **multiple times**
- For clean slate: **restart server** with fresh database

## Performance Benchmarks

Typical performance on localhost:

| Operation | Time |
|-----------|------|
| Player creation | 50-100 ms |
| Round start | 50-150 ms |
| Word submission | 100-200 ms |
| Full game flow | 1-2 seconds |
| 100 players | 5-10 seconds |

## Next Steps

1. ✅ Start backend server
2. ✅ Run quick tests: `./run_localhost_tests.sh quick`
3. ✅ If all pass, run full suite: `./run_localhost_tests.sh all`
4. ✅ Check [README_LOCALHOST_TESTS.md](README_LOCALHOST_TESTS.md) for details

## Help

```bash
# Bash script help
./run_localhost_tests.sh help

# Python script help
python run_localhost_tests.py help

# Pytest help
pytest --help
```

## Resources

- **Detailed Documentation**: [README_LOCALHOST_TESTS.md](README_LOCALHOST_TESTS.md)
- **API Reference**: [../docs/API.md](../docs/API.md)
- **Game Rules**: [../README.md](../README.md)
- **Test Helpers**: [helpers_localhost.py](helpers_localhost.py)

---

**Happy Testing! 🚀**
