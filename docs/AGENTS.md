# AGENTS.md - AI Agent Instructions for Quipflip

This document provides comprehensive guidance for AI agents working with the Quipflip codebase, a multiplayer phrase association game with monetary stakes.

## 🎯 Quick Overview

**Quipflip** is a three-phase multiplayer game:
1. **Prompt Round** (100f cost) - Submit phrases for creative prompts
2. **Copy Round** (100f/90f cost) - Submit similar phrases without seeing the prompt
3. **Vote Round** (1f cost) - Identify the original phrase from three options

Players compete for prize pools split based on vote performance. The system uses Flipcoins (f) as in-game currency.

## 📁 Project Structure

```
quipflip/
├── backend/              # FastAPI + SQLAlchemy backend
│   ├── main.py           # ASGI entrypoint
│   ├── routers/          # API endpoints (players, rounds, phrasesets, quests)
│   ├── services/         # Business logic layer
│   ├── models/           # SQLAlchemy ORM models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── utils/            # Shared utilities and helpers
│   └── migrations/       # Alembic database migrations
├── frontend/             # React + TypeScript frontend
├── docs/                 # Comprehensive documentation
├── tests/                # Pytest test suites
└── scripts/             # Utility scripts
```

## 🔧 Tech Stack

**Backend:**
- **Framework**: FastAPI (async Python)
- **Database**: PostgreSQL (prod) / SQLite (dev)
- **ORM**: SQLAlchemy (async)
- **Auth**: JWT access + refresh tokens
- **Validation**: Pydantic + NASPA dictionary + sentence-transformers

**Frontend:**
- **Framework**: React 18 + TypeScript
- **Build**: Vite
- **Styling**: Tailwind CSS
- **State**: React Context API
- **HTTP**: Axios with auto-retry

## 🏗️ Architecture Patterns

### Service Layer Pattern
Business logic is centralized in service classes:

```python
# Example: RoundService handles all round operations
from backend.services.round_service import RoundService
from backend.services.transaction_service import TransactionService

round_service = RoundService(db_session)
transaction_service = TransactionService(db_session)

# Start a prompt round
round_obj = await round_service.start_prompt_round(
    player, transaction_service
)
```

### Denormalized Data Pattern
Phrasesets store copies of source data for performance:

```python
# Phraseset model includes denormalized fields
class Phraseset:
    # Denormalized (copied from rounds)
    prompt_text = Column(String(500))
    original_phrase = Column(String(100))
    copy_phrase_1 = Column(String(100))
    
    # Relationships to source data
    prompt_round = relationship("Round", foreign_keys=[prompt_round_id])
```

### Configuration Management
All game balance settings centralized in `backend/config.py`:

```python
# Game economics
prompt_cost: int = 100
copy_cost_normal: int = 100
copy_cost_discount: int = 90
vote_cost: int = 1
vote_payout_correct: int = 5

# Timing
prompt_round_seconds: int = 180
copy_round_seconds: int = 180
vote_round_seconds: int = 60
```

## 🎮 Core Game Mechanics

### Round Lifecycle State Machine

```
START ROUND → "active" → SUBMIT PHRASE → "submitted" → QUEUE
                ↓
           TIMER EXPIRES → "abandoned" (penalty applied)
```

### Voting Timeline State Machine

```
PHRASESET CREATED → "open" (0-2 votes)
    ↓
3RD VOTE → "open" (10-minute window)
    ↓
5TH VOTE OR 10 MIN → "closing" (60-second final window)
    ↓
20TH VOTE OR TIMEOUT → "closed" → CALCULATE PAYOUTS → "finalized"
```

### Anti-Cheat Enforcement
- One round at a time per player
- Players cannot vote on own phrasesets
- 10 outstanding prompts limit per player
- Duplicate submission prevention
- Grace period for network latency

## 💰 Economics System

### Currency
- **Flipcoins (f)**: In-game currency
- **Starting balance**: 5000f
- **Daily bonus**: 100f (after first day)

### Costs & Payouts
- **Prompt round**: 100f (90f refunded on timeout)
- **Copy round**: 100f normal, 90f with discount
- **Vote round**: 1f
- **Correct vote**: +5f gross (+4f net)
- **Prize pools**: Split proportionally by votes received

### Copy Discount System
When >10 prompts waiting:
- Copy cost drops to 90f
- System contributes 10f to maintain 300f prize pool

## 🔍 Phrase Validation Rules

### Format Requirements
- **Length**: 4-100 characters total
- **Words**: 1-5 words (2-15 chars each)
- **Characters**: Letters A-Z and spaces only
- **Dictionary**: NASPA word list validation

