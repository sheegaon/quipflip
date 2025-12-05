# ThinkLink Data Models

This guide documents the ThinkLink-specific tables housed under `backend/models/tl`. These models build on the shared base tables described in [DATA_MODELS.md](../DATA_MODELS.md) (players, tokens, transactions, notifications, and system configuration) and add the game entities unique to ThinkLink.

## Architecture Note

ThinkLink uses the **unified Player model with game-specific data delegation** pattern. See [DATA_MODELS.md Architecture Overview](../DATA_MODELS.md#architecture-overview) for details on how `Player` delegates game-specific fields to `TLPlayerData`.

## Core Models

### TLPlayerData (Game-Specific Player State)
- `player_id` (UUID, PK, FK to players.player_id) - unified player account reference
- `wallet` (integer, default 1000) - current spendable ThinkCoins balance. New accounts are seeded from `settings.tl_starting_balance` (1000 by default)
- `vault` (integer, default 0) - accumulated long-term ThinkCoins from earnings (30% rake)
- `tutorial_completed` (boolean, default false) - whether player has finished tutorial
- `tutorial_progress` (string, default 'not_started') - current tutorial step
- `tutorial_started_at` (timestamp, nullable) - when tutorial was started
- `tutorial_completed_at` (timestamp, nullable) - when tutorial was completed
- Indexes: `player_id`
- Constraints: PK on player_id (one-to-one relationship)
- Relationships: `player` (back-reference to unified Player)

**Note**: While these fields live in `TLPlayerData`, the `Player` model provides transparent access via property accessors, so frontend code can still use `player.tl_wallet`, `player.tl_vault`, etc.

### TLPrompt (Corpus Management)
- `prompt_id` (UUID, PK, default=uuid.uuid4) - unique prompt identifier
- `text` (string, max 500, indexed) - the question/prompt (e.g., "Name something people forget at home")
- `embedding` (Vector(1536), nullable) - OpenAI text-embedding-3-small vector for on-topic validation
- `is_active` (boolean, default true) - whether prompt is available for rounds
- `ai_seeded` (boolean, default false) - whether prompt was auto-generated (vs manually curated)
- `created_at` (timestamp with timezone) - creation time
- Indexes: `is_active`, `text`
- Relationships: `answers` (one-to-many)

**Usage**: Prompts are loaded on-demand as rounds start. `is_active=true` filters available prompts. Embeddings enable semantic validation that guesses are on-topic.

### TLAnswer (Community Corpus)
- `answer_id` (UUID, PK) - unique answer identifier
- `prompt_id` (UUID, FK to tl_prompt) - the prompt this answers
- `text` (string) - the answer text (e.g., "Keys")
- `embedding` (Vector(1536), nullable) - semantic embedding for matching
- `cluster_id` (UUID, nullable, FK to tl_cluster) - which semantic cluster this belongs to
- `answer_players_count` (integer, default 1) - how many unique players submitted this exact text
- `shows` (integer, default 0) - how many rounds this answer appeared in (for usefulness calculation)
- `contributed_matches` (integer, default 0) - how many times a guess matched this answer
- `is_active` (boolean, default true) - whether answer is available for matching
- `created_at` (timestamp with timezone)
- Indexes: `prompt_id`, `cluster_id`
- Relationships: `prompt`, `cluster`, `guesses`

**Usefulness Formula**: `contributed_matches / (shows + 1)` - used for corpus pruning. Answers with better match rate are kept.

### TLCluster (Semantic Grouping)
- `cluster_id` (UUID, PK) - unique cluster identifier
- `prompt_id` (UUID, FK to tl_prompt) - which prompt's answers this clusters
- `centroid_embedding` (Vector(1536), nullable) - running-mean centroid of all answers in cluster
- `size` (integer) - number of answers in this cluster
- `example_answer_id` (UUID, nullable, FK to tl_answer) - representative answer for display
- `created_at` (timestamp with timezone)
- Indexes: `prompt_id`
- Relationships: `prompt`, `answers`

**Clustering Logic**:
- New answers are compared to existing clusters using cosine similarity
- **Join Threshold (0.75)**: If similarity > 0.75 to any cluster, add to that cluster
- **Duplicate Threshold (0.90)**: If similarity > 0.90 to any answer, reject as duplicate
- **Centroid Update**: Running mean: `(old_centroid * n + new_embedding) / (n + 1)`
- **Match Threshold (0.55)**: Used during matching - guesses scoring > 0.55 to ANY answer in cluster count as match

### TLRound (Game Session)
- `round_id` (UUID, PK) - unique round identifier
- `player_id` (UUID, FK to players, indexed) - which player started this round
- `prompt_id` (UUID, FK to tl_prompt) - which prompt is being guessed
- `status` (string, enum: 'active', 'abandoned') - round state
- `snapshot_answer_ids` (JSON list) - frozen corpus IDs at round start (up to 1000 active answers)
- `snapshot_cluster_ids` (JSON list) - frozen cluster IDs from snapshot
- `snapshot_total_weight` (float) - total weight of snapshot clusters (for coverage calc)
- `matched_clusters` (JSON list) - cluster IDs that were matched during this round
- `strikes` (integer, default 0, range 0-3) - strike count (round ends at 3)
- `final_coverage` (float, nullable) - matched_weight / snapshot_weight (only set on finalize)
- `gross_payout` (integer, nullable) - calculated payout before vault rake (only set on finalize)
- `ended_at` (timestamp, nullable) - when round finished
- `created_at` (timestamp with timezone, indexed)
- Indexes: `player_id`, `prompt_id`, `created_at`
- Relationships: `player`, `prompt`, `guesses`, `transactions`

**Round Flow**:
1. Player starts round → snapshot frozen, entry cost deducted
2. Player submits guesses up to 3 strikes
3. Each match adds matched clusters
4. 3 strikes or player abandons → round ends
5. Coverage calculated, payout finalized

### TLGuess (Submission Log)
- `guess_id` (UUID, PK) - unique guess identifier
- `round_id` (UUID, FK to tl_round, indexed) - which round this guess belongs to
- `text` (string) - what the player guessed (e.g., "My wallet")
- `embedding` (Vector(1536)) - semantic embedding of guess
- `was_match` (boolean) - whether this guess matched any answers
- `matched_answer_ids` (JSON list) - answer IDs that matched
- `matched_cluster_ids` (JSON list) - cluster IDs that matched
- `caused_strike` (boolean) - whether this guess caused a strike (no match = true)
- `created_at` (timestamp with timezone)
- Indexes: `round_id`, `created_at`
- Relationships: `round`

**Matching Process**:
1. Phrase validation (format, dictionary, prompt overlap)
2. Embedding generation
3. On-topic check vs prompt (threshold 0.40)
4. Self-similarity check vs prior guesses (threshold 0.80)
5. Find matches in snapshot answers (threshold 0.55)
6. If matches found: update matched_clusters, mark as_match=true
7. If no matches: add strike, mark caused_strike=true

### TLTransaction (Economic Log)
- `transaction_id` (UUID, PK) - unique transaction identifier
- `player_id` (UUID, FK to players, indexed) - which player's wallet affected
- `round_id` (UUID, nullable, FK to tl_round) - associated round (if any)
- `amount` (integer) - coins added (positive) or removed (negative)
- `transaction_type` (string) - 'round_entry', 'round_payout', 'round_abandon_refund', 'daily_bonus'
- `description` (string) - human-readable description (e.g., "Round entry: Name something...")
- `created_at` (timestamp with timezone)
- Indexes: `player_id`, `round_id`, `created_at`
- Relationships: `player`, `round`

**Transaction Types**:
- `round_entry` (-100): Entry cost when starting round
- `round_payout` (+amount): Payout when round finalized
- `round_abandon_refund` (+95): Partial refund when abandoning (100 - 5 penalty)
- `daily_bonus` (+100): Daily login bonus

### TLChallenge (v2 Placeholder)
- `challenge_id` (UUID, PK) - unique challenge identifier
- `player_id` (UUID, FK to players) - who initiated the challenge
- `opponent_id` (UUID, nullable, FK to players) - target opponent (null if open)
- `prompt_id` (UUID, FK to tl_prompt) - shared prompt
- `status` (string) - 'pending', 'accepted', 'rejected', 'in_progress', 'completed'
- `created_at` (timestamp with timezone)
- Relationships: `player`, `opponent`, `prompt`

**Note**: v1 does not implement challenges. This table exists for schema completeness only.

## Thresholds & Constants

All configurable via `backend/config.py`:

### Game Economics
- `tl_starting_balance`: 1000 ThinkCoins
- `tl_entry_cost`: 100 ThinkCoins per round
- `tl_max_payout`: 300 ThinkCoins (hard cap)
- `tl_daily_bonus_amount`: 100 ThinkCoins
- `tl_vault_rake_percent`: 30% of earnings go to vault

### Semantic Thresholds
- `tl_match_threshold`: 0.55 - cosine similarity to count as match
- `tl_cluster_join_threshold`: 0.75 - add to existing cluster
- `tl_cluster_duplicate_threshold`: 0.90 - reject as duplicate
- `tl_topic_threshold`: 0.40 - minimum similarity to prompt
- `tl_self_similarity_threshold`: 0.90 - reject if too similar to own prior guess

### Corpus Management
- `tl_active_corpus_cap`: 1000 - max active answers per prompt
- Pruning keeps top ~1000 by usefulness when exceeded

### Scoring
- `tl_payout_exponent`: 1.5 - coverage curve exponent
- Payout formula: `300 * (coverage ** 1.5)` (capped at 300)
- Breakeven at ~100 coins: above 100, 30% goes to vault

## Relationships Summary

```
Player
  ├── TLPlayerData (1:1)
  ├── TLRound (1:many) - player_id
  ├── TLTransaction (1:many) - player_id
  └── TLChallenge (1:many) - player_id or opponent_id

TLPrompt
  ├── TLRound (1:many) - prompt_id
  ├── TLAnswer (1:many) - prompt_id
  └── TLCluster (1:many) - prompt_id

TLAnswer
  ├── TLCluster (FK) - cluster_id
  └── TLGuess (referenced in matched_answer_ids)

TLCluster
  ├── TLRound (referenced in matched_clusters)
  └── TLGuess (referenced in matched_cluster_ids)

TLRound
  ├── TLGuess (1:many) - round_id
  └── TLTransaction (1:many) - round_id
```

## Embedding Storage

- **Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Storage**: SQLAlchemy `Vector(1536)` type
  - PostgreSQL: Native pgvector `vector(1536)` type
  - SQLite (dev): JSON-encoded text (pgvector fallback)
- **Caching**: MatchingService caches embeddings in-memory per session
- **Reuse**: Same text always produces same embedding (OpenAI deterministic)

## Snapshot Freezing

Rounds capture a **snapshot** of the corpus at start time:
- Limits answers to ~1000 most recent/active (by `created_at` DESC)
- Prevents corpus changes mid-round from affecting guesses
- `snapshot_answer_ids` and `snapshot_cluster_ids` are immutable JSON lists
- Coverage calculation uses only snapshot clusters

## Naming Conventions

- **Coins**: "ThinkCoins" (or "Coins" in UI)
- **Answers**: Community-submitted responses (e.g., "Keys", "Wallet")
- **Guesses**: Player submissions during a round (e.g., "My keys")
- **Coverage**: Matched cluster weight / total snapshot weight (0.0 to 1.0)
- **Usefulness**: `contributed_matches / (shows + 1)` - metric for pruning
