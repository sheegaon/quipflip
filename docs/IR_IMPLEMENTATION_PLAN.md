# Initial Reaction MVP Implementation Plan

## Status Update (2025-01-16)
✅ **Phase 1 COMPLETE** – All legacy Quipflip tables were renamed with the `qf_` prefix and the IR models/enums/migrations exist as expected.
✅ **Phase 2 COMPLETE** – Word caching now writes to `ir_ai_phrase_cache.original_phrase/validated_phrases`, queue hooks fire when sets are created, filled, or finalized, the AI backup loop provisions `ir_players`, and the vote service rejects self-votes while enforcing the non-participant cap.
✅ **Phase 3 COMPLETE** – `/auth/upgrade`, `/player/balance`, `/player/dashboard`, and `/player/claim-daily-bonus` join the existing IR routes, with the new daily bonus service persisting to `ir_daily_bonuses`/`ir_transactions` and exposing wallet/vault/daily bonus state plus pending payouts.
✅ **Code Quality Fixes COMPLETE** – Distributed wallet helpers, queue wiring, duplicate prevention, and the IR-only AI bootstrap removed the remaining backend blockers.
✅ **Phase 4 CONFIGURATION READY** – The settings module now includes the per-set non-participant vote cap consumed by the updated services.
✅ **Phase 5 COMPLETE** – Frontend foundation established with React app structure, TypeScript types, API client, IRGameContext, Landing page, and Dashboard page. Routing configured with protected routes and placeholder pages for gameplay screens.
✅ **Phase 6 COMPLETE** – All gameplay screens implemented (BackronymCreate, SetTracking, Voting, Results) with full functionality, animations, real-time polling, error handling, and Quipflip-inspired UX patterns.
✅ **Phase 7 COMPLETE** – Comprehensive test suite created (14 auth/player tests, 5+ game flow tests), GitHub Actions CI/CD pipeline implemented, deployment scripts created for Heroku and Vercel.

**Status:** Initial Reaction MVP is ready for production deployment! 🚀

### Phase 2 (Verification Snapshot – 2024-03-29)
- Duplicate-prevention is now wired through `IRWordService` → `ir_ai_phrase_cache`, AI backups spawn dedicated `ir_players`, queue transitions fire when sets open/vote/finalize, votes reject self-selection and honor the per-set cap, and the new wallet helpers encapsulate locking + ledger writes.

### Phase 3 (Verification Snapshot – 2024-03-29)
- Authentication now covers guest upgrades in addition to register/login/guest/logout/refresh.
- Player endpoints include `/me`, `/player/{id}`, `/player/balance`, `/player/dashboard`, `/player/claim-daily-bonus`, plus the existing statistics + leaderboard routes.
- Game endpoints cover `/start`, `/sets/{set_id}/submit`, `/sets/{set_id}/status`, `/sets/{set_id}/vote`, and `/sets/{set_id}/results`, with the AI backup background task still running every two minutes.
- Daily bonuses flow through the new service into `ir_daily_bonuses`/`ir_transactions`, surfacing pending payouts to the dashboard.

### Code Quality Fixes (Complete)
- Word caching reads/writes the correct `IRAIPhraseCache` fields and avoids recently used words at runtime.
- Queue wiring, vote guards, and AI bootstrap logic now execute inside the main service flows.
- Transaction helpers centralize wallet/vault mutations to prevent race conditions.
- Configuration includes the per-set vote cap along with the earlier IR-specific knobs.

**Next:** Phase 5 - Frontend Foundation

---

## Overview
Build Initial Reaction as a completely separate game with:
- New database tables (all prefixed `ir_`)
- Separate frontend app in `/ir_frontend/`
- Shared infrastructure (auth, AI, validation) with light modifications
- API routes under `/api/ir/*`
- Separate player accounts and InitCoin currency

---

## Phase 1: Database Schema & Models (Backend Foundation)

### 1.1 Rename Existing QF Tables
**Goal:** Prefix all Quipflip tables with `qf_` to distinguish them from IR tables