### Similarity Detection
- **Copy validation**: Must differ from original (cosine similarity < 0.80)
- **Model**: all-mpnet-base-v2 (sentence-transformers)
- **Threshold**: Configurable via `similarity_threshold` setting

### Special Cases
- Connecting words ("a", "an", "the", "I") always allowed
- Case-insensitive input, stored uppercase
- Exact duplicates rejected with retry opportunity

## 🛠️ Development Workflows

### Backend Development

**Start Development Environment:**
```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn backend.main:app --reload
```

**Testing:**
```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_round_service.py -v

# Run integration tests (requires running server)
pytest tests/test_integration_localhost.py -v
```

### Frontend Development

**Start Development:**
```bash
cd frontend
npm install
npm run dev -- --host
```

**Key Files:**
- `src/contexts/GameContext.tsx` - Global state management
- `src/api/client.ts` - API client with auto-retry
- `src/pages/` - Route components (Dashboard, PromptRound, etc.)

## 📊 Database Models

### Key Tables
- **players** - User accounts, balances, tutorial progress
- **rounds** - All round types (prompt/copy/vote) with nullable fields
- **phrasesets** - Groups of 3 phrases ready for voting
- **votes** - Individual vote records
- **transactions** - Financial audit trail
- **quests** - Achievement system (16 quest types)

### Important Relationships
```python
# One player can have one active round
Player.active_round_id → Round.round_id

# Phrasesets reference source rounds
Phraseset.prompt_round_id → Round.round_id
Phraseset.copy_round_1_id → Round.round_id

# Votes link to phrasesets and players
Vote.phraseset_id → Phraseset.phraseset_id
Vote.player_id → Player.player_id
```

## 🧪 Testing Patterns

### Unit Tests
Focus on service layer business logic:

```python
@pytest.mark.asyncio
async def test_start_prompt_round_success(db_session, player_with_balance):
    round_service = RoundService(db_session)
    transaction_service = TransactionService(db_session)
    
    round_obj = await round_service.start_prompt_round(
        player_with_balance, transaction_service
    )
    
    assert round_obj.status == "active"
    assert player_with_balance.balance == 900  # 1000 - 100
```

### Integration Tests
Test complete API workflows:

```python
def test_complete_prompt_round(verify_server):
    client = create_authenticated_client()
    
    # Start round
    response = client.post("/rounds/prompt")
    round_id = response.json()["round_id"]
    
    # Submit phrase
    response = client.post(f"/rounds/{round_id}/submit", 
                          json={"phrase": "CELEBRATION"})
    assert response.status_code == 200
```

### Game Flow Helpers
Use test helpers for complex scenarios:

```python
from tests.helpers_localhost import GameFlowHelper

# Complete a full prompt round
round_id, result = GameFlowHelper.complete_prompt_round(client, "HAPPY")

# Create a phraseset with 3 players
GameFlowHelper.create_complete_phraseset(client1, client2, client3)
```

## 🔐 Authentication System

### JWT Tokens
- **Access tokens**: 15-minute expiry, stored in localStorage
- **Refresh tokens**: 30-day expiry, HTTP-only cookies
- **Auto-refresh**: Client automatically refreshes on 401 errors

### API Client Pattern
```typescript
// Frontend API client with auto-retry
const response = await apiClient.startPromptRound();
// Automatically handles token refresh and retries
```

## 🚨 Error Handling Patterns

### Backend Exceptions
```python
from backend.utils.exceptions import (
    RoundExpiredError,
    InsufficientBalanceError,
    InvalidPhraseError
)

# Service methods raise specific exceptions
if round.expires_at < datetime.now(UTC):
    raise RoundExpiredError("Round has expired")
```

### Frontend Error Processing
```typescript
// Extract user-friendly error messages
import { extractErrorMessage } from '../api/client';

try {
    await apiClient.startPromptRound();
} catch (err) {
    const message = extractErrorMessage(err);
    setError(message); // Shows to user
}
```

## 🎯 Common Development Tasks

### Adding New Configuration
1. Add setting to `backend/config.py`
2. Update Admin panel in `frontend/src/pages/Admin.tsx`
3. Add to database override system if needed
4. Test in `tests/test_game_balance.py`

### Adding New API Endpoint
1. Create schema in `backend/schemas/`
2. Add endpoint to appropriate router in `backend/routers/`
3. Implement business logic in `backend/services/`
4. Add frontend client method in `frontend/src/api/client.ts`
5. Write tests in `tests/`

### Modifying Game Economics
1. Update settings in `backend/config.py`
2. Modify transaction logic in `services/transaction_service.py`
3. Update UI displays in frontend
4. Test economic calculations thoroughly

