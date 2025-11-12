# Quipflip

A multiplayer phrase association game with flipcoin stakes (the in-game currency). Players respond to prompts with brief phrases, copy them, and vote to identify originals.

## 🎮 Game Overview

Quipflip is a three-phase game where players:
1. **Prompt** - Submit a phrase for a creative prompt (100f)
2. **Copy** - Submit a similar phrase without seeing the prompt (50f or 40f with the queue discount)
3. **Vote** - Identify the original phrase from three options (10f)

Winners split a prize pool based on vote performance. See full game rules below.

> **Currency Note:** All amounts in this README are listed in flipcoins (f).

## 🚀 Quick Start

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run migrations
alembic upgrade head

# Start API server
uvicorn backend.main:app --reload

# In a separate terminal start the phrase validation worker from the quipflip-pwv folder
cd ..
cd quipflip-pwv
uvicorn main:app --port 9000 --reload
```

Server runs at **http://localhost:8000**
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

### Frontend

```bash
# Navigate to frontend
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev -- --host
```

Frontend runs at **http://localhost:5173**
- See [frontend/README.md](frontend/README.md) for detailed documentation

## 📚 Documentation

**For Developers:**
- **[API.md](docs/API.md)** - Complete REST API reference with TypeScript types
- **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - System architecture and backend logic
- **[DATA_MODELS.md](docs/DATA_MODELS.md)** - Database schema reference
- **[AI_SERVICE.md](docs/AI_SERVICE.md)** - AI player service details
- **[CLEANUP_SCRIPTS.md](docs/CLEANUP_SCRIPTS.md)** - Background cleanup job implementations

**For Game Design:**
- **[README.md](README.md)** - This file (complete game rules)
- **[GAME_RULES.md](docs/GAME_RULES.md)** - Detailed game mechanics and examples

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

## 👤 Account Types

### Guest Accounts
- **Quick Start**: Play now without email/password signup
- **Auto-Generated Credentials**: Email (`guest####@quipflip.xyz`) and password (`QuipGuest`) provided after creation
- **Rate Limits**: Stricter limits to prevent abuse (50 req/min general, 10 req/min voting)
- **Upgrade Path**: Convert to full account anytime in Settings to save progress permanently

### Full Accounts
- **Custom Credentials**: Choose your own email and password
- **Higher Limits**: Standard rate limits (100 req/min general, 20 req/min voting)
- **Cross-Device**: Access your account from any device
- **Permanent**: All progress saved indefinitely

---

# Complete Game Rules

---

## Round Types

### 1. Prompt Round
- **Cost**: 100f (full amount deducted immediately, 95f refunded on timeout)
- **Process**: Player receives a randomly assigned prompt (e.g., “my deepest desire is to be (a)”) and submits a short phrase.
- **Phrase Requirements**:
  - 1–5 words (2–100 characters total)
  - Letters A–Z and spaces only (case insensitive)
  - Each word must appear in the NASPA dictionary (common connectors like “a”, “an”, “the”, “I” are always allowed)
- **Timing**: 3-minute (180-second) submission window
- **Abandonment**: If the timer expires, the round is cancelled, 5f is forfeited, and the remaining 95f is refunded. The prompt is re-queued for other players.
- **Queue**: Submitted prompts enter the prompt queue until two copy players claim them (future phases will add AI backups after long waits).

### 2. Copy Round
- **Cost**: 50f or 40f (full amount deducted immediately, 45f or 35f refunded on timeout)
- **Dynamic Pricing**: When more than 10 prompts are waiting, copy rounds drop to 40f; the system contributes 10f for each discounted copy so the phraseset prize pool remains 200f.
- **Process**: Player sees only the original player’s phrase (not the prompt) and must submit a similar or related phrase.
- **Phrase Requirements**: Same as the prompt round, plus the submission cannot match the original phrase.
- **Duplicate Handling**: Exact duplicates are rejected and the player must submit a different phrase while the timer continues.
- **Timing**: 3-minute (180-second) submission window
- **Abandonment**: Expiring forfeits 5f (discounted or not) and refunds the remainder. The prompt returns to the queue and the player is blocked from retrying that prompt for 24 hours.
- **Queue**: Once two distinct copy phrases are submitted, the trio forms a phraseset and moves to the voting queue.

### 3. Vote Round
- **Cost**: 10f (deducted immediately)
- **Process**: Player sees the original prompt and three phrases (1 original + 2 copies in voter-specific random order) and selects the phrase they believe is the original.
- **Timing**: 60-second hard limit (frontend enforces, backend allows a 5-second grace period)
- **Abandonment**: No vote = forfeited 10f entry fee.
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
- **Base Contributions**: 100f from the prompt player + 50f from each copy player = 200f total (the system adds 10f per discounted copy so the base pool always starts at 200f).
- **Vote Entries**: Each vote adds 10f to the prize pool before results are calculated.
- **Correct Vote Payouts**: 20f is paid out of the prize pool for every correct vote (maximum 400f if all 20 votes pick the original).
- **Remaining Prize Pool**: `200f + (votes × 10f) - (correct votes × 20f)` is distributed to contributors proportionally to points earned, rounded down to the nearest flipcoin (any remainder is raked).

### Points Distribution
- **Vote for Original**: 1 point to original (prompt) player
- **Vote for Copy**: 2 points to that copy player
- **Example**: 10 votes total
  - 4 votes for original = 4 points to original player
  - 3 votes for copy A = 6 points to copy A player
  - 3 votes for copy B = 6 points to copy B player
  - Total: 16 points

### Payout Calculation
- Prize pool split proportionally by points earned, rounded down to the nearest flipcoin (remainder is raked)
- **Example** (continuing above with 220f remaining after 10 votes with 4 correct voters):
  - Original player: 4/16 × 220f = 55f
  - Copy A player: 6/16 × 220f = 82f
  - Copy B player: 6/16 × 220f = 82f

### Voter Payouts
- **Correct vote**: 20f gross (10f entry + 10f net profit)
- **Incorrect vote**: 0f (lose 10f entry fee)

---

## Player Economics

### Starting Balance
- New players begin with **5000f**

### Daily Login Bonus
- **100f** credited once per UTC calendar date, excluding player creation date
- First bonus available the day after account creation
- Automatically tracks via `last_login_date` UTC timestamp field

### Transaction Costs
- Prompt round: -100f (deducted immediately, 95f refunded on timeout)
- Copy round: -50f or -40f (deducted immediately, 45f or 35f refunded on timeout)
- Vote round: -10f (deducted immediately)

### Revenue Opportunities
- Correct votes: +10f net (20f gross - 10f entry)
- Prize pool earnings: Variable based on performance and votes received
- Daily login bonus: +100f
- *Future Ideas:* Correct voter bonus upon 5 correct votes in a row: +10f

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
- **Copy Queue Discount**: When `prompts_waiting > 10`, copy rounds cost 40f (the system contributes 10f per discounted copy)
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
- **Prompt abandonment**: Round cancelled, 5f penalty forfeited (95f refunded), prompt removed from queue
- **Copy abandonment**: Round cancelled, 5f penalty forfeited (45f refunded on 50f rounds, 35f on discounted rounds), prompt_round returned to queue for other players (original player blocked 24h)
- **Vote abandonment**: Player loses 10f, vote not counted
- **Manual abandon action**: Players can click the red × on the dashboard countdown card to abandon an active prompt or copy round instantly; the same penalty/refund rules apply immediately
- **Implementation**: Backend timeout cleanup job processes expired rounds periodically