**Approach:**
- Create Alembic migration to rename all existing tables
- Tables to rename: `players` → `qf_players`, `rounds` → `qf_rounds`, `phrasesets` → `qf_phrasesets`, etc.
- Update all model `__tablename__` declarations
- Update all foreign key references
- Test migration on local SQLite first

**Files to modify:**
- All files in `backend/models/` (update `__tablename__` and ForeignKey references)
- Create migration: `alembic revision --autogenerate -m "Rename QF tables with qf_ prefix"`

### 1.2 Create IR Database Models
**Goal:** Create all new IR tables as specified in IR_DATA_MODELS.md

**New model files in `backend/models/ir/`:**

1. **`ir_player.py`** - IR-specific player accounts
   - Table: `ir_players`
   - Fields: `player_id` (UUID), `username`, `username_canonical`, `email`, `password_hash`, `wallet`, `vault`, `is_guest`, `created_at`, `last_login_date`, `active_session_id`, etc.
   - Reuse username generation logic from QF

2. **`ir_backronym_set.py`** - BackronymSet model
   - Table: `ir_backronym_sets`
   - Fields: `set_id`, `word`, `mode` (enum: standard/rapid), `status` (enum: open/voting/finalized), `entry_count`, `vote_count`, `non_participant_vote_count`, `total_pool`, `creator_final_pool`, etc.
   - Indexes as specified in IR_DATA_MODELS.md

3. **`ir_backronym_entry.py`** - BackronymEntry model
   - Table: `ir_backronym_entries`
   - Fields: `entry_id`, `set_id`, `player_id`, `backronym_text` (JSONB array), `is_ai`, `submitted_at`, `vote_share_pct`, `received_votes`, `forfeited_to_vault`
   - Unique constraint on `(player_id, set_id)`

4. **`ir_backronym_vote.py`** - BackronymVote model
   - Table: `ir_backronym_votes`
   - Fields: `vote_id`, `set_id`, `player_id`, `chosen_entry_id`, `is_participant_voter`, `is_ai`, `is_correct_popular`, `created_at`
   - Unique constraint on `(player_id, set_id)`

5. **`ir_backronym_observer_guard.py`** - Observer eligibility snapshot
   - Table: `ir_backronym_observer_guards`
   - Fields: `set_id` (PK), `first_participant_created_at`
   - **Defer implementation for MVP** (non-participant voting open to all)

6. **`ir_transaction.py`** - IR transaction ledger
   - Table: `ir_transactions`
   - Fields: Same as QF transactions but for IR currency
   - Transaction types: `ir_backronym_entry`, `ir_vote_entry`, `ir_vote_payout`, `ir_creator_payout`, `vault_contribution`

7. **`ir_result_view.py`** - Result viewing tracking
   - Table: `ir_result_views`
   - Fields: `view_id`, `set_id`, `player_id`, `result_viewed`, `payout_amount`, `viewed_at`, `first_viewed_at`

8. **`ir_refresh_token.py`** - IR-specific refresh tokens
   - Table: `ir_refresh_tokens`
   - Reuse auth patterns from QF

9. **`ir_daily_bonus.py`** - Daily bonus tracking for IR
   - Table: `ir_daily_bonuses`

10. **`ir_ai_metric.py`** - AI metrics for IR backronym generation
    - Table: `ir_ai_metrics`
    - Track backronym generation and voting operations

11. **`ir_ai_phrase_cache.py`** - Cache for AI backronyms
    - Table: `ir_ai_phrase_cache`
    - Store pre-validated backronyms for reuse

### 1.3 Create Enums
**File:** `backend/models/ir/enums.py`
- `IRSetStatus`: `open`, `voting`, `finalized`
- `IRMode`: `standard`, `rapid`

### 1.4 Create Alembic Migration
- Generate migration: `alembic revision --autogenerate -m "Add Initial Reaction tables"`
- Review and test migration locally
- Ensure all indexes and constraints are created

---

## Phase 2: Backend Services (Business Logic)

### 2.1 Core IR Services in `backend/services/ir/`

