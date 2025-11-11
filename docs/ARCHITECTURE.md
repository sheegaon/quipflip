# Technical Architecture and Overview

## System Overview

Quipflip is a FastAPI-based backend service with a stateless REST API architecture. The backend maintains all game state while the frontend is a presentation layer.

## Project Structure

```
repo/
├── backend/              # FastAPI application, SQLAlchemy models, and services
│   ├── main.py           # ASGI entrypoint
│   ├── routers/          # Route modules (players, rounds, phrasesets, quests, feedback, health)
│   ├── services/         # Business logic (rounds, votes, phrasesets, players, quests)
│   ├── models/           # ORM models (Player, Round, Phraseset, Quest, etc.)
│   ├── schemas/          # Pydantic request/response schemas
│   ├── utils/            # Queue/lock abstractions, JSON encoders, helpers
│   └── migrations/       # Alembic migrations
├── frontend/             # React + TypeScript client (Vite powered)
├── docs/                 # Architecture, API, data model, and planning docs
├── scripts/              # Utilities (e.g., dictionary download)
├── tests/                # Pytest suites (integration coverage)
└── requirements.txt      # Backend dependencies
```

The backend is designed around a clear service layer (`backend/services`) that encapsulates database access and business rules. Routers perform authentication and validation before delegating to services. Shared infrastructure concerns (queues, distributed locks, JSON encoding) live in `backend/utils`. The React frontend consumes the documented API but remains optional for backend development.

### Technology Stack
- **Framework**: FastAPI (async Python web framework)
- **Database**: PostgreSQL (production) / SQLite (development)
- **ORM**: SQLAlchemy (async)
- **Authentication**: JWT access tokens with refresh token rotation
- **Validation**: Pydantic schemas + NASPA word dictionary + sentence-transformers similarity
- **Queueing & Locks**: Redis-backed when available with in-memory/threaded fallback

### Authentication

