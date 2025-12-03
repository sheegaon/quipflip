# ThinkLink Implementation Plan (v1)

## Executive Summary

ThinkLink is a semantic-matching game where players guess answers that match the crowd's prior answers. This plan outlines how to implement ThinkLink v1 (solo play) by reusing existing QuipFlip (QF) and MemeMint (MM) infrastructure while building the game-specific semantic matching, clustering, and scoring systems.

**v1 Scope**: Solo gameplay with unlimited guesses, strike-based termination, and weighted semantic coverage scoring.

**v2 Scope** (deferred): Head-to-head challenge mode with shared snapshots and real-time competition.

## Game Mechanics Overview

**Core Loop:**
1. Player receives a prompt (e.g., "Name something people forget at home")
2. Player makes unlimited guesses trying to match crowd's semantic answer space
3. Valid guesses with no matches cause strikes (3 strikes = round end)
4. Scoring based on weighted coverage of crowd's clustered answer space
5. Economic model: 100 coin entry, max 300 coin payout (net +200 possible)

**Key Technical Features:**
- Semantic matching via OpenAI embeddings (`text-embedding-3-small`, 1536-dim)
- Dynamic clustering of answers (cosine similarity ≥ 0.75 to join cluster)
- Weighted coverage scoring (popular clusters worth more)
- Active corpus cap (K=1000 answers per prompt)
- Round-based snapshots (frozen at start, unchanged during play)

## Architecture Mapping to Existing System

### Backend Structure

```
backend/
├── routers/tl/              # ThinkLink-specific routes
│   ├── __init__.py
│   ├── rounds.py            # Round lifecycle (start, submit, abandon)
│   ├── game.py              # Game state, prompts, dashboard
│   └── admin.py             # Prompt seeding, corpus management
├── models/tl/               # ThinkLink data models
│   ├── __init__.py
│   ├── player_data.py       # TLPlayerData (wallet, vault, tutorial)
│   ├── prompt.py            # TLPrompt
│   ├── answer.py            # TLAnswer (with embedding vector)
│   ├── cluster.py           # TLCluster (centroid embeddings)
│   ├── round.py             # TLRound (snapshot-based)
│   └── challenge.py         # TLChallenge (v2, stub for future)
├── services/tl/             # ThinkLink business logic
│   ├── __init__.py
│   ├── round_service.py     # Round orchestration
│   ├── matching_service.py  # Semantic matching engine
│   ├── clustering_service.py # Cluster assignment & maintenance
│   ├── scoring_service.py   # Coverage calculation & payouts
│   └── prompt_service.py    # Prompt selection & seeding
└── schemas/tl/              # Pydantic request/response models
    ├── __init__.py
    ├── round.py             # Round-related schemas
    ├── game.py              # Dashboard, balance schemas
    └── admin.py             # Admin operation schemas
```

**Shared Infrastructure to Reuse:**
- Authentication (JWT, cookies, ws-token) - **existing, no changes**
- Player account (unified `players` table) - **existing, add TLPlayerData**
- Transaction ledger pattern - **reuse from QF**
- Quest system - **adapt for TL-specific quests**
- Admin config pattern - **add TL-specific settings**
- Phrase validation (word lists, moderation) - **reuse QF validator**
- AI service pattern - **adapt for prompt seeding only**

### Frontend Structure

```
frontend/
├── crowdcraft/              # Shared components (reuse)
│   ├── components/          # Header, SubHeader, modals, etc.
│   ├── contexts/            # Base context patterns
│   └── utils/               # API client, helpers
└── tl/                      # ThinkLink SPA
    ├── src/
    │   ├── contexts/
    │   │   ├── GameContext.tsx        # Auth, balance, dashboard
    │   │   ├── RoundContext.tsx       # Round state management
    │   │   └── AppProviders.tsx       # Context orchestration
    │   ├── pages/
    │   │   ├── Dashboard.tsx          # Main landing page
    │   │   ├── RoundPlay.tsx          # Gameplay UI
    │   │   ├── RoundResults.tsx       # Post-game results
    │   │   └── RoundHistory.tsx       # Past rounds list
    │   ├── components/
    │   │   ├── GuessInput.tsx         # Strike-aware input
    │   │   ├── CoverageBar.tsx        # Live coverage meter
    │   │   ├── StrikeIndicator.tsx    # Visual strike counter
    │   │   └── MatchFeedback.tsx      # Matched cluster feedback
    │   └── api/
    │       └── client.ts               # TL-specific API client
    └── package.json
```