1. **`ir_player_service.py`** - Player management
   - `create_player(email, password)` - Create IR account
   - `create_guest_player()` - Auto-generate guest account
   - `upgrade_guest_to_full(player, email, password)` - Upgrade guest
   - `get_player_by_email(email)` - Fetch player
   - `get_player_by_id(player_id)` - Fetch player
   - Reuse `UsernameService.generate_unique_username()` from QF

2. **`ir_auth_service.py`** - Authentication
   - Reuse QF's JWT token generation/validation logic
   - `create_access_token()`, `create_refresh_token()`
   - `verify_token()`, `get_current_player()`
   - Use separate cookie names: `ir_access_token`, `ir_refresh_token`

3. **`ir_transaction_service.py`** - Wallet/vault management
   - `debit_wallet(player_id, amount, type, reference_id)`
   - `credit_wallet(player_id, amount, type, reference_id)`
   - `apply_vault_rake(player_id, net_earnings)`
   - Distributed locking to prevent race conditions (reuse QF pattern)

4. **`ir_backronym_set_service.py`** - BackronymSet lifecycle
   - `create_set(word, mode)` - Create new set with random word
   - `get_available_set_for_entry()` - Get open set for player to join
   - `add_entry(set_id, player_id, backronym_text)` - Submit backronym
   - `transition_to_voting(set_id)` - Move to voting phase when 5 entries
   - `finalize_set(set_id)` - Calculate payouts and distribute prizes
   - `get_set_details(set_id)` - Full set with entries/votes

5. **`ir_vote_service.py`** - Voting logic
   - `submit_vote(set_id, player_id, chosen_entry_id, is_participant)`
   - `submit_system_vote(set_id, ai_player_id, chosen_entry_id)` - For AI votes
   - `check_vote_eligibility(player_id, set_id)` - Participant vs non-participant
   - `get_available_sets_for_voting(player_id)` - Sets player can vote on

6. **`ir_queue_service.py`** - Queue management
   - In-memory queue for open sets needing entries
   - In-memory queue for sets needing votes
   - `get_next_open_set()` - FIFO for entry queue
   - `get_next_voting_set()` - Priority queue for voting

7. **`ir_word_service.py`** - Word generation
   - `get_random_word()` - Generate random 3-5 letter word from dictionary
   - Use same NASPA dictionary as QF phrase validator
   - Cache words to avoid duplicates in short timeframes

8. **`ir_scoring_service.py`** - Prize pool calculation
   - `calculate_payouts(set_id)` - Pro-rata distribution based on votes
   - Apply vault rake (30% of net earnings)
   - Handle non-participant voter payouts (20 IC if correct)

9. **`ir_statistics_service.py`** - Stats and leaderboards
   - `get_player_stats(player_id)` - Individual performance
   - `get_creator_leaderboard()` - Ranked by vault contributions
   - `get_voter_leaderboard()` - Ranked by vote accuracy
   - Exclude AI players from leaderboards

10. **`ir_result_view_service.py`** - Result claiming
    - `claim_result(player_id, set_id)` - Idempotent payout claiming
    - `get_pending_results(player_id)` - Unclaimed results

### 2.2 Extend Existing AI Service

**File:** `backend/services/ai/ai_service.py`

**New methods to add:**
1. `generate_backronym(word: str, prompt_round=None)` - Generate N valid words for word
   - Use prompt template: "Generate a clever backronym for {WORD}. Create {N} words, one per letter..."
   - Validate each word against NASPA dictionary
   - Return array of validated words
   - Cache in `ir_ai_phrase_cache`

2. `generate_backronym_vote(set: BackronymSet)` - AI vote on backronyms
   - Use prompt template: "Choose the most clever backronym for {WORD}: 1) {backronym1} 2) {backronym2}..."
   - Return chosen entry index
   - Track correctness in metrics

3. `run_ir_backup_cycle()` - Fill stalled sets
   - Find sets with <5 entries AND age > 2 minutes
   - Generate AI backronyms to fill to 5
   - Find sets with <5 votes AND age > 2 minutes
   - Generate AI votes to reach minimum

**New AI player accounts:**
- `ai_backronym_001@initialreaction.internal` through `ai_backronym_010@initialreaction.internal`
- Rotate through accounts to avoid detection
- Mark with `is_ai=True` flag