JWT authentication using HTTP-only cookies for enhanced security:
- **Access tokens** (2-hour lifetime): Stored in HTTP-only cookie, automatically sent with requests
- **Refresh tokens** (30-day lifetime): Stored in HTTP-only cookie, used for automatic token rotation
- **Cookie security**: HttpOnly, Secure (production), SameSite=Lax
- **REST API**: Proxied through Vercel for same-origin (HttpOnly cookies work)
- **WebSocket**: Token exchange pattern (Vercel doesn't support WebSocket proxying)
- **iOS compatibility**: Same-origin REST requests work reliably on iOS Safari
- **Automatic refresh**: Frontend intercepts 401 errors and silently refreshes tokens
- **Backward compatibility**: Authorization header still supported for API clients

**Production Setup:**
- Frontend: Vercel hosting at `quipflip.xyz`
- Backend: Heroku at `quipflip-c196034288cd.herokuapp.com`
- REST API: Vercel proxy (`/api/*` → Heroku) for same-origin
- WebSocket: Token exchange via `/auth/ws-token` + direct connection to Heroku

**WebSocket Token Exchange Pattern:**
1. Frontend calls `/api/auth/ws-token` (REST via Vercel proxy with HttpOnly cookie)
2. Backend validates cookie and returns short-lived token (60 seconds)
3. Frontend uses token for direct WebSocket connection to Heroku
4. Short lifetime limits security risk if token is exposed

See [API.md](API.md) for complete authentication documentation including:
- Cookie-based authentication (preferred)
- Authorization header format (`Authorization: Bearer <token>`) - fallback for API clients
- Credential-based login (`POST /auth/login`)
- Refresh token endpoint (`POST /auth/refresh`)
- Automatic token refresh on expiration

### WebSocket Architecture

**Online Users Feature** (`/online/ws` endpoint):

The WebSocket implementation provides real-time updates for the "Who's Online" feature, showing players which users are currently active.

**Key Components:**
- **Connection Manager**: Centralized manager tracks all active WebSocket connections
- **Background Broadcast Task**: Automatically broadcasts online users updates every 5 seconds
- **User Activity Tracking**: `UserActivity` model tracks last action and timestamp for each player

**Connection Lifecycle:**
1. Client requests WebSocket connection with token (query param or cookie)
2. Server authenticates token before accepting connection
3. Unauthenticated connections rejected with WebSocket code 1008
4. First connection starts background broadcast task
5. Last disconnection stops background broadcast task

**Efficiency Optimizations:**
- Background task only runs when clients are connected
- Single broadcast sent to all connected clients (no per-client queries)
- Automatic cleanup of disconnected clients
- Database query executed once per 5-second interval, results broadcast to all

**Authentication Options:**
- Query parameter: `wss://backend.com/online/ws?token=<access_token>`
- Cookie: HttpOnly cookie automatically sent with WebSocket handshake (browser-dependent)
- Token exchange: `/auth/ws-token` endpoint provides short-lived token (60s) for WebSocket connections

**Data Flow:**
1. Player makes API call → UserActivity record updated with timestamp and action
2. Background task queries UserActivity for records from last 30 minutes
3. Results formatted with relative timestamps ("2m ago", "5s ago")
4. Broadcast JSON message to all connected WebSocket clients
5. Repeat every 5 seconds

**Distinction from PhrasesetActivity:**
- `UserActivity`: Real-time presence tracking (last 30 minutes), used for "Who's Online"
- `PhrasesetActivity`: Historical event log for phraseset lifecycle tracking and review

See [online_users.py router](../backend/routers/online_users.py) for implementation details.

---

## Results & UI

### Results Display
- **Status Area**: Shows all active and completed rounds, split by type (prompt, copy, vote)
- **Visual Cue**: Small notification when results are ready
- **Deferred Collection**: Prizes are claimed the first time contributors view results (tracked via `result_views`)
- **Results Content**:
  - For contributors: All votes shown, reveal which phrase was original, points earned, payout amount
  - For voters: Correct answer revealed immediately after vote submission, payout equals the configured `vote_payout_correct` amount if correct. Show voters vote tally thus far and add to status area so players can check back to see final vote tally.

### Result Timing
- **For Voters**: Immediate feedback after vote submission (correct/incorrect, original phrase revealed, payout if correct equal to configured `vote_payout_correct`)
- **For Contributors**: Results available immediately after voting period closes
- **Prize Collection**: Requires viewing results screen to credit account

### Currency
- **Flipcoins (f)**: In-game currency shown with flipcoin icon in UI
- **Display format**: Flipcoin icon + number (no dollar sign)
- **Documentation format**: "100f" or "100 Flipcoins"

---

## Responsibility Division

### Frontend Responsibilities
- UI presentation for all round types
- Countdown timer display (client-side calculation from `expires_at`)
- Player dashboard (balance, active rounds, pending results)
- Quest progress display and reward claiming
- Round type selection with availability indicators
- Queue depth display and copy discount notifications
- Input validation (basic format checks before API call)
- Polling for round availability and results during idle state
- Tutorial system with interactive overlay and guided tours
- State management (see [API.md](API.md#frontend-integration) for details)

### Backend Responsibilities
- Player accounts, username recovery, and wallet management
- Guest account creation and upgrade flow
- Daily login bonus tracking and distribution
- Tutorial progress tracking and persistence
- Quest system (16 achievement types with automatic progress tracking)
- Quest reward distribution and tier progression
- Phrase validation against NASPA dictionary and semantic similarity
- Duplicate and similarity detection (copy vs. original, cosine similarity threshold)
- Queue management (prompt, copy, vote queues)
- Copy discount activation (when prompts_waiting > 10)
- Matchmaking logic
- Round lifecycle state machine
- Timer enforcement with grace period
- Vote counting and finalization triggers with automatic payout calculation
- Voting timeline management (3-vote 10-min, 5-vote 60-sec windows)
- Scoring calculations and payout distribution
- Transaction logging and audit trail (including quest rewards)
- Anti-cheat enforcement (self-voting prevention, duplicate vote checks)
- Rate limiting (guest-specific: 50 req/min general, 10 req/min voting, 5 guest creations/min per IP)
- Results preparation and storage
- One-round-at-a-time constraint enforcement

---

## API Endpoints

See [API.md](API.md) for complete REST API documentation including:
- All endpoint specifications with request/response formats
- Error codes and HTTP status codes
- Frontend integration guide
- Example workflows
- TypeScript type definitions
- Polling recommendations

---

## Core Game Logic

### Phrase Validation
- Dictionary: NASPA word list (~191,000 words) for individual word validation
- Phrase length: 2-5 words (4-100 characters total including spaces)
- Format: Letters A-Z and spaces only (case-insensitive, stored uppercase)
- Connecting words: A, I always allowed (count toward 5-word limit)
- Copy validation: Must differ from original and be semantically distinct (cosine similarity < 0.85)
- Similarity model: all-mpnet-base-v2 (sentence-transformers)
- See [API.md](API.md#game-configuration) for complete validation rules

### Phrase Randomization
For voting displays, phrase order is randomized per-voter (not stored in database) to prevent pattern recognition if players share results.

---

## Code Quality Patterns

### Denormalized Data Pattern
Phraseset uses denormalized fields for performance while maintaining referential integrity:

```python
# Denormalized fields (copied from source rounds)
prompt_text = Column(String(500), nullable=False)
original_phrase = Column(String(100), nullable=False)
copy_phrase_1 = Column(String(100), nullable=False)
copy_phrase_2 = Column(String(100), nullable=False)

# Relationships to source data
prompt_round = relationship("Round", foreign_keys=[prompt_round_id])
copy_round_1 = relationship("Round", foreign_keys=[copy_round_1_id])
copy_round_2 = relationship("Round", foreign_keys=[copy_round_2_id])
```

**Validation**: RoundService validates all denormalized fields exist before creating phrasesets to prevent data corruption.

### Timezone Handling Pattern
Use `ensure_utc()` utility for consistent timezone handling:

```python
from backend.utils.datetime_helpers import ensure_utc

# Convert timezone-naive datetime from database
elapsed = (current_time - ensure_utc(phraseset.fifth_vote_at)).total_seconds()
```

**Benefits**: Eliminates 6+ blocks of duplicated timezone normalization code across services.

### System/Programmatic Operations
VoteService provides separate methods for human vs system operations:

```python
# Human voting (requires active round, checks grace period)
async def submit_vote(round, phraseset, phrase, player, transaction_service) -> Vote

# System/AI voting (no round required, skips grace period)
async def submit_system_vote(phraseset, player, chosen_phrase, transaction_service) -> Vote
```

**Single Source of Truth**: Both AI and human votes use identical business logic for consistency.

### Resource Management Pattern
HTTP clients use async context managers for proper lifecycle:

```python
async with PhraseValidationClient() as client:
    result = await client.validate("phrase")
# Session automatically closed on exit
```

**Cleanup**: Application lifespan manager ensures all resources are properly closed on shutdown.

### Game Balance Configuration
All game balance constants centralized in settings for easy tuning:

```python
# In config.py
vote_max_votes: int = 20
vote_closing_threshold: int = 5
vote_closing_window_minutes: int = 1
vote_minimum_threshold: int = 3
vote_minimum_window_minutes: int = 10

# Usage in services
if phraseset.vote_count >= settings.vote_max_votes:
    should_finalize = True
```

**Benefits**: Single place to adjust game balance, no magic numbers scattered across code.