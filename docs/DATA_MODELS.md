# Data Models

## Core Models

### Player
- `player_id` (UUID, primary key)
- `username` (string, unique) - generated display name
- `username_canonical` (string, unique) - lowercase form for lookups
- `pseudonym` (string, indexed) - display name for leaderboards/public views
- `pseudonym_canonical` (string) - lowercase form for lookups
- `email` (string, unique) - player email for authentication
- `password_hash` (string) - bcrypt hashed password
- `balance` (integer, default 1000) - current balance in whole dollars
- `created_at` (timestamp)
- `last_login_date` (date, nullable) - UTC date for daily bonus tracking
- `active_round_id` (UUID, nullable, references rounds.round_id) - enforces one-round-at-a-time
- `tutorial_completed` (boolean, default false) - whether player has finished tutorial
- `tutorial_progress` (string, default 'not_started') - current tutorial step
- `tutorial_started_at` (timestamp, nullable) - when tutorial was started
- `tutorial_completed_at` (timestamp, nullable) - when tutorial was completed
- Indexes: `player_id`, `active_round_id`, `pseudonym`

**Authentication**: JWT access/refresh tokens (stored in `refresh_tokens` table)

### Round (Unified for Prompt, Copy, and Vote)
- `round_id` (UUID, primary key)
- `player_id` (UUID, references player, indexed)
- `round_type` (enum: 'prompt', 'copy', 'vote')
- `status` (enum: 'active', 'submitted', 'expired', 'abandoned')
- `created_at` (timestamp)
- `expires_at` (timestamp, indexed)
- `cost` (integer) - amount deducted (100, 90, or 1)
-
- **Prompt-specific fields** (nullable for non-prompt rounds):
  - `prompt_id` (UUID, references prompt library)
  - `prompt_text` (string) - denormalized for performance
  - `submitted_phrase` (string, nullable) - prompt player's phrase
  - `phraseset_status` (string, nullable) - mirrors phraseset lifecycle while attached to the round
  - `copy1_player_id` / `copy2_player_id` (UUID, nullable) - contributors once assigned

- **Copy-specific fields** (nullable for non-copy rounds):
  - `prompt_round_id` (UUID, references rounds.round_id, indexed) - links to original prompt
  - `original_phrase` (string) - the phrase to copy
  - `copy_phrase` (string, nullable) - copy player's submitted phrase
  - `system_contribution` (integer, default 0) - 0 or 10 for discounted copies

- **Vote-specific fields** (nullable for non-vote rounds):
  - `phraseset_id` (UUID, references phraseset, indexed) - assigned phraseset for voting
  - `vote_submitted_at` (timestamp, nullable)

- Indexes: `round_id`, `player_id`, `status+created_at`, `expires_at`, `prompt_round_id`, `phraseset_id`
- Note: Using single table with nullable fields for cleaner queries and simpler schema

### Prompt (Library)
- `prompt_id` (UUID, primary key)
- `text` (string, unique) - e.g., "my deepest desire is to be (a/an)"
- `category` (enum: 'simple', 'deep', 'silly', 'fun', 'abstract')
- `created_at` (timestamp)
- `usage_count` (integer, default 0) - tracking for rotation
- `avg_copy_quality` (float, nullable) - for future optimization
- `enabled` (boolean, default true) - allow disabling problematic prompts
- Indexes: `prompt_id`, `enabled+category`

### PhraseSet
- `phraseset_id` (UUID, primary key)
- `prompt_round_id` (UUID, references rounds.round_id, indexed)
- `copy_round_1_id` (UUID, references rounds.round_id)
- `copy_round_2_id` (UUID, references rounds.round_id)
- `prompt_text` (string) - denormalized for display
- `original_phrase` (string) - prompt player's phrase
- `copy_phrase_1` (string) - first copy player's phrase
- `copy_phrase_2` (string) - second copy player's phrase
- `status` (enum: 'open', 'closing', 'closed', 'finalized')
- `vote_count` (integer, default 0)
- `third_vote_at` (timestamp, nullable) - starts 10-minute window
- `fifth_vote_at` (timestamp, nullable, indexed) - starts 60-second window
- `closes_at` (timestamp, nullable) - calculated closure time
- `created_at` (timestamp)
- `finalized_at` (timestamp, nullable)
- `total_pool` (integer, default 300) - includes system contribution if applicable
- `system_contribution` (integer, default 0) - 0 or 10 for discounted copies
- Indexes: `phraseset_id`, `prompt_round_id`, `status+vote_count`, `fifth_vote_at`
- Note: Phrase positions randomized per-voter, NOT stored in database