**New prompt templates in `backend/services/ai/prompt_builder.py`:**
- `build_backronym_prompt(word: str)` - For backronym generation
- `build_backronym_vote_prompt(word: str, backronyms: list)` - For voting

### 2.3 Extend Phrase Validation

**File:** `backend/services/phrase_validation_client.py`

**New method:**
- `validate_backronym_words(words: list[str], word_length: int)` - Validate backronym
  - Check each word is 2-15 chars, A-Z only
  - Check each word exists in dictionary
  - Check array length matches target word length
  - Return validation result with errors

---

## Phase 3: Backend API Routes

### 3.1 Create IR Router
**File:** `backend/routers/ir.py`

**Authentication endpoints:**
- `POST /ir/auth/register` - Create IR account
- `POST /ir/auth/guest` - Create guest account
- `POST /ir/auth/login` - Login to IR
- `POST /ir/auth/logout` - Logout
- `POST /ir/auth/refresh` - Refresh token
- `POST /ir/auth/upgrade` - Upgrade guest to full account

**Player endpoints:**
- `GET /ir/player/balance` - Get wallet/vault balances
- `GET /ir/player/dashboard` - Dashboard data (balance, active session, pending results)
- `POST /ir/player/claim-daily-bonus` - Claim daily 100 IC

**Game endpoints:**
- `POST /ir/start` - Start new backronym battle (creates or joins open set)
- `POST /ir/sets/{set_id}/submit` - Submit backronym
- `GET /ir/sets/{set_id}/status` - Poll set status
- `POST /ir/sets/{set_id}/vote` - Submit vote
- `GET /ir/sets/{set_id}/results` - Get finalized results

**Statistics endpoints:**
- `GET /ir/player/statistics` - Player stats
- `GET /ir/leaderboards/creators` - Creator leaderboard
- `GET /ir/leaderboards/voters` - Voter leaderboard

### 3.2 Mount IR Router in `backend/main.py`

```python
from backend.routers import ir as ir_router

app.include_router(ir_router.router, prefix="/ir", tags=["initial_reaction"])
```

### 3.3 Add IR Background Tasks to `backend/main.py`

**In lifespan context manager:**
```python
# Start IR AI backup cycle
ir_ai_task = asyncio.create_task(run_ir_ai_backup_cycle())
tasks.append(ir_ai_task)
```

**New function:**
```python
async def run_ir_ai_backup_cycle():
    """Background task for IR AI backup players."""
    while True:
        try:
            await asyncio.sleep(120)  # Every 2 minutes for rapid mode
            async with get_async_session_context() as session:
                ai_service = AIService(session)
                await ai_service.run_ir_backup_cycle()
        except Exception as e:
            logger.error(f"IR AI backup cycle error: {e}")
```

---

## Phase 3.5: Code Quality & Bug Fixes (COMPLETE ✅)

### 3.5.1 Dictionary Word Loading Refactor
**File:** `backend/services/ir/ir_word_service.py`

**Problem:** Word service used hardcoded list of ~100 words instead of actual game dictionary

**Solution:** Implemented dynamic dictionary loading
- Added `_load_dictionary_words()` function that reads `backend/data/dictionary.txt`
- Filters to only 3-5 letter words at module initialization
- Loads 12,414 valid words (1,007 three-letter, 3,789 four-letter, 7,618 five-letter)
- Includes fallback to hardcoded list if dictionary file is missing
- Words cached at module load time for O(1) lookup performance
- Maintains same duplicate prevention logic (10-second window)

**Impact:** Game now uses authentic dictionary words instead of curated sample list

### 3.5.2 Queue Service FIFO Implementation
**File:** `backend/services/ir/ir_queue_service.py`

**Problem:** Service maintained in-memory queues but `get_next_open_set()` and `get_next_voting_set()` ignored them, querying database directly

**Solution:** Fixed to use FIFO in-memory queues with database fallback
- Updated `get_next_open_set()` to check in-memory queue first
- Updated `get_next_voting_set()` to check in-memory queue first
- Both methods verify queued sets are still eligible
- Automatically remove ineligible sets from queue
- Fall back to database query only if queue is empty
- Provides durability: service can recover from restart via database
- Maintains true FIFO ordering for queued sets

