# Troubleshooting Integration Tests

## Common Issues and Solutions

### 1. Tests Fail with 500 Internal Server Error

**Symptom:**
```
assert response.status_code == 201
assert 500 == 201
```

**Cause:** Database connection or migration issue

**Solutions:**

#### A. Check Database Migrations
```bash
# Run pending migrations
alembic upgrade head

# Verify current migration
alembic current

# If migrations are out of sync, downgrade and re-upgrade
alembic downgrade -1
alembic upgrade head
```

#### B. Reset Database (SQLite)
```bash
# Backup existing database
cp quipflip.db quipflip.db.backup

# Remove database
rm quipflip.db

# Re-run migrations
alembic upgrade head

# Restart server
uvicorn backend.main:app --reload
```

#### C. Check Server Logs
The backend server terminal will show the actual error. Look for:
- Database connection errors
- SQLAlchemy errors
- Missing tables
- Foreign key constraint violations

#### D. Verify Database Connection
```python
# Test database connection
python3 -c "
from backend.database import engine
from backend.models.player import Player
import asyncio

async def test():
    async with engine.begin() as conn:
        await conn.execute('SELECT 1')
        print('Database connection OK')

asyncio.run(test())
"
```

### 2. Cannot Connect to Server

**Symptom:**
```
Cannot connect to backend server at http://localhost:8000/qf
```

**Solution:**
```bash
# Start the backend server
uvicorn backend.main:app --reload

# Verify it's running
curl http://localhost:8000/qf/health
```

### 3. Port Already in Use

**Symptom:**
```
ERROR: [Errno 48] Address already in use
```

**Solution:**
```bash
# Find process using port 8000
lsof -i :8000

# Kill the process
kill -9 <PID>

# Or use a different port
uvicorn backend.main:app --reload --port 8001

# Update BASE_URL in test files if using different port
```

### 4. Module Import Errors

**Symptom:**
```
ModuleNotFoundError: No module named 'helpers_localhost'
```

**Solution:**
```bash
# Ensure you're running from project root
cd /path/to/quipflip

# Run tests with proper path
pytest tests/test_integration_localhost.py -v

# Or add current directory to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:${PWD}"
```

### 5. Tests Hang or Timeout

**Symptom:**
Tests run forever without completing

**Causes & Solutions:**

#### A. Server Not Responding
```bash
# Check server health
curl -v http://localhost:8000/qf/health

# Restart server if needed
# Ctrl+C to stop
uvicorn backend.main:app --reload
```

#### B. Database Lock (SQLite)
```bash
# Kill any processes holding database lock
lsof quipflip.db

# Restart server
```

#### C. Increase Timeout
Edit test files and increase TIMEOUT:
```python
# In test files, change:
TIMEOUT = 10.0  # seconds

# To:
TIMEOUT = 30.0  # seconds
```

### 6. Word Validation Errors

**Symptom:**
```
Word validation failed - dictionary not loaded
```

**Solution:**
```bash
# Download NASPA word list
python3 scripts/download_dictionary.py

# Verify dictionary exists
ls -lh naspa_word_list.txt

# Restart server to reload dictionary
```

### 7. Tests Pass But Backend Shows Errors

**Symptom:**
Tests pass but server logs show errors

**This is OK if:**
- Tests are checking error conditions
- 400/401/404 errors are expected for negative tests
- Server recovers and continues

**This is NOT OK if:**
- 500 errors appear
- Database integrity errors
- Unhandled exceptions

Check server logs to verify errors are expected test cases.

### 8. Inconsistent Test Results

**Symptom:**
Tests pass sometimes, fail other times

**Causes & Solutions:**

#### A. Race Conditions
Add delays between operations:
```python
import time
time.sleep(0.5)  # Wait for queue/database
```

#### B. Database State
Some tests depend on database state. Reset database:
```bash
rm quipflip.db
alembic upgrade head
```

#### C. Queue State
Tests may compete for queue items. Run tests sequentially:
```bash
pytest tests/test_integration_localhost.py -v --maxfail=1
```

### 9. Permission Denied

**Symptom:**
```
Permission denied: 'quipflip.db'
```

**Solution:**
```bash
# Check file permissions
ls -l quipflip.db

# Fix permissions
chmod 644 quipflip.db

# Ensure parent directory is writable
chmod 755 .
```

### 10. Python Version Issues

**Symptom:**
```
SyntaxError or compatibility issues
```

**Solution:**
```bash
# Check Python version (need 3.9+)
python3 --version

# Use correct Python interpreter
python3.11 -m pytest tests/test_integration_localhost.py -v

# Or create virtual environment
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Debugging Steps

### Step 1: Verify Server Health
```bash
curl http://localhost:8000/qf/health
```

Expected:
```json
{"status": "ok", "database": "connected", "redis": "memory"}
```

### Step 2: Test Player Creation Manually
```bash
curl -X POST http://localhost:8000/qf/player
```

Expected:
```json
{
  "player_id": "...",
  "api_key": "...",
  "balance": 1000,
  "message": "..."
}
```

### Step 3: Check Database
```bash
# If using SQLite
sqlite3 quipflip.db "SELECT name FROM sqlite_master WHERE type='table';"

# Should show tables: players, prompts, rounds, phrasesets, votes, transactions, etc.
```

### Step 4: Run Single Test with Verbose Output
```bash
pytest tests/test_integration_localhost.py::TestHealthEndpoints::test_health_check -vv -s
```

### Step 5: Check Server Logs
Watch the terminal running `uvicorn` for detailed error messages

## Getting Help

If tests still fail after trying these solutions:

1. **Check Server Logs** - Most issues show detailed errors in uvicorn output
2. **Check Database State** - Verify migrations are current
3. **Try Fresh Database** - Reset and re-run migrations
4. **Check Dependencies** - Ensure all packages from requirements.txt are installed
5. **Verify Python Version** - Must be 3.9 or higher

## Quick Reset Procedure

When all else fails, complete reset:

```bash
# 1. Stop server (Ctrl+C)

# 2. Backup database
cp quipflip.db quipflip.db.backup

# 3. Remove database
rm quipflip.db

# 4. Re-run migrations
alembic upgrade head

# 5. Download dictionary if needed
python3 scripts/download_dictionary.py

# 6. Start server
uvicorn backend.main:app --reload

# 7. Wait 5 seconds

# 8. Run tests
./run_localhost_tests.sh health
```

If health checks pass, try full suite:
```bash
./run_localhost_tests.sh integration
```

## Expected Behavior

**Healthy System:**
- Health checks: 2/2 passing
- Player creation: Instant (50-100ms)
- Round operations: Fast (100-200ms)
- No 500 errors in server logs
- Database operations complete successfully

**System Issues:**
- 500 errors
- Timeouts
- Connection refused
- Database locked
- Missing tables

Check the specific error message and follow the troubleshooting steps above.