### Vote
- `vote_id` (UUID, primary key)
- `phraseset_id` (UUID, references phraseset, indexed)
- `player_id` (UUID, references player, indexed)
- `voted_phrase` (string) - the actual phrase voted for
- `correct` (boolean) - whether vote was for original
- `payout` (integer) - gross payout (5 or 0)
- `created_at` (timestamp, indexed) - for vote timeline tracking
- Indexes: `vote_id`, `phraseset_id`, `(player_id, phraseset_id)` unique composite, `created_at`

### ResultView
- `view_id` (UUID, primary key)
- `phraseset_id` (UUID, references phraseset, indexed)
- `player_id` (UUID, references player, indexed)
- `payout_claimed` (boolean, default false, indexed)
- `payout_amount` (integer) - prize pool payout for contributor
- `viewed_at` (timestamp) - most recent view timestamp
- `first_viewed_at` (timestamp, nullable) - when the player first saw the results
- `payout_claimed_at` (timestamp, nullable) - when payout_claimed flipped to true
- Indexes: `view_id`, `(player_id, phraseset_id)` unique composite, `payout_claimed`
- Note: Used for idempotent prize collection

### Transaction (Ledger)
- `transaction_id` (UUID, primary key)
- `player_id` (UUID, references player, indexed)
- `amount` (integer) - can be negative for charges, positive for payouts
- `type` (enum: 'prompt_entry', 'copy_entry', 'vote_entry', 'vote_payout', 'prize_payout', 'refund', 'daily_bonus', 'system_contribution')
- `reference_id` (UUID, nullable) - references round_id, phraseset_id, or vote_id depending on type
- `balance_after` (integer) - player balance after this transaction (for audit)
- `created_at` (timestamp, indexed)
- Indexes: `transaction_id`, `(player_id, created_at)`, `type`, `reference_id`
- Note: All balance changes MUST create transaction record for audit trail

### DailyBonus
- `bonus_id` (UUID, primary key)
- `player_id` (UUID, references player, indexed)
- `amount` (integer, default 100)
- `claimed_at` (timestamp)
- `date` (date, indexed) - UTC date for tracking one per day
- Indexes: `bonus_id`, `player_id`, `(player_id, date)` unique composite
- Note: Separate table for easy daily bonus queries and analytics

### PlayerAbandonedPrompt (Cooldown Tracking)
- `id` (UUID, primary key)
- `player_id` (UUID, references player, indexed)
- `prompt_round_id` (UUID, references rounds.round_id)
- `abandoned_at` (timestamp)
- Indexes: `(player_id, prompt_round_id)` unique composite
- Note: Prevents same player from getting same abandoned prompt within 24h
- Note: Can be cleaned up periodically (delete records older than 24h)

---

## Design Decisions

### Single Round Table
Using one table for all round types (prompt, copy, vote) with nullable fields:
- **Pros**: Simpler queries, easier to enforce one-round-at-a-time, cleaner foreign keys
- **Cons**: Some nullable fields, slightly larger row size
- **Decision**: Single table preferred for MVP simplicity

### No Stored Phrase Positions
Phrase order for voting randomized per-voter (not stored):
- **Pros**: Prevents pattern recognition from shared results
- **Cons**: Cannot reproduce exact view a voter saw
- **Decision**: Don't store, randomize on each GET request

### Transaction Balance Snapshot
Each transaction stores `balance_after`:
- **Pros**: Easy balance verification, audit trail, can reconstruct balance at any point
- **Cons**: Slight redundancy
- **Decision**: Include for audit and debugging

### Denormalized Fields
`prompt_text` stored in both Prompt and PhraseSet tables:
- **Pros**: Faster queries, no joins needed for display
- **Cons**: Data duplication
- **Decision**: Denormalize for read performance (game is read-heavy)
