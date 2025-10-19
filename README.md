# Quipflip

A multiplayer phrase association game with monetary stakes. Players respond to prompts with brief phrases, copy them, and vote to identify originals.

## 🎮 Game Overview

Quipflip is a three-phase game where players:
1. **Prompt** - Submit a phrase for a creative prompt (\$100)
2. **Copy** - Submit a similar phrase without seeing the prompt (\$100 or \$90)
3. **Vote** - Identify the original phrase from three options (\$1)

Winners split a prize pool based on vote performance. See full game rules below.

## 🚀 Quick Start

### Backend (Production Ready)

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start server
uvicorn backend.main:app --reload
```

Server runs at **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Frontend (MVP Complete)

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

Frontend runs at **http://localhost:5173**
- See [frontend/README.md](frontend/README.md) for detailed documentation

## 📚 Documentation

**For Developers:**
- **[API.md](docs/API.md)** - Complete REST API reference with TypeScript types
- **[FRONTEND_PLAN.md](docs/FRONTEND_PLAN.md)** - Frontend implementation guide (NEW)
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and backend logic
- **[DATA_MODELS.md](docs/DATA_MODELS.md)** - Database schema reference
- **[MVP_SUMMARY.md](docs/MVP_SUMMARY.md)** - Project status and completion checklist

**For Game Design:**
- **[README.md](README.md)** - This file (complete game rules)
- **[PLAN.md](docs/PROJECT_PLAN)** - Implementation phases and roadmap

## ⚡ Features

**✅ Phase 1 MVP Complete (100%)**

*Backend:*
- Player accounts with JWT + refresh token authentication (HTTP-only cookies)
- Email-based login with auto-generated player pseudonyms
- Three round types (Prompt, Copy, Vote)
- Queue management with dynamic pricing
- NASPA dictionary validation (191k words)
- Proportional prize distribution
- Daily login bonuses
- Prompt feedback system (like/dislike)
- Phraseset tracking and unclaimed results
- Comprehensive player statistics with win rates and earnings breakdown
- Transaction audit trail
- 20+ REST API endpoints
- 88% test coverage

*Frontend:*
- React 18 + TypeScript with Vite 5 (stable, production-ready)
- JWT authentication with automatic token refresh
- Email/password login with auto-suggested usernames for registration
- Responsive UI with Tailwind CSS 3 and custom branding
- Real-time countdown timers with visual states
- Dashboard with balance, round selection, and phraseset tracking
- All three round types with feedback mechanisms
- Results viewing with pseudonym display, vote breakdown and prize claiming
- Phraseset tracking dashboard (by role and status)
- Interactive statistics page with charts and performance metrics (Recharts)
- Automatic state polling with request cancellation
- Error handling & notifications
- 22% smaller bundle size vs bleeding-edge versions

**🔜 Phase 2 (Planned)**
- Transaction history endpoint
- Admin API for testing

**🎯 Phase 3+ (Future)**
- AI backup players
- Real-time WebSocket updates
- Leaderboards & achievements
- Social features

## 🛠️ Tech Stack

**Backend:**
- FastAPI (async Python web framework)
- SQLAlchemy (async ORM)
- PostgreSQL / SQLite
- Redis (with in-memory fallback)
- Alembic (migrations)
- Pydantic (validation)

**Deployment:**
- Docker / docker-compose
- Heroku ready (heroku.yml)
- Environment-based configuration

## 🧪 Testing

```bash
pytest tests/
```

---

# Complete Game Rules

---

## Round Types

### 1. Prompt Round
- **Cost**: \$100 (full amount deducted immediately, \$90 refunded on timeout)
- **Process**: Player receives a randomly assigned prompt (e.g., “my deepest desire is to be (a)”) and submits a short phrase.
- **Phrase Requirements**:
  - 1–5 words (2–100 characters total)
  - Letters A–Z and spaces only (case insensitive)
  - Each word must appear in the NASPA dictionary (common connectors like “a”, “an”, “the”, “I” are always allowed)
- **Timing**: 3-minute (180-second) submission window
- **Abandonment**: If the timer expires, the round is cancelled, \$10 is forfeited, and the remaining \$90 is refunded. The prompt is re-queued for other players.
- **Queue**: Submitted prompts enter the prompt queue until two copy players claim them (future phases will add AI backups after long waits).

### 2. Copy Round
- **Cost**: \$100 or \$90 (full amount deducted immediately, \$90 refunded on timeout)
- **Dynamic Pricing**: When more than 10 prompts are waiting, copy rounds drop to \$90; the system contributes \$10 so the phraseset prize pool remains \$300.
- **Process**: Player sees only the original player’s phrase (not the prompt) and must submit a similar or related phrase.
- **Phrase Requirements**: Same as the prompt round, plus the submission cannot match the original phrase.
- **Duplicate Handling**: Exact duplicates are rejected and the player must submit a different phrase while the timer continues.
- **Timing**: 3-minute (180-second) submission window
- **Abandonment**: Expiring forfeits \$10 (or \$9 on discounted rounds) and refunds the remainder. The prompt returns to the queue and the player is blocked from retrying that prompt for 24 hours.
- **Queue**: Once two distinct copy phrases are submitted, the trio forms a phraseset and moves to the voting queue.

### 3. Vote Round
- **Cost**: \$1 (deducted immediately)
- **Process**: Player sees the original prompt and three phrases (1 original + 2 copies in voter-specific random order) and selects the phrase they believe is the original.
- **Timing**: 60-second hard limit (frontend enforces, backend allows a 5-second grace period)
- **Abandonment**: No vote = forfeited \$1 entry fee.
- **Voting Pool**:
  - Minimum 3 votes required before finalization (future phases will auto-fill with AI if needed).
  - Maximum 20 votes per phraseset.
  - After the 3rd vote, the phraseset stays open for up to 10 minutes unless it hits a 5th vote sooner.
  - After the 5th vote, new voters have a 60-second window to participate.
  - The phraseset closes at 20 votes or when the 60-second post–5th vote window elapses (whichever comes first).
- **Restrictions**: Contributors (prompt + both copy players) cannot vote on their own phraseset, and each voter only gets one vote per phraseset.

---

## Player Constraints

### One Round At A Time
- Only one round (prompt, copy, or vote) may be active per player at any time.
- Players must submit or abandon the current round before starting another.
- Viewing finalized results does not count as an active round.

### Ten Outstanding Prompts
- A player can hold up to 10 outstanding prompts whose phrasesets are still “open” or “closing”.
- The limit is enforced when calling `POST /rounds/prompt`.
- Checking results does not affect the outstanding count.

---

## Scoring & Payouts

### Prize Pool Formation
- **Contributions**: \$100 each from 3 players = \$300 total pool (system contributes \$10 when copy discount active)
- **Vote Payments Deducted**: \$5 per correct vote (max \$100 for 20 votes)
- **Rake**: Vote entry fees (\$1 per voter) are rake and don't enter prize pool
- **Remaining Prize Pool**: \$300 - (correct votes × \$5) = distributed to contributors proportionally to points earned, rounded down to nearest \$1 and remainder is raked

### Points Distribution
- **Vote for Original**: 1 point to original (prompt) player
- **Vote for Copy**: 2 points to that copy player
- **Example**: 10 votes total
  - 4 votes for original = 4 points to original player
  - 3 votes for copy A = 6 points to copy A player
  - 3 votes for copy B = 6 points to copy B player
  - Total: 16 points

### Payout Calculation
- Prize pool split proportionally by points earned, rounded down to nearest \$1 (remainder is raked)
- **Example** (continuing above with \$250 remaining pool after \$50 in vote payments):
  - Original player: 4/16 × \$250 = \$62
  - Copy A player: 6/16 × \$250 = \$93
  - Copy B player: 6/16 × \$250 = \$93

### Voter Payouts
- **Correct vote**: \$5 gross (\$4 net after \$1 entry fee)
- **Incorrect vote**: \$0 (lose \$1 entry fee)

---

## Player Economics

### Starting Balance
- New players begin with **\$1000**

### Daily Login Bonus
- **\$100** credited once per UTC calendar date, excluding player creation date
- First bonus available the day after account creation
- Automatically tracks via `last_login_date` field

### Transaction Costs
- Prompt round: -\$100 (deducted immediately, \$90 refunded on timeout)
- Copy round: -\$100 or -\$90 (deducted immediately, \$90 or \$81 refunded on timeout)
- Vote round: -\$1 (deducted immediately)

### Revenue Opportunities
- Correct votes: +\$4 net (+\$5 gross - \$1 entry)
- Prize pool earnings: Variable based on performance and votes received
- Daily login bonus: +\$100
- *Future Ideas:* Correct voter bonus upon 5 correct votes in a row: +\$10

---

## Game Flow & Matchmaking

### Player Choice
At any time (if not already in an active round), players can choose to:
1. **Start Prompt Round** - Only if the player has sufficient balance and fewer than 10 outstanding prompts (phrasesets in “open” or “closing” status)
2. **Start Copy Round** - Only if prompts are waiting for copies in queue
3. **Start Vote Round** - Only if complete phrasesets (1 original + 2 copies) are waiting for votes (excluding the player’s own phrasesets)

### Queue System
- **Prompt Queue**: Submitted prompts waiting for copy players (FIFO)
- **Copy Assignment**: FIFO from prompt queue when player calls POST /rounds/copy
- **Copy Queue Discount**: When `prompts_waiting > 10`, copy rounds cost \$90 (the system contributes \$10 per phraseset)
- **Vote Queue**: Complete phrasesets waiting for voters
- **Vote Assignment Priority**:
  1. Phrasesets with ≥5 votes (FIFO by 5th vote time)
  2. Phrasesets with 3–4 votes (FIFO by 3rd vote time)
  3. Phrasesets with <3 votes (random selection)

### Anti-Gaming Measures
- Contributors cannot vote on their own phrasesets (filtered at assignment).
- Phrase order is randomized per voter in the voting display (not stored).
- Rate limit: Maximum 10 outstanding prompts per player (phrasesets in “open”/“closing” status).
- One vote per phraseset per player (enforced via a unique composite index); votes cannot be changed once submitted.
- Grace period: 5 seconds past timer expiry (backend only, not shown to users)
- API rate limiting: Prevent abuse/brute force attempts

---

## Timing Rules

### Submission Windows
- **Prompt/Copy submission**: 3 minutes (180 seconds) (frontend enforces, backend has a 5-second grace period)
- **Voting**: 60 seconds (frontend enforces, backend has a 5-second grace period)

### Grace Period Implementation
- **Frontend**: Disables submit button and shows "Time's up" message when timer reaches 0
- **Backend**: Accepts submissions up to 5 seconds after expires_at timestamp
- **Purpose**: Accounts for network latency and ensures fair play

### Voting Finalization Timeline
- **After 3rd vote**: Phraseset remains open for the earlier of:
  - 10 minutes, OR
  - Until 5th vote is received
- **After 5th vote received**: Accept new voters (POST /rounds/vote) for 60 seconds
- **Closure**: After the 20th vote OR when 60 seconds have elapsed since the 5th vote and all pending voters have submitted
- **Grace period**: Voters who called POST /rounds/vote within the 60-second window get their full 60 seconds to vote, even if this extends past the window

### Abandonment Handling
- **Prompt abandonment**: Round cancelled, \$10 penalty forfeited (\$90 refunded), prompt removed from queue
- **Copy abandonment**: Round cancelled, \$10 or \$9 penalty forfeited (rest refunded), prompt_round returned to queue for other players (original player blocked 24h)
- **Vote abandonment**: Player loses \$1, vote not counted
- **Implementation**: Backend timeout cleanup job processes expired rounds periodically