**Context Architecture (Adapted from QF):**
- **GameContext**: Auth, balance, dashboard polling
- **RoundContext**: Round-specific state (snapshot, guesses, strikes, coverage)
- **NetworkContext**: Reuse existing offline queue
- **NavigationHistoryContext**: Reuse existing
- **TutorialContext**: Simple TL tutorial (welcome → first round → done)

## Data Model Design

### Core Tables

**TLPlayerData** (game-specific, follows QF/MM/IR pattern):
```sql
CREATE TABLE tl_player_data (
    player_id UUID PRIMARY KEY REFERENCES players(player_id) ON DELETE CASCADE,
    wallet INTEGER NOT NULL DEFAULT 5000,
    vault INTEGER NOT NULL DEFAULT 0,
    tutorial_completed BOOLEAN NOT NULL DEFAULT FALSE,
    tutorial_progress VARCHAR(50) DEFAULT 'not_started',
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

**TLPrompt** (prompt corpus):
```sql
CREATE TABLE tl_prompt (
    prompt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    text TEXT NOT NULL,
    embedding vector(1536),  -- pgvector for on-topic checks
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    ai_seeded BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tl_prompt_active ON tl_prompt(is_active);
CREATE INDEX idx_tl_prompt_text ON tl_prompt(text);
```

**TLAnswer** (answer corpus with embeddings):
```sql
CREATE TABLE tl_answer (
    answer_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES tl_prompt(prompt_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    cluster_id UUID REFERENCES tl_cluster(cluster_id) ON DELETE SET NULL,
    answer_players_count INTEGER NOT NULL DEFAULT 0,  -- Distinct submitters
    shows INTEGER NOT NULL DEFAULT 0,
    contributed_matches INTEGER NOT NULL DEFAULT 0,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tl_answer_prompt ON tl_answer(prompt_id);
CREATE INDEX idx_tl_answer_cluster ON tl_answer(cluster_id);
CREATE INDEX idx_tl_answer_active ON tl_answer(is_active, prompt_id);
```

**TLCluster** (semantic clusters):
```sql
CREATE TABLE tl_cluster (
    cluster_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES tl_prompt(prompt_id) ON DELETE CASCADE,
    centroid_embedding vector(1536) NOT NULL,
    size INTEGER NOT NULL DEFAULT 1,
    example_answer_id UUID REFERENCES tl_answer(answer_id) ON DELETE SET NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tl_cluster_prompt ON tl_cluster(prompt_id);
```

**TLRound** (snapshot-based rounds):
```sql
CREATE TABLE tl_round (
    round_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    prompt_id UUID NOT NULL REFERENCES tl_prompt(prompt_id) ON DELETE CASCADE,
    snapshot_answer_ids JSONB NOT NULL,  -- Array of answer_ids
    snapshot_cluster_ids JSONB NOT NULL,  -- Array of cluster_ids
    matched_clusters JSONB NOT NULL DEFAULT '[]'::jsonb,  -- Updated during play
    strikes INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'active',  -- active, completed, abandoned
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    challenge_id UUID REFERENCES tl_challenge(challenge_id) ON DELETE SET NULL,  -- v2
    final_coverage FLOAT,  -- 0-1, set on completion
    gross_payout INTEGER,  -- 0-300, set on completion
    CONSTRAINT valid_strikes CHECK (strikes >= 0 AND strikes <= 3),
    CONSTRAINT valid_status CHECK (status IN ('active', 'completed', 'abandoned'))
);
CREATE INDEX idx_tl_round_player ON tl_round(player_id, created_at DESC);
CREATE INDEX idx_tl_round_status ON tl_round(status);
```

**TLChallenge** (v2 placeholder - not implemented in v1):
```sql
CREATE TABLE tl_challenge (
    challenge_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id UUID NOT NULL REFERENCES tl_prompt(prompt_id),
    initiator_player_id UUID NOT NULL REFERENCES players(player_id),
    opponent_player_id UUID NOT NULL REFERENCES players(player_id),
    initiator_round_id UUID REFERENCES tl_round(round_id),
    opponent_round_id UUID REFERENCES tl_round(round_id),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    time_limit_seconds INTEGER NOT NULL DEFAULT 300,
    started_at TIMESTAMP,
    ends_at TIMESTAMP,
    completed_at TIMESTAMP,
    winner_player_id UUID REFERENCES players(player_id),
    initiator_final_coverage FLOAT,
    opponent_final_coverage FLOAT,
    initiator_gross_payout INTEGER,
    opponent_gross_payout INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
-- NOTE: No v1 implementation, table structure ready for v2
```

**TLGuess** (submitted guesses log):
```sql
CREATE TABLE tl_guess (
    guess_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    round_id UUID NOT NULL REFERENCES tl_round(round_id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    embedding vector(1536) NOT NULL,
    was_match BOOLEAN NOT NULL,
    matched_answer_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    matched_cluster_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    caused_strike BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tl_guess_round ON tl_guess(round_id, created_at);
```

**TLTransaction** (follows QF transaction pattern):
```sql
CREATE TABLE tl_transaction (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    player_id UUID NOT NULL REFERENCES players(player_id) ON DELETE CASCADE,
    amount INTEGER NOT NULL,
    transaction_type VARCHAR(50) NOT NULL,  -- round_entry, round_payout, daily_bonus, etc.
    round_id UUID REFERENCES tl_round(round_id) ON DELETE SET NULL,
    description TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_tl_transaction_player ON tl_transaction(player_id, created_at DESC);
```

## Implementation Phases

### Phase 1: Backend Foundation (Week 1)

**1.1 Data Models & Migrations**
- [ ] Create `backend/models/tl/` package with `__init__.py`
- [ ] Implement `TLPlayerData` model with property accessors on `Player` base model
  - Add `tl_wallet`, `tl_vault`, `tl_tutorial_completed`, `tl_tutorial_progress` properties
  - Follow same pattern as `qf_wallet`, `mm_wallet`, etc.
- [ ] Implement `TLPrompt` model (text, embedding, is_active, ai_seeded)
- [ ] Implement `TLAnswer` model (text, embedding, cluster_id, stats fields)
- [ ] Implement `TLCluster` model (centroid_embedding, size, example_answer_id)
- [ ] Implement `TLRound` model (snapshot fields, strikes, status, coverage, payout)
- [ ] Implement `TLChallenge` model (stub structure, no logic in v1)
- [ ] Implement `TLGuess` model (guess log with embeddings and match results)
- [ ] Implement `TLTransaction` model (reuse transaction pattern from QF)
- [ ] Create Alembic migration for all tables
- [ ] Add pgvector extension requirement to migration
- [ ] Add all indexes (see schema above)

**1.2 Configuration**
- [ ] Add TL-specific settings to `backend/config.py`:
  ```python
  # ThinkLink Economics
  tl_starting_balance: int = 1000
  tl_entry_cost: int = 100
  tl_max_payout: int = 300
  tl_daily_bonus_amount: int = 100

  # ThinkLink Matching
  tl_match_threshold: float = 0.55
  tl_cluster_join_threshold: float = 0.75
  tl_cluster_duplicate_threshold: float = 0.90
  tl_topic_threshold: float = 0.40
  tl_self_similarity_threshold: float = 0.80

  # ThinkLink Corpus
  tl_active_corpus_cap: int = 1000

  # ThinkLink Scoring
  tl_payout_exponent: float = 1.5
  tl_vault_split_rate: float = 0.30

  # ThinkLink Rounds
  tl_round_grace_period_seconds: int = 5
  ```

**1.3 Core Services - Matching**
- [ ] Create `backend/services/tl/matching_service.py`:
  - `MatchingService` class
  - `generate_embedding(text: str) -> List[float]`:
    - Call OpenAI embeddings API (`text-embedding-3-small`)
    - Return 1536-dim vector
    - Cache in memory to avoid duplicate API calls
  - `cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float`:
    - Vectorized dot product computation
    - Use NumPy for efficiency
  - `find_matches(guess_embedding, snapshot_answers, threshold=0.55) -> List[AnswerMatch]`:
    - Compare guess embedding to all snapshot answer embeddings
    - Return list of matches with similarity scores
    - Sort by similarity descending
  - `check_self_similarity(guess_embedding, prior_guesses, threshold=0.80) -> bool`:
    - Compare to player's own prior guesses in this round
    - Return True if too similar (reject guess)
  - `check_on_topic(prompt_embedding, guess_embedding, threshold=0.40) -> bool`:
    - Validate guess is semantically related to prompt

**1.4 Core Services - Clustering**
- [ ] Create `backend/services/tl/clustering_service.py`:
  - `ClusteringService` class
  - `assign_cluster(answer_embedding, prompt_id) -> UUID`:
    - Load all cluster centroids for prompt
    - Find best match (highest cosine similarity)
    - If sim ≥ 0.75: assign to cluster, update centroid
    - Else: create new cluster
    - Return cluster_id
  - `update_centroid(cluster_id, new_embedding)`:
    - Running mean: `new_centroid = (old * n + new) / (n + 1)`
    - Update cluster size
  - `calculate_cluster_weight(cluster_id) -> float`:
    - Sum answer weights for all answers in cluster
    - Answer weight: `1 + log(1 + min(answer_players_count, 20))`
  - `prune_corpus(prompt_id, keep_count=1000)`:
    - Calculate usefulness for each answer: `contributed_matches / (shows + 1)`
    - Sort by usefulness * weight
    - Mark lowest-ranked answers as inactive
    - Preserve cluster diversity (don't remove all members of a cluster)

### Phase 2: Round & Scoring Logic (Week 2)

**2.1 Services - Prompt & Round**
- [ ] Create `backend/services/tl/prompt_service.py`:
  - `PromptService` class
  - `get_random_active_prompt() -> TLPrompt`:
    - Weighted random selection (prefer prompts with fuller corpus)
  - `seed_prompts_from_csv(filepath: str)`:
    - Bulk import prompts from CSV (text column)
    - Generate embeddings for each
    - Mark as active
  - `seed_ai_answers(prompt_id, count=50)`:
    - Call OpenAI to generate diverse answers
    - Validate each (phrase validator, on-topic, moderation)
    - Embed and cluster
    - Store with ai_seeded=True

- [ ] Create `backend/services/tl/round_service.py`:
  - `RoundService` class
  - `start_round(player_id) -> TLRound`:
    - Verify player has ≥100 coins
    - Deduct 100 coins (transaction: round_entry)
    - Select prompt via PromptService
    - Build snapshot:
      - Query up to 1000 active answers for prompt
      - Load cluster assignments and weights
      - Store snapshot_answer_ids, snapshot_cluster_ids as JSON
    - Create TLRound record (status=active)
    - Return round with prompt text
  - `submit_guess(round_id, player_id, guess_text) -> GuessResult`:
    - Validate ownership and round is active
    - Validate phrase (QF validator: 2-5 words, NASPA, moderation)
    - Generate embedding
    - Check on-topic (prompt vs guess)
    - Check self-similarity (reject if ≥0.80 to prior guesses)
    - Find matches in snapshot answers
    - If matches found:
      - Identify matched clusters
      - Update round.matched_clusters (union with new)
      - Log guess (was_match=True)
    - Else:
      - Increment strikes
      - Log guess (was_match=False, caused_strike=True)
      - If strikes == 3: auto-finalize round
    - Return: matched (bool), new_coverage (float), strikes (int), match_details
  - `abandon_round(round_id, player_id)`:
    - Verify ownership and round is active
    - Partial refund: 95 coins (5 coin penalty)
    - Mark round status=abandoned, ended_at=now
    - Transaction: round_abandon_refund
  - `finalize_round(round_id)`:
    - Calculate final_coverage via ScoringService
    - Calculate payouts via ScoringService
    - Update player wallet/vault
    - Write transactions
    - Update answer stats (shows, contributed_matches)
    - Mark round status=completed, ended_at=now

**2.2 Services - Scoring**
- [ ] Create `backend/services/tl/scoring_service.py`:
  - `ScoringService` class
  - `calculate_coverage(round: TLRound) -> float`:
    - Load cluster weights for matched_clusters
    - Load total snapshot weight (W_total)
    - Coverage p = Σ(matched cluster weights) / W_total
    - Clamp to [0, 1]
  - `calculate_payout(coverage: float) -> Tuple[int, int, int]`:
    - Gross = round(300 * (coverage ** 1.5))
    - Clamp gross to [0, 300]
    - If gross ≤ 100:
      - wallet_award = gross, vault_award = 0
    - Else:
      - extra = gross - 100
      - vault_award = int(extra * 0.30)
      - wallet_award = gross - vault_award
    - Return (wallet_award, vault_award, gross)
  - `update_answer_stats(round: TLRound)`:
    - For all snapshot answers: increment shows
    - For matched answers: increment contributed_matches

### Phase 3: API Endpoints (Week 2-3)

**3.1 Router Setup**
- [ ] Create `backend/routers/tl/__init__.py` with router registration
- [ ] Mount router in `backend/main.py` at `/tl` prefix
- [ ] Add CORS configuration for TL routes

**3.2 Game Endpoints**
- [ ] Create `backend/routers/tl/game.py`:
  - `GET /tl/player/dashboard`:
    - Response: { player: {wallet, vault, tutorial}, activeRound, roundAvailability }
    - Reuse QF dashboard pattern
  - `GET /tl/player/balance`:
    - Response: { wallet, vault, daily_bonus_available }
  - `POST /tl/player/claim-daily-bonus`:
    - Reuse QF daily bonus logic
    - +100 coins to wallet
  - `GET /tl/prompts/preview`:
    - Return random prompt text (no round creation)
    - For browsing/curiosity

**3.3 Round Endpoints**
- [ ] Create `backend/routers/tl/rounds.py`:
  - `POST /tl/rounds/start`:
    - Request: none
    - Response: { round_id, prompt_id, prompt_text, created_at }
  - `POST /tl/rounds/{round_id}/guess`:
    - Request: { guess_text }
    - Response: {
        success, guess_text, was_match,
        matched_clusters: [{cluster_id, example_answer}],
        strikes, current_coverage, round_status
      }
  - `POST /tl/rounds/{round_id}/abandon`:
    - Response: { round_id, status: 'abandoned', refund_amount: 95 }
  - `GET /tl/rounds/{round_id}`:
    - Response: full round details (prompt, strikes, coverage, status)
  - `GET /tl/rounds/{round_id}/history`:
    - Response: { guesses: [{text, was_match, caused_strike, created_at}] }
    - Post-game review
  - `GET /tl/rounds/{round_id}/results`:
    - Response: {
        prompt_text, final_coverage, gross_payout, wallet_award, vault_award,
        total_clusters, matched_clusters, strikes_used,
        cluster_breakdown: [{cluster_id, example_answer, weight, matched}]
      }

**3.4 Admin Endpoints**
- [ ] Create `backend/routers/tl/admin.py`:
  - `POST /tl/admin/prompts/seed` (admin only):
    - Request: CSV upload or JSON array of prompt texts
    - Seeds prompts via PromptService
  - `POST /tl/admin/prompts/{prompt_id}/seed-answers` (admin only):
    - Generate AI answers for prompt
    - Call PromptService.seed_ai_answers()
  - `GET /tl/admin/corpus/{prompt_id}`:
    - View active answers, clusters, stats
  - `POST /tl/admin/corpus/{prompt_id}/prune`:
    - Manually trigger pruning to K=1000

**3.5 Schemas**
- [ ] Create `backend/schemas/tl/` package
- [ ] `round.py`: RoundStart, GuessRequest, GuessResponse, RoundDetails, RoundResults
- [ ] `game.py`: DashboardResponse, BalanceResponse, PromptPreview
- [ ] `admin.py`: SeedPromptsRequest, SeedAnswersRequest, CorpusView

### Phase 4: Frontend - Foundation (Week 3-4)

**4.1 Project Setup**
- [ ] Create `frontend/tl/` directory
- [ ] Copy Vite config from `frontend/qf/` (adapt for TL)
- [ ] Configure TypeScript with `@crowdcraft/*` imports
- [ ] Set up Tailwind CSS
- [ ] Configure routing (React Router)
- [ ] Create `frontend/tl/src/api/client.ts` and `types.ts`:
  - Axios instance with base URL `/tl`
  - withCredentials: true
  - Same interceptors as QF (auth, error handling)

**4.2 Core Contexts**
- [ ] Create `frontend/tl/src/contexts/GameContext.tsx`:
  - State: { isAuthenticated, username, player, loading, error }
  - Actions: startSession, logout, refreshBalance, claimBonus
  - Polling: dashboard every 30s when authenticated
  - Reuse QF GameContext structure
  - Copy QF `NetworkContext.tsx`, `ResultsContext.tsx`, `TutorialContext.tsx` and modify for TL

- [ ] Create `frontend/tl/src/contexts/RoundContext.tsx`:
  - State: {
      currentRound: {round_id, prompt_text, strikes, coverage, status},
      guesses: [{text, was_match, caused_strike}],
      loading, error
    }
  - Actions: startRound, submitGuess, abandonRound, loadRoundResults
  - Clear state on round end

- [ ] Create `frontend/tl/src/contexts/AppProviders.tsx`:
  - Nest: NetworkProvider → GameContext → RoundContext → app
  - Reuse QF AppProviders pattern

**4.3 Shared Component Reuse**
- [ ] Import Header from `@crowdcraft/components`
- [ ] Import SubHeader from `@crowdcraft/components`
- [ ] Import modals (ErrorModal, ConfirmModal) from `@crowdcraft/components`
- [ ] Import BalanceFlipper from `@crowdcraft/components`
- [ ] Adapt styling/branding for TL (color scheme from QF, logos already exist)
- [ ] Copy and adapt components/hooks from QF/MM as needed

### Phase 5: Frontend - Gameplay UI (Week 4-5)

**5.1 Dashboard Page**
- [ ] Create `frontend/tl/src/pages/Dashboard.tsx`:
  - Adapt MM dashboard layout
  - Balance display (wallet, vault)
  - "Start Round" button (disabled if in active round)
  - Active round preview card (if round in progress)
    - "Resume Round" button → navigate to /play
  - Recent rounds history (5 most recent)
    - Coverage %, payout, date
  - Daily bonus claim button
  - Tutorial prompt (if not completed)

**5.2 Round Play Page**
- [ ] Create `frontend/tl/src/pages/RoundPlay.tsx`:
  - Prompt display (large, centered, readable font)
  - GuessInput component (submit on Enter)
  - StrikeIndicator component (3 circles)
  - CoverageBar component (0-100%)
  - MatchFeedback component (show recent matched cluster examples)
  - Abandon button (bottom, small, confirm modal)
  - Auto-redirect to results when round ends (strikes=3 or manual quit)

**5.3 Round Results Page**
- [ ] Create `frontend/tl/src/pages/RoundResults.tsx`:
  - Final coverage % (large, prominent)
  - Payout breakdown:
    - Gross payout
    - Wallet award (green)
    - Vault award (blue)
    - Net change (wallet award - 100)
  - Cluster summary:
    - Total clusters in snapshot
    - Clusters matched by you
    - Coverage %
  - Matched cluster list (expand to show example answers)
  - Guess history (show all guesses, mark strikes)
  - "Play Again" button → start new round

**5.4 Round History Page**
- [ ] Create `frontend/tl/src/pages/RoundHistory.tsx`:
  - Based on `Tracking.tsx` page from QF
  - Paginated list of past rounds
  - Each row: prompt (truncated), coverage %, payout, date
  - Click to view detailed results

**5.5 Seconday Pages**
- [ ] Copy QF/MM pages for Admin, BetaSurveyPage, GameHistory, Landing, Leaderboard, OnlineUsers, Quests, Settings, Statistics
- [ ] Modify navigation links in Header/SubHeader to include TL pages
- [ ] Update page titles and metadata for TL branding
- [ ] Ensure all pages use TL API client
- [ ] Add routing paths in main App component
- [ ] Leave core logic for v2

**5.6 Key Components**
- [ ] Create `frontend/tl/src/components/GuessInput.tsx`:
  - Text input field
  - Real-time validation feedback (word count, length)
  - Submit button (disabled during submission)
  - Loading spinner during API call
  - Error display (invalid word, off-topic, etc.)

- [ ] Create `frontend/tl/src/components/CoverageBar.tsx`:
  - Animated progress bar (0-100%)
  - Color gradient: red (0-30%) → yellow (30-70%) → green (70-100%)
  - Percentage label

- [ ] Create `frontend/tl/src/components/StrikeIndicator.tsx`:
  - 3 circles/icons (on brand color)
  - Empty/filled states
  - Flash red animation on new strike

- [ ] Create `frontend/tl/src/components/MatchFeedback.tsx`:
  - Show last 3 matched cluster examples
  - "You matched: 'keys', 'wallet', 'phone'..."
  - Fade in animation on new match
  - Clear on round end

### Phase 6: Tutorial & Polish (Week 5-6)

**6.1 Simple Tutorial**
- [ ] Create `frontend/tl/src/pages/Tutorial.tsx`:
  - Step 1: Welcome to ThinkLink
    - "Guess words that match what others have said"
  - Step 2: How to play
    - "Unlimited guesses, but 3 strikes and you're out"
    - "Higher coverage = bigger payout"
  - Step 3: Play your first round
    - Start tutorial round (use seeded prompt with easy matches)
    - Guide through first guess
  - Step 4: Complete
    - Mark tutorial as completed
- [ ] Integrate tutorial trigger on Dashboard (if not completed)
- [ ] Add "Skip Tutorial" option

**6.2 Backend Tutorial Support**
- [ ] Add tutorial endpoints (reuse QF pattern):
  - `GET /tl/player/tutorial/status`
  - `POST /tl/player/tutorial/progress`
  - `POST /tl/player/tutorial/reset`

**6.3 Polish & UX**
- [ ] Add loading states for all async actions
- [ ] Add error boundaries for crash recovery
- [ ] Add smooth transitions between pages
- [ ] Add tooltips for coverage, strikes, clusters
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Accessibility (ARIA labels, keyboard navigation)

### Phase 7: Testing & QA (Week 6-7)

**7.1 Backend Unit Tests**
- [ ] Test MatchingService:
  - Cosine similarity calculations
  - Self-similarity guard
  - On-topic validation
- [ ] Test ClusteringService:
  - Cluster assignment logic
  - Centroid updates
  - Pruning algorithm
- [ ] Test ScoringService:
  - Coverage calculation
  - Payout curve (verify math)
  - Vault split
- [ ] Test RoundService:
  - Round lifecycle (start → guess → finalize)
  - Strike logic
  - Snapshot freezing

**7.2 Backend Integration Tests**
- [ ] Complete round flow:
  - Start round → make guesses → reach 3 strikes → verify payout
- [ ] Multiple rounds with same prompt:
  - Verify snapshots are independent
- [ ] Corpus growth:
  - Submit new answers → verify clustering
  - Prune corpus → verify K=1000 cap
- [ ] Transaction ledger:
  - Verify all balance changes logged

**7.3 Frontend E2E Tests** (Playwright):
- [ ] Complete round flow:
  - Login → dashboard → start round → submit guesses → view results
- [ ] Strike mechanics:
  - Verify strike indicator updates
  - Verify round ends at 3 strikes
- [ ] Coverage updates:
  - Verify coverage bar updates after each guess
- [ ] Abandon flow:
  - Abandon round → verify refund

**7.4 Performance Testing**
- [ ] Load test embedding API:
  - 100 concurrent guesses
  - Verify response times <2s
- [ ] Database query performance:
  - Snapshot building (1000 answers)
  - Coverage calculation
  - Verify <500ms per operation
- [ ] Frontend rendering:
  - Verify smooth animations
  - No UI freezing during API calls

** 7.5 Linting & Code Quality**
- [ ] Run linters (npm run lint, npm run build)
- [ ] Fix all warnings/errors
- [ ] Start backend with `uvicorn` and verify no runtime warnings

### Phase 8: Deployment Prep (Week 7)

**8.1 Database Setup**
- [ ] Run migrations on production Postgres
- [ ] Install pgvector extension:
  ```sql
  CREATE EXTENSION IF NOT EXISTS vector;
  ```
- [ ] Verify indexes created

**8.2 Prompt Seeding**
- [ ] Use `backend/data/prompts.csv` CSV with ~300 curated prompts and `backend/data/prompt_completions.csv` for AI answers
- [ ] Upload to DB
- [ ] Run seed script: `POST /tl/admin/prompts/seed`
- [ ] Optional script to generate additional AI answers for all prompts:
  - Batch script to call `POST /tl/admin/prompts/{id}/seed-answers`
  - 40-60 answers per prompt
  - Save AI answers to CSV for record-keeping
- [ ] Verify corpus quality:
  - Check cluster distribution
  - Test a few prompts manually

**8.3 Configuration**
- [ ] Set environment variables:
  - `OPENAI_API_KEY` (embeddings)
  - `TL_ENTRY_COST=100`
  - `TL_MAX_PAYOUT=300`
  - `TL_MATCH_THRESHOLD=0.55`
  - `TL_CLUSTER_JOIN_THRESHOLD=0.75`
  - `TL_TOPIC_THRESHOLD=0.40`
  - `TL_ACTIVE_CORPUS_CAP=1000`
- [ ] Verify CORS settings for frontend domain

**8.4 Frontend Deployment**
- [ ] Build production bundle: `npm run build`
- [ ] Deploy to Vercel (new subdomain: `thinklink.vercel.app`)
- [ ] Configure Vercel proxy: `/api/tl/*` → Heroku backend `/tl/*`
- [ ] Set environment variables:
  - `VITE_API_URL` (backend URL)
  - `VITE_GAME_NAME=ThinkLink`
- [ ] Verify deployment:
  - Test login flow
  - Test round flow
  - Check console for errors

### Phase 9: Launch (Week 8)

**9.1 Soft Launch (Internal Testing)**
- [ ] Team plays 20+ rounds
- [ ] Collect feedback:
  - Coverage feels fair?
  - Prompts engaging?
  - Payout curve balanced?
- [ ] Monitor metrics:
  - Avg coverage per round
  - Avg payout
  - Avg guesses per round
  - Strike distribution
- [ ] Adjust thresholds if needed:
  - If coverage too low: lower match threshold
  - If coverage too high: raise match threshold
  - If clusters too coarse: lower cluster join threshold

**9.2 Public Launch**
- [ ] Add ThinkLink to shared Header navigation
- [ ] Announce on QF/MM player base (if cross-game marketing allowed)
- [ ] Create landing page explainer (how to play)
- [ ] Monitor adoption:
  - New players per day
  - Rounds per player
  - Retention rate

**9.3 Post-Launch Monitoring**
- [ ] Track OpenAI API usage and costs (should be low - embeddings are cheap)
- [ ] Monitor database performance (snapshot queries, clustering)
- [ ] Watch for edge cases:
  - Prompts with no matches
  - Extremely high/low coverage
  - Corpus pruning issues
- [ ] Collect player feedback via in-game survey (optional)

## Reuse Strategy Summary

### Backend Reuse (90% of infrastructure)
| Component | Reuse Level | Notes |
|-----------|-------------|-------|
| Authentication | 100% | JWT, cookies, ws-token - zero changes |
| Player model | 100% | Add TLPlayerData, reuse property accessor pattern |
| Transaction pattern | 100% | Same structure, TL-specific types |
| Phrase validator | 80% | Reuse word/moderation, add semantic checks |
| Admin config | 100% | Add TL settings to existing ConfigService |
| Database patterns | 100% | Same async SQLAlchemy setup |
| Quest system | 50% | Create TL-specific quest templates later |

### Frontend Reuse (85% of shared code)
| Component | Reuse Level | Notes |
|-----------|-------------|-------|
| Header/SubHeader | 100% | Direct import from @crowdcraft |
| Authentication flow | 100% | Login, logout, session - unchanged |
| Context architecture | 80% | Adapt GameContext, new RoundContext |
| API client pattern | 100% | Same Axios setup with cookies |
| Modals/UI components | 100% | ErrorModal, ConfirmModal, etc. |
| Routing structure | 100% | Dashboard → Play → Results pattern |
| Tutorial framework | 60% | Reuse structure, simplified flow |

### Net New Development (Unique to TL)
- **Embedding & Matching**: 100% new (core differentiator)
- **Clustering Engine**: 100% new (unique semantic grouping)
- **Snapshot System**: 100% new (frozen round state)
- **Coverage Scoring**: 100% new (weighted semantic coverage)
- **Challenge Mode Data Model**: Stub created, 0% implemented (v2 scope)

## Technical Considerations

### Vector Operations Performance
- **1000 comparisons per guess**: Fast on modern CPU (~10ms with NumPy)
- **Embedding caching**: Critical - never recompute same text
- **Batch operations**: Use vectorized NumPy operations for similarity
- **Future optimization**: pgvector for nearest-neighbor if scaling >1000 answers

### Embedding API Management
- **Cost**: ~$0.13/1M tokens, embeddings are cheap
- **Rate limits**: OpenAI allows high throughput
- **Caching strategy**:
  - Cache in memory during round (guess validation)
  - Store in database (answers, prompts)
  - Never make duplicate API calls

### Data Model Future-Proofing
- **TLChallenge table**: Structure exists, ready for v2
- **Round.challenge_id**: Foreign key ready
- **Snapshot system**: Works for both solo and challenge modes
- **Coverage calculation**: Independent of game mode

### Isolation from Other Games
- **Separate wallets/vaults**: TLPlayerData is game-specific
- **No cross-game transactions**: Each game has own transaction table
- **Shared only**: Authentication, player account, quest system
- **Future**: Could add cross-game leaderboards, but not v1 scope

## Success Criteria (v1 MVP)

**Launch Readiness:**
- [ ] Players can complete solo rounds end-to-end
- [ ] Scoring feels fair (avg coverage 40-60% for engaged players)
- [ ] No critical bugs in round finalization or payout
- [ ] Tutorial completable by new players
- [ ] 300 prompts seeded with 40+ AI answers each

**Week 1 Metrics:**
- [ ] 50+ players try ThinkLink
- [ ] 500+ rounds completed
- [ ] Avg coverage: 40-60%
- [ ] Avg payout: 150-200 coins (net +50 to +100)
- [ ] No database performance issues
- [ ] OpenAI API costs reasonable (<$20/week)

**Player Experience:**
- [ ] Tutorial completion rate >50%
- [ ] Multi-round players (3+ rounds) >30%
- [ ] Positive feedback on prompt quality
- [ ] No widespread complaints about fairness/bugs

## v2 Roadmap (Post-Launch)

**Challenge Mode Implementation** (4-6 weeks post-launch):
- Implement ChallengeService (shared snapshot, dual scoring)
- Add challenge endpoints (create, accept, guess, results)
- Build challenge UI (lobby, play, comparison results)
- Optional: WebSocket for live updates
- Test thoroughly (harder to QA than solo mode)

**Additional Features** (future):
- Quest system integration (TL-specific quests)
- Leaderboards (highest coverage, biggest payouts)
- Prompt voting (players rate/flag prompts)
- User-submitted prompts (moderated queue)
- Stats page (coverage distribution, cluster insights)
- Practice mode (no cost, no payout, learn clusters)

## Open Questions Resolved

✅ **Timeline**: 8 weeks is acceptable
✅ **Challenge Mode**: Defer to v2, data model supports it
✅ **Embedding Provider**: OpenAI only, no fallback needed
✅ **Prompt Curation**: Manual CSV imports
✅ **Vault Isolation**: Separate per game
✅ **Tutorial**: Simple v1 (welcome → play → done)
✅ **Cost Monitoring**: Not needed in v1

## Next Steps

1. **Review & Approve Plan**: Get stakeholder sign-off
2. **Create Jira/Linear Tickets**: Break down into sprint-sized tasks
3. **Set Up Dev Environment**: pgvector on local Postgres
4. **Phase 1 Kickoff**: Start with data models and migrations
5. **Weekly Check-ins**: Track progress against 8-week timeline
