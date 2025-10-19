# Technical Architecture and Overview

## System Overview

Quipflip is a FastAPI-based backend service with a stateless REST API architecture. The backend maintains all game state while the frontend is a presentation layer.

## Project Structure

```
repo/
├── backend/              # FastAPI application, SQLAlchemy models, and services
│   ├── main.py           # ASGI entrypoint
│   ├── routers/          # Route modules (players, rounds, phrasesets, health)
│   ├── services/         # Business logic (rounds, votes, phrasesets, players)
│   ├── models/           # ORM models (Player, Round, PhraseSet, etc.)
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
- **Authentication**: JWT access tokens with refresh token rotation (legacy API key fallback)
- **Validation**: Pydantic schemas + NASPA word dictionary + sentence-transformers similarity
- **Queueing & Locks**: Redis-backed when available with in-memory/threaded fallback

### Authentication

JWT authentication with short-lived access tokens and 30-day refresh tokens. See [API.md](API.md) for complete authentication documentation including:
- Authorization header format (`Authorization: Bearer <token>`)
- Credential-based login (`POST /auth/login`)
- Refresh token endpoint (`POST /auth/refresh`)
- Legacy API key rotation endpoint

---

## Results & UI

### Results Display
- **Status Area**: Shows all active and completed rounds, split by type (prompt, copy, vote)
- **Visual Cue**: Small notification when results are ready
- **Deferred Collection**: Prizes are claimed the first time contributors view results (tracked via `result_views`)
- **Results Content**:
  - For contributors: All votes shown, reveal which phrase was original, points earned, payout amount
  - For voters: Correct answer revealed immediately after vote submission, \$5 credited if correct. Show voters vote tally thus far and add to status area so players can check back to see final vote tally.

### Result Timing
- **For Voters**: Immediate feedback after vote submission (correct/incorrect, original phrase revealed, \$5 payout if correct)
- **For Contributors**: Results available immediately after voting period closes
- **Prize Collection**: Requires viewing results screen to credit account

---

## Responsibility Division

### Frontend Responsibilities
- UI presentation for all round types
- Countdown timer display (client-side calculation from `expires_at`)
- Player dashboard (balance, active rounds, pending results)
- Round type selection with availability indicators
- Queue depth display and copy discount notifications
- Input validation (basic format checks before API call)
- Polling for round availability and results during idle state
- Tutorial system with interactive overlay and guided tours
- State management (see [API.md](API.md#frontend-integration) for details)

### Backend Responsibilities
- Player accounts, username recovery, and wallet management
- Daily login bonus tracking and distribution
- Tutorial progress tracking and persistence
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
- Transaction logging and audit trail
- Anti-cheat enforcement (self-voting prevention, duplicate vote checks)
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
- Phrase length: 1-5 words (2-100 characters total)
- Format: Letters A-Z and spaces only (case-insensitive, stored uppercase)
- Connecting words: A, AN, THE, I always allowed (count toward 5-word limit)
- Copy validation: Must differ from original and be semantically distinct (cosine similarity < 0.85)
- Similarity model: all-MiniLM-L6-v2 (sentence-transformers)
- See [API.md](API.md#game-configuration) for complete validation rules

### Phrase Randomization
For voting displays, phrase order is randomized per-voter (not stored in database) to prevent pattern recognition if players share results.

---

## Backend State Machines

### Voting Timeline State Machine

```
Phrase Set Created → status: "open"
  ↓
3rd vote received → third_vote_at = now, status: "open"
  ↓
  Wait for earlier of:
  - 10 minutes elapsed since third_vote_at
  - 5th vote received
  ↓
5th vote received (within 10 min) → fifth_vote_at = now, status: "closing"
  ↓
  Accept new voters for 60 seconds (POST /rounds/vote)
  Grace period: voters who called POST /rounds/vote within 60s window get full 60s to submit
  ↓
20th vote OR (60s elapsed since 5th vote, all pending voters submitted) → status: "closed"
  ↓
Calculate scores and payouts → status: "finalized"
  (Contributors can now view results via GET /phrasesets/{id}/results)
```

### Copy Round Abandonment

When a copy round times out without submission:
1. Round status set to "abandoned"
2. Player refunded \$95 (keeps \$5 entry fee as penalty)
3. Associated prompt_round returned to queue for reassignment
4. Same player prevented from getting same prompt_round_id again (24h cooldown)
5. No limit on how many times a prompt can be abandoned by different players

### Outstanding Prompts Limit

Players limited to 10 outstanding prompts where:
- "Outstanding" = phrasesets in status "open" or "closing" (not yet finalized)
- Viewing results does not affect count
- Enforced when calling POST /rounds/prompt