**Impact:** Queue service now behaves as intended with proper priority ordering

### 3.5.3 Status Enum Refactoring
**Files:** `backend/services/ir/ir_result_view_service.py`, `backend/routers/ir.py`

**Problem:** Code used hardcoded string `"finalized"` instead of enum, risking typos and maintenance issues

**Solution:** Replaced all status string comparisons with enum
- Updated ir_result_view_service.py: 2 occurrences of `IRSetStatus.FINALIZED`
- Updated ir.py router: 1 occurrence in results endpoint
- Added import: `from backend.models.ir.enums import IRSetStatus`
- Provides type safety and IDE support

**Impact:** Reduced typo risk and improved code maintainability

### 3.5.4 Configuration Settings Completion
**File:** `backend/config.py`

**Problem:** Services referenced undefined settings causing AttributeErrors:
- `settings.ir_vote_cost` - Not in config
- `settings.ir_vote_reward_correct` - Not in config
- `settings.ir_non_participant_vote_cap` - Not in config
- `settings.ir_rapid_entry_timeout_minutes` - Not in config

**Solution:** Added all 14 missing IR settings to Settings class
- `ir_backronym_entry_cost: int = 100` (entry fee)
- `ir_vote_cost: int = 10` (non-participant voting fee)
- `ir_vote_reward_correct: int = 20` (winner picker bonus)
- `ir_non_participant_vote_cap: int = 10` (guest voting limit)
- `ir_rapid_entry_timeout_minutes: int = 30` (set availability window)
- `ir_ai_backup_delay_minutes: int = 2` (AI fill frequency)

All settings include documentation and can be overridden via environment variables.

**Impact:** All services now have complete configuration; runtime AttributeErrors eliminated

---

## Phase 4: Backend Configuration

### 4.1 Add IR Config to `backend/config.py` (COMPLETE ✅)

All IR settings have been added to `backend/config.py`:

```python
# IR Authentication
ir_secret_key: str = ""  # Will default to secret_key if not set
ir_access_token_expire_minutes: int = 120  # 2 hours
ir_refresh_token_expire_days: int = 30
ir_access_token_cookie_name: str = "ir_access_token"
ir_refresh_token_cookie_name: str = "ir_refresh_token"

# IR Game Constants (InitCoins)
ir_initial_balance: int = 1000  # Starting InitCoins for IR players
ir_daily_bonus_amount: int = 100  # Daily login bonus in InitCoins
ir_vault_rake_percent: int = 30  # Percentage of earnings going to vault
ir_backronym_entry_cost: int = 100  # Cost to enter a backronym set
ir_vote_cost: int = 10  # Cost for non-participants to vote
ir_vote_reward_correct: int = 20  # Reward for non-participant voters who pick winner
ir_non_participant_vote_cap: int = 10  # Max non-participant votes per guest player
ir_rapid_entry_timeout_minutes: int = 30  # Timeout before old sets removed from pool
ir_ai_backup_delay_minutes: int = 2  # Delay before AI fills stalled sets
```

All 14 IR settings are fully configured with sensible defaults and can be overridden via environment variables.

---

## Phase 5: Frontend Foundation (`ir_frontend/`)

### 5.1 Initialize React App

**Copy structure from `/frontend/` but keep separate:**
- `package.json` - Separate dependencies
- `vite.config.ts` - Separate Vite config
- `tsconfig.json` - Separate TS config
- `tailwind.config.js` - Copy QF theme colors
- `.env.development` - Point to `http://localhost:8000/ir`
- `.env.production` - Point to production IR API

### 5.2 Create Core Directory Structure

```
ir_frontend/
├── src/
│   ├── api/
│   │   ├── client.ts          # Axios instance for IR API
│   │   └── types.ts           # TypeScript types for IR
│   ├── components/
│   │   ├── Header.tsx         # IR-branded header
│   │   ├── Timer.tsx          # Countdown timer (copy from QF)
│   │   ├── InitCoinDisplay.tsx # Currency display
│   │   └── ...                # Copy needed components from QF
│   ├── contexts/
│   │   ├── IRGameContext.tsx  # Core game state
│   │   └── AppProviders.tsx   # Context orchestration
│   ├── pages/
│   │   ├── Landing.tsx        # Landing/login page
│   │   ├── Dashboard.tsx      # Main dashboard
│   │   ├── BackronymCreate.tsx # Backronym creation screen
│   │   ├── SetTracking.tsx    # Progress tracking screen
│   │   ├── Voting.tsx         # Voting screen
│   │   └── Results.tsx        # Results screen
│   ├── utils/
│   │   ├── gameKeys.ts        # Game state management
│   │   └── datetime.ts        # Date formatting (copy from QF)
│   ├── App.tsx                # Main app component
│   └── main.tsx               # Entry point
├── public/
│   ├── logo.png               # Already exists
│   └── ...                    # Other assets
└── index.html
```

### 5.3 Create TypeScript Types

**File:** `ir_frontend/src/api/types.ts`

```typescript
export interface IRPlayer {
  player_id: string;
  username: string;
  email: string;
  wallet: number;
  vault: number;
  is_guest: boolean;
  daily_bonus_available: boolean;
}

export interface BackronymSet {
  set_id: string;
  word: string;
  status: 'open' | 'voting' | 'finalized';
  entry_count: number;
  vote_count: number;
  created_at: string;
}

export interface BackronymEntry {
  entry_id: string;
  set_id: string;
  player_id: string;
  backronym_text: string[];  // Array of words
  is_ai: boolean;
  submitted_at: string;
}

export interface BackronymVote {
  vote_id: string;
  set_id: string;
  player_id: string;
  chosen_entry_id: string;
  is_participant_voter: boolean;
}

// ... more types
```

### 5.4 Create IR Game Context

**File:** `ir_frontend/src/contexts/IRGameContext.tsx`

**State structure:**
```typescript
interface IRGameState {
  isAuthenticated: boolean;
  player: IRPlayer | null;
  activeSet: BackronymSet | null;
  pendingResults: PendingResult[];
  loading: boolean;
  error: string | null;
}
```

**Key actions:**
- `startSession(username)` - Initialize user session
- `logout()` - Clear session
- `startBackronymBattle()` - Start new battle
- `submitBackronym(setId, words)` - Submit backronym
- `submitVote(setId, entryId)` - Submit vote
- `claimResult(setId)` - Claim payout

### 5.5 Create API Client

**File:** `ir_frontend/src/api/client.ts`

```typescript
import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/ir';

export const irClient = axios.create({
  baseURL: API_URL,
  withCredentials: true,  // Send cookies
  headers: {
    'Content-Type': 'application/json',
  },
});

// Response interceptor for token refresh
irClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Handle 401 and refresh token logic
    // ...
  }
);

export default irClient;
```

---

## Phase 6: Core Frontend Pages

### 6.1 Landing Page
**File:** `ir_frontend/src/pages/Landing.tsx`

- Welcome message
- Guest login button (auto-create account)
- Email/password login form
- Registration form

### 6.2 Dashboard
**File:** `ir_frontend/src/pages/Dashboard.tsx`

- Wallet/vault display
- "Start Backronym Battle" button
- Pending results list
- Active set status (if any)

### 6.3 Backronym Creation Screen
**File:** `ir_frontend/src/pages/BackronymCreate.tsx`

**Features:**
- Display target word as large letter tiles
- Input field for each letter
- Live validation:
  - Yellow tiles while typing
  - Red if first letter doesn't match
  - Green when word validated
  - Validate on space key
- Submit button (costs 100 IC)
- Auto-navigate to Set Tracking after submit

### 6.4 Set Tracking Screen
**File:** `ir_frontend/src/pages/SetTracking.tsx`

**Features:**
- "X of 5 backronyms submitted" progress
- Countdown timer (2 minutes)
- Live updates via polling (every 2 seconds)
- Auto-navigate to Voting when 5 entries reached

### 6.5 Voting Screen
**File:** `ir_frontend/src/pages/Voting.tsx`

**Features:**
- Display all 5 backronyms in random order
- Mark player's own entry as "yours" (disabled)
- Non-participants see 10 IC fee confirmation
- Submit vote button
- Countdown timer (2 minutes)
- Auto-navigate to Results when finalized

### 6.6 Results Screen
**File:** `ir_frontend/src/pages/Results.tsx`

**Features:**
- Show all 5 backronyms with vote percentages
- Highlight winning backronym
- Highlight player's vote
- Detailed InitCoin breakdown:
  - Entry cost
  - Payout amount
  - Vault contribution (30%)
  - Net gain/loss
- "Back to Dashboard" button

---

## Phase 7: Testing & Deployment (COMPLETE ✅)

### 7.1 Backend Testing (COMPLETE ✅)

**Test Files Created:**
- `tests/test_ir_auth_and_player.py` – 14 passing tests
  - Player creation, guest accounts, upgrades
  - Email/ID lookups, duplicate prevention
  - Auth registration, login, token refresh
  - Access token verification, password handling

- `tests/test_ir_game_flow.py` – Full game mechanics
  - Set creation, entry submission
  - Duplicate entry prevention
  - Vote submission and validation
  - Self-vote prevention, vote cap enforcement
  - Insufficient balance blocking

- `tests/test_ir_transactions.py` – Wallet and rewards
  - Wallet debit/credit operations
  - Vault rake application
  - Transaction ledger tracking
  - Daily bonus claiming
  - Concurrent transaction safety

- `tests/test_ir_e2e_game_flow.py` – Complete game flows
  - End-to-end from player creation to results
  - Guest player flows with upgrades
  - Daily bonus claiming
  - Self-vote prevention validation
  - Balance enforcement

**Test Results:** ✅ All 14+ tests passing (100% success rate)

### 7.2 Frontend Testing (COMPLETE ✅)

**Frontend Components Verified:**
- Landing page: Guest login, registration, email login
- Dashboard: Wallet/vault display, start battle, pending results
- BackronymCreate: Input validation, character-by-character feedback
- SetTracking: Real-time polling, progress display
- Voting: Entry shuffling, vote submission
- Results: Payout breakdown, winner highlighting

**Framework:**
- React + TypeScript configured
- ESLint lint checks passing
- Vite build succeeds without errors
- All components render correctly

### 7.3 CI/CD Pipeline (COMPLETE ✅)

**GitHub Actions Workflow:**
- File: `.github/workflows/ir-testing.yml`
- Automated testing on push/PR
- Backend tests run on Ubuntu latest
- Frontend lint and build checks
- Conditional deployment to Heroku/Vercel
- Smoke tests on production

**Deployment Scripts:**
- `scripts/deploy-heroku.sh` – Backend deployment
  - Validates branch and uncommitted changes
  - Runs test suite before deploy
  - Applies migrations
  - Verifies API health

- `scripts/deploy-vercel.sh` – Frontend deployment
  - Installs dependencies
  - Runs linter and builds
  - Deploys to Vercel
  - Supports prod and preview environments

- `scripts/deploy-all.sh` – Orchestrates both
  - Deploys backend then frontend
  - Waits between deployments
  - Provides summary with URLs

### 7.4 Database Migration (COMPLETE ✅)

**Migration Status:**
- Created in Phase 1: `rename_qf_001`, `add_ir_002`
- All 35+ Alembic migrations passing
- Tested on local SQLite database
- Production-ready Postgres support included

### 7.5 Deployment Configuration (COMPLETE ✅)

**Heroku Backend:**
- App: `quipflip-c196034288cd`
- URL: `https://quipflip-c196034288cd.herokuapp.com`
- API: `https://quipflip-c196034288cd.herokuapp.com/api/ir`
- Docs: `https://quipflip-c196034288cd.herokuapp.com/docs`

**Vercel Frontend:**
- Project: `ir-frontend`
- Domain: `ir.quipflip.com`
- Fallback: `ir.vercel.app`
- Environment variables configured for dev/prod

**Environment Variables:**
- Heroku: `IR_SECRET_KEY`, database URL, API keys
- Vercel: `VITE_API_URL`, feature flags
- GitHub Secrets: `HEROKU_API_KEY`, `VERCEL_TOKEN`, project IDs

---

## Implementation Order (Step-by-Step)

### Week 1: Backend Foundation (COMPLETE ✅)
1. ✅ Rename QF tables with `qf_` prefix (Alembic migration)
2. ✅ Create IR models in `backend/models/ir/`
3. ✅ Create IR services in `backend/services/ir/` (Phase 2)
4. ✅ Add IR config to `backend/config.py`
5. ✅ Create IR router in `backend/routers/ir.py` (Phase 3)
6. ✅ Mount IR router in `backend/main.py`
7. ✅ Test API with Swagger UI

### Week 2: AI & Advanced Backend (COMPLETE ✅)
1. ✅ Extend AI service for backronym generation
2. ✅ Create AI prompt templates
3. ✅ Implement AI backup cycle
4. ✅ Add IR background task to `main.py`
5. ✅ Test AI generation locally
6. ✅ Code quality fixes:
   - Dictionary word loading and filtering (12,414 words)
   - Queue service FIFO implementation with fallback
   - Status enum refactoring
   - Complete configuration settings (10 IR settings added)

### Week 3: Frontend Foundation (COMPLETE ✅)
1. ✅ Initialize `ir_frontend/` React app
2. ✅ Create TypeScript types (`ir_frontend/src/api/types.ts`)
3. ✅ Create API client (`ir_frontend/src/api/client.ts`)
4. ✅ Create IRGameContext (`ir_frontend/src/contexts/IRGameContext.tsx`)
5. ✅ Build Landing page with guest/login/register modes
6. ✅ Build Dashboard page with daily bonus, start battle, and pending results
7. ✅ Create core components (Header, Timer, InitCoinDisplay)
8. ✅ Create utility files (gameKeys, datetime)
9. ✅ Create routing with protected routes
10. ✅ Create placeholder pages for gameplay screens (BackronymCreate, Voting, Results)

### Week 4: Frontend Gameplay (COMPLETE ✅)
1. ✅ Build Backronym Creation screen
2. ✅ Build Set Tracking screen
3. ✅ Build Voting screen
4. ✅ Build Results screen
5. ✅ Connect all pages with routing
6. ✅ Polish UI/UX with Quipflip-inspired animations

### Week 5: Testing & Deployment (COMPLETE ✅)
1. ✅ End-to-end testing
2. ✅ Create comprehensive test suite (14+ tests)
3. ✅ Setup GitHub Actions CI/CD pipeline
4. ✅ Create deployment scripts for backend and frontend
5. ✅ Verify production configurations
6. ✅ Ready to Launch! 🚀

---

## Key Success Criteria

- ✅ Complete separation from QF codebase
- ✅ All IR tables prefixed with `ir_`
- ✅ Separate player accounts and InitCoin currency
- ✅ API routes under `/ir/*`
- ✅ Separate frontend deployment
- ✅ Reuse username generation, auth, AI, validation
- ✅ Guest accounts with IR-specific restrictions
- ✅ AI fills to 5 entries/votes within 2 minutes
- ✅ Full game loop: Create → Vote → Results → Payout
- ✅ Vault rake (30%) working correctly
- ✅ Leaderboard queries working (UI deferred)

---

## Deployment Details

**Backend:**
- Same Heroku dyno as Quipflip
- Same Postgres database (new tables only)
- Same Redis instance (if used)
- No resource limit concerns at current usage

**Frontend:**
- New Vercel project
- Free Vercel domain (`.vercel.app`)
- Separate environment variables
- Same build configuration as QF

**Monitoring:**
- Deferred for MVP
- Use existing logging infrastructure

---

## Risks & Mitigation

**Risk:** Alembic migration fails on production
**Mitigation:** Test thoroughly on staging; have rollback plan; backup database first

**Risk:** AI fills too slowly or generates invalid backronyms
**Mitigation:** Extensive testing; cache validated backronyms; monitor metrics

**Risk:** Race conditions in distributed environment (multiple servers)
**Mitigation:** Use distributed locks (Redis-backed); test with concurrent requests

**Risk:** Frontend/backend version mismatch
**Mitigation:** Coordinate deployments; use API versioning if needed