## 📈 Performance Considerations

### Database Optimization
- Use async SQLAlchemy throughout
- Leverage selectinload() for relationships
- Index frequently queried fields
- Denormalize for read performance

### Frontend Optimization
- Polling strategy: 60s for balance, 90s for results
- Request cancellation with AbortController
- Optimistic UI updates where appropriate
- Lazy loading for non-critical data

## 🔍 Debugging Tips

### Backend Debugging
```python
# Enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)

# Check configuration
from backend.config import get_settings
settings = get_settings()
print(f"Prompt cost: {settings.prompt_cost}")

# Inspect database state
from backend.database import get_db
async with get_db() as db:
    result = await db.execute("SELECT * FROM players LIMIT 5")
```

### Frontend Debugging
```typescript
// GameContext includes extensive logging
const { state } = useGame();
console.log('Current state:', state);

// Check API responses in Network tab
// Monitor React Context in React DevTools
// Verify localStorage for tokens
```

### Common Issues
1. **"No prompts available"** - Check prompt queue or create test prompts
2. **Balance discrepancies** - Verify transaction audit trail
3. **Timer issues** - Check system clock and timezone handling
4. **Authentication failures** - Verify JWT tokens and refresh logic

## 📚 Essential Documentation

**For Game Understanding:**
- `README.md` - Complete game rules and quick start
- `docs/ARCHITECTURE.md` - Technical architecture overview
- `docs/API.md` - Complete REST API reference

**For Development:**
- `docs/DATA_MODELS.md` - Database schema reference
- `docs/FRONTEND_PLAN.md` - Frontend implementation guide
- `frontend/README.md` - Frontend-specific documentation

**For Features:**
- `docs/TUTORIAL_IMPLEMENTATION.md` - Tutorial system guide
- `docs/AI_SERVICE.md` - AI backup service documentation
- `docs/ADMIN_PLAN.md` - Admin panel features

**For Testing:**
- `tests/QUICK_START_TESTS.md` - Testing quick start guide
- `docs/TEST_REPORT.md` - Comprehensive test results

## 🎮 Game Context for Agents

### Player Personas
- **Prompt Players**: Creative writers who enjoy crafting prompts
- **Copy Players**: Strategic players who try to blend in
- **Voters**: Analytical players who identify originals
- **Mixed Players**: Play all three roles for variety

### Economic Balance
- System designed for slight positive expected value
- Rake comes from vote entry fees (1f per vote)
- Prize pools funded by round entry fees (300f total)
- Daily bonuses prevent player bankruptcy

### Engagement Hooks
- Real money stakes create engagement
- Progressive difficulty through vote competition
- Social elements via pseudonym system
- Achievement system with 16 quest types

## 🔄 State Management Patterns

### Backend State
- Database as single source of truth
- Services manage state transitions
- Transactions ensure consistency
- Queue states tracked in real-time

### Frontend State
```typescript
// GameContext provides centralized state
const { state, actions } = useGame();

// Key state elements
state.player.balance          // Current balance
state.activeRound            // Current round if any
state.roundAvailability      // What rounds can be started
state.pendingResults         // Unviewed results count
```

## 🎨 UI/UX Patterns

### Color Coding
- **Prompt rounds**: Blue theme
- **Copy rounds**: Green theme  
- **Vote rounds**: Purple theme
- **Success**: Green notifications
- **Errors**: Red notifications
- **Warnings**: Yellow/orange

### Responsive Design
- Mobile-first Tailwind CSS approach
- Touch-friendly button sizes (min 44px)
- Collapsible navigation for mobile
- Readable text at all screen sizes

## 💡 Tips for Agents

### When Modifying Game Logic
1. **Always consider economic impact** - Changes affect player earnings
2. **Test edge cases thoroughly** - Money is involved, bugs are costly
3. **Check transaction consistency** - Audit trail must be complete
4. **Verify timing behavior** - Grace periods and timeouts are critical

### When Adding Features
1. **Follow existing patterns** - Service layer, schemas, tests
2. **Consider mobile experience** - Most players are on mobile
3. **Add comprehensive logging** - Debugging is easier with good logs
4. **Plan for scale** - Queue systems handle concurrent users

### When Debugging Issues
1. **Check the audit trail** - Transaction logs show money flow
2. **Verify timer logic** - Many issues relate to timing
3. **Test authentication flow** - Token refresh can cause subtle bugs
4. **Monitor queue states** - Game depends on healthy queues

---

*This guide provides the essential context for working with Quipflip. For detailed implementation, consult the specific documentation files referenced throughout.*