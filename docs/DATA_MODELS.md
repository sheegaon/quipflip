# Data Models

## Core Models

### Player
- `player_id` (UUID, primary key)
- `username` (string, unique) - **automatically generated** random display name (player cannot choose or change)
- `username_canonical` (string, unique) - lowercase form for lookups
- `email` (string, unique) - player email for authentication
- `password_hash` (string) - bcrypt hashed password
- `wallet` (integer, database default 1000) - current spendable Flipcoin balance for entering rounds and transactions. New accounts are seeded from `settings.starting_balance` (5000f by default) when created via the service layer.
- `vault` (integer, database default 0) - accumulated long-term Flipcoin balance from net earnings (30% rake). Used for leaderboard rankings.
- `created_at` (timestamp)
- `last_login_date` (timestamp with timezone, nullable) - UTC timestamp for last login tracking
- `active_round_id` (UUID, nullable, references rounds.round_id) - enforces one-round-at-a-time
- `is_guest` (boolean, default false) - whether this is a guest account with auto-generated credentials
- `tutorial_completed` (boolean, default false) - whether player has finished tutorial
- `tutorial_progress` (string, default 'not_started') - current tutorial step (`not_started`, `welcome`, `dashboard`, `prompt_round`, `copy_round`, `vote_round`, `completed_rounds_guide`, `completed`)
- `tutorial_started_at` (timestamp, nullable) - when tutorial was started
- `tutorial_completed_at` (timestamp, nullable) - when tutorial was completed
- `is_admin` (boolean, default false) - admin privileges flag for administrative access
- `locked_until` (timestamp with timezone, nullable) - account lock expiration time (for temporary bans/suspensions)
- `flag_dismissal_streak` (integer, default 0) - tracks consecutive flags submitted by this player that were dismissed by an admin. Higher number indicates poor flagging history. Player is locked for 24 hours when streak reaches 5, then streak resets to 0. Streak resets to 0 when a flag is confirmed.
- `consecutive_incorrect_votes` (integer, default 0) - tracks incorrect votes for guest accounts
- `vote_lockout_until` (timestamp with timezone, nullable) - guest vote lockout expiration when too many incorrect votes
- Indexes: `player_id`, `active_round_id`
- Constraints: Unique `username_canonical`
- Relationships: `active_round`, `rounds`, `transactions`, `votes`, `daily_bonuses`, `result_views`, `abandoned_prompts`, `phraseset_activities`, `refresh_tokens`, `quests`, `survey_responses`

**Authentication**: JWT access/refresh tokens (stored in `refresh_tokens` table)
**Registration**:
- Guest accounts: Created via `POST /player/guest` with auto-generated credentials (email: `guest####@quipflip.xyz`, password: `QuipGuest`)
- Full accounts: Created via `POST /player` with email and password; username is randomly generated and cannot be changed
- Upgrade: Guest accounts can be upgraded to full accounts via `POST /player/upgrade`
**Admin Access**: Controlled by `is_admin` field (boolean flag) combined with email-based authorization in admin endpoints
**Moderation**: Account locking (`locked_until`) and vote lockout (`vote_lockout_until`) for guest accounts with excessive incorrect votes

### Round (Unified for Prompt, Copy, and Vote)
- `round_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed)
- `round_type` (string) - 'prompt', 'copy', 'vote'
- `status` (string) - 'active', 'submitted', 'expired', 'abandoned'
- `created_at` (timestamp, indexed)
- `expires_at` (timestamp, indexed)
- `cost` (integer) - amount deducted (prompt: 100, copy: 50 or 40 with discount, vote: 10)

- **Prompt-specific fields** (nullable for non-prompt rounds):
  - `prompt_id` (UUID, references prompts.prompt_id)
  - `prompt_text` (string) - denormalized for performance
  - `submitted_phrase` (string, nullable) - prompt player's phrase
  - `phraseset_status` (string, nullable) - 'waiting_copies', 'waiting_copy1', 'active', 'voting', 'closing', 'finalized', 'abandoned'
  - `copy1_player_id` (UUID, nullable, references players.player_id, indexed)
  - `copy2_player_id` (UUID, nullable, references players.player_id, indexed)

- **Copy-specific fields** (nullable for non-copy rounds):
  - `prompt_round_id` (UUID, references rounds.round_id, indexed) - links to original prompt
  - `original_phrase` (string) - the phrase to copy
  - `copy_phrase` (string, nullable) - copy player's submitted phrase
  - `system_contribution` (integer, default 0) - 0 or 10 for discounted copies

- **Vote-specific fields** (nullable for non-vote rounds):
  - `phraseset_id` (UUID, references phrasesets.phraseset_id, indexed) - assigned phraseset for voting
  - `vote_submitted_at` (timestamp, nullable)

- Indexes: `round_id`, `player_id`, `created_at`, `expires_at`, `copy1_player_id`, `copy2_player_id`, `prompt_round_id`, `phraseset_id`, composite `(status, created_at)`, `phraseset_status`
- Relationships: `player`, `prompt`, `phraseset`, `copy1_player`, `copy2_player`, `prompt_round`, `hints`
- Note: Using single table with nullable fields for cleaner queries and simpler schema

### Prompt (Library)
- `prompt_id` (UUID, primary key)
- `text` (string, unique) - e.g., "my deepest desire is to be (a/an)"
- `category` (string) - 'simple', 'deep', 'silly', 'fun', 'abstract'
- `created_at` (timestamp)
- `usage_count` (integer, default 0) - tracking for rotation
- `avg_copy_quality` (float, nullable) - for future optimization
- `enabled` (boolean, default true) - allow disabling problematic prompts
- Indexes: `prompt_id`
- Relationships: `rounds`, `feedbacks`

### Phraseset
- `phraseset_id` (UUID, primary key)
- `prompt_round_id` (UUID, references rounds.round_id, indexed)
- `copy_round_1_id` (UUID, references rounds.round_id)
- `copy_round_2_id` (UUID, references rounds.round_id)
- `prompt_text` (string) - denormalized for display
- `original_phrase` (string) - prompt player's phrase
- `copy_phrase_1` (string) - first copy player's phrase
- `copy_phrase_2` (string) - second copy player's phrase
- `status` (string, default 'open') - 'open', 'closing', 'closed', 'finalized'
- `vote_count` (integer, default 0)
- `third_vote_at` (timestamp, nullable) - starts 10-minute window
- `fifth_vote_at` (timestamp, nullable, indexed) - starts 60-second window
- `closes_at` (timestamp, nullable) - calculated closure time
- `created_at` (timestamp)
- `finalized_at` (timestamp, nullable)
- `total_pool` (integer, default 200) - base prize pool (prompt + copies) before vote contributions
- `vote_contributions` (integer, default 0) - total Flipcoins contributed by vote entry fees
- `vote_payouts_paid` (integer, default 0) - total paid out to correct voters
- `system_contribution` (integer, default 0) - 0 or 10 for discounted copies
- `second_copy_contribution` (integer, default 0) - 0 or 50 when both copies from same player
- Indexes: `phraseset_id`, `prompt_round_id`, `fifth_vote_at`, composite `(status, vote_count)`
- Relationships: `prompt_round`, `copy_round_1`, `copy_round_2`, `votes`, `vote_rounds`, `result_views`, `activities`
- Note: Phrase positions randomized per-voter, NOT stored in database
- Note: System contribution is already included in base prize pool
- Note: Second copy contribution is added to pool when both copies come from same player (2nd copy costs 100 FC, base includes 50 FC, so 50 FC is added)

### Vote
- `vote_id` (UUID, primary key)
- `phraseset_id` (UUID, references phrasesets.phraseset_id, indexed)
- `player_id` (UUID, references players.player_id, indexed)
- `voted_phrase` (string) - the actual phrase voted for
- `correct` (boolean) - whether vote was for original
- `payout` (integer) - gross payout (5 or 0)
- `created_at` (timestamp, indexed) - for vote timeline tracking
- Indexes: `vote_id`, `phraseset_id`, `player_id`, `created_at`
- Constraints: Unique composite `(player_id, phraseset_id)` - one vote per player per phraseset
- Relationships: `phraseset`, `player`

### Notification
- `notification_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed) - notification recipient
- `notification_type` (string) - `copy_submitted` or `vote_submitted`
- `phraseset_id` (UUID, references phrasesets.phraseset_id, indexed) - affected phraseset
- `actor_player_id` (UUID, references players.player_id, nullable) - player that triggered the notification
- `data` (JSON, nullable) - denormalized metadata used by the frontend (`phrase_text`, `recipient_role`, `actor_username`)
- `created_at` (timestamp with timezone) - when notification was persisted
- Indexes: composite `('player_id', 'created_at')` for rate limiting + history lookups, `phraseset_id`
- Relationships: `player`, `actor_player`, `phraseset`
- Notes: Records are created for every delivered/attempted notification so we can audit delivery counts, enforce the "10 per minute" rate limit, and add future notification center functionality

### ResultView
- `view_id` (UUID, primary key)
- `phraseset_id` (UUID, references phrasesets.phraseset_id, indexed)
- `player_id` (UUID, references players.player_id, indexed)
- `result_viewed` (boolean, default false, indexed)
- `payout_amount` (integer) - prize pool payout for contributor
- `viewed_at` (timestamp) - most recent view timestamp
- `first_viewed_at` (timestamp, nullable) - when the player first saw the results
- `result_viewed_at` (timestamp, nullable) - when result_viewed flipped to true
- Indexes: `view_id`, `phraseset_id`, `player_id`, `result_viewed`
- Constraints: Unique composite `(player_id, phraseset_id)` - one view record per player per phraseset
- Relationships: `phraseset`, `player`
- Note: Used for idempotent prize collection

### Transaction (Ledger)
- `transaction_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed)
- `amount` (integer) - can be negative for charges, positive for payouts
- `type` (string, indexed) - transaction type
  - Core types: `prompt_entry`, `copy_entry`, `vote_entry`, `vote_payout`, `prize_payout`, `refund`, `daily_bonus`, `system_contribution`
  - Quest rewards: `quest_reward_hot_streak`, `quest_reward_deceptive_copy`, `quest_reward_obvious_original`, `quest_reward_round_completion`, `quest_reward_balanced_player`, `quest_reward_login_streak`, `quest_reward_feedback`, `quest_reward_milestone`
  - Vault types: `vault_rake` (30% of net earnings deposited to vault)
- `wallet_type` (string, default 'wallet') - which balance this transaction affects: 'wallet' or 'vault'
- `reference_id` (UUID, nullable, indexed) - references round_id, phraseset_id, vote_id, or quest_id depending on type
- `wallet_balance_after` (integer, nullable) - wallet balance after this transaction (for audit)
- `vault_balance_after` (integer, nullable) - vault balance after this transaction (for audit)
- `created_at` (timestamp, indexed)
- Indexes: `transaction_id`, `player_id`, `type`, `reference_id`, `created_at`, composite `(player_id, created_at)`
- Relationships: `player`
- Note: All balance changes MUST create transaction record for audit trail. Net earnings from rounds are automatically split: 70% to wallet, 30% to vault (via `vault_rake` transaction).

### DailyBonus
- `bonus_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed)
- `amount` (integer, default 100)
- `claimed_at` (timestamp)
- `date` (date, indexed) - UTC date for tracking one per day
- Indexes: `bonus_id`, `player_id`, `date`
- Constraints: Unique composite `(player_id, date)` - one bonus per player per day
- Relationships: `player`
- Note: Separate table for easy daily bonus queries and analytics

### PlayerAbandonedPrompt (Cooldown Tracking)
- `id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed)
- `prompt_round_id` (UUID, references rounds.round_id)
- `abandoned_at` (timestamp)
- Indexes: `player_id`
- Constraints: Unique composite `(player_id, prompt_round_id)` - tracks unique player-prompt abandonment
- Relationships: `player`
- Note: Prevents same player from getting same abandoned prompt within 24h
- Note: Can be cleaned up periodically (delete records older than 24h)

### RefreshToken
- `token_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed, cascade delete)
- `token_hash` (string, indexed) - hashed refresh token
- `expires_at` (timestamp)
- `created_at` (timestamp)
- `revoked_at` (timestamp, nullable) - when token was revoked
- Indexes: `token_id`, `player_id`, `token_hash`
- Relationships: `player` (cascade delete)
- Methods: `is_active(now)` - returns True if token has not expired or been revoked
- Note: Stores JWT refresh tokens for authentication, automatically deleted when player is deleted

### PromptFeedback
- `feedback_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed, cascade delete)
- `prompt_id` (UUID, references prompts.prompt_id, indexed, cascade delete)
- `round_id` (UUID, references rounds.round_id, indexed, cascade delete)
- `feedback_type` (string) - 'like' or 'dislike'
- `last_updated_at` (timestamp) - auto-updates on modification
- Indexes: `player_id`, `prompt_id`, `round_id`
- Constraints: Unique composite `(player_id, round_id)` - one feedback per player per round
- Relationships: `player`, `prompt`, `round`
- Note: Tracks player feedback on prompts for quality improvement and quest progress

### SurveyResponse
- `response_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed, cascade delete)
- `survey_id` (string, indexed) - currently `beta_oct_2025`
- `payload` (JSONB) - serialized answers array captured from the frontend
- `created_at` (timestamp with timezone, default now())
- Indexes: `player_id`, `survey_id`, unique composite `(player_id, survey_id)`
- Relationships: `player`
- Note: Stores one submission per player for each in-app survey; payload is schema-less for flexibility

---

## Supporting Models

### Quest
- `quest_id` (UUID, primary key)
- `player_id` (UUID, references players.player_id, indexed)
- `quest_type` (string, indexed) - type identifier (matches QuestType enum)
  - Streak quests: `hot_streak_5`, `hot_streak_10`, `hot_streak_20`
  - Quality quests: `deceptive_copy`, `obvious_original`
  - Activity quests: `round_completion_5`, `round_completion_10`, `round_completion_20`, `balanced_player`, `login_streak_7`
  - Feedback quests: `feedback_contributor_10`, `feedback_contributor_50`
  - Milestone quests: `milestone_votes_100`, `milestone_prompts_50`, `milestone_copies_100`, `milestone_phraseset_20votes`
- `status` (string, default 'active', indexed) - 'active', 'completed', 'claimed'
- `progress` (JSON, default {}) - flexible progress tracking
- `reward_amount` (integer) - Flipcoin reward for completion
- `created_at` (timestamp)
- `completed_at` (timestamp, nullable)
- `claimed_at` (timestamp, nullable)
- Indexes: `quest_id`, `player_id`, `quest_type`, `status`, composite `(player_id, status)`, unique composite `(player_id, quest_type)`
- Relationships: `player`
- Note: Tracks individual player quest progress and completion

### QuestTemplate
- `template_id` (string, primary key) - matches QuestType values
- `name` (string) - display name
- `description` (string) - quest description
- `reward_amount` (integer) - Flipcoin reward
- `target_value` (integer) - goal threshold
- `category` (string) - 'streak', 'quality', 'activity', 'milestone'
- Note: Configuration for quest definitions, referenced when creating Quest instances

### PhrasesetActivity
- `activity_id` (UUID, primary key)
- `phraseset_id` (UUID, nullable, references phrasesets.phraseset_id, indexed)
- `prompt_round_id` (UUID, nullable, references rounds.round_id, indexed)
- `activity_type` (string) - type of activity/event
- `player_id` (UUID, nullable, references players.player_id, indexed)
- `payload` (JSON, nullable, column name: 'metadata') - flexible activity data
- `created_at` (timestamp)
- Indexes: `phraseset_id`, `prompt_round_id`, `player_id`, composite `(phraseset_id, created_at)`, composite `(prompt_round_id, created_at)`, composite `(player_id, created_at)`
- Relationships: `phraseset`, `prompt_round`, `player`
- Note: Activity log for tracking phraseset lifecycle events and player interactions

### WeeklyLeaderboardCache
- `storage` (Redis key) - `leaderboard:weekly:v5`
- `payload.prompt_leaderboard` (array) - cached leaderboard rows for prompt role
  - `player_id` (UUID string)
  - `username` (string)
  - `role` (string) - "prompt"
  - `total_costs` (integer)
  - `total_earnings` (integer)
  - `net_earnings` (integer) - earnings minus costs
  - `win_rate` (float) - percentage of rounds with positive earnings (0-100)
  - `total_rounds` (integer) - number of rounds played in this role
  - `rank` (integer)
- `payload.copy_leaderboard` (array) - cached leaderboard rows for copy role
  - Same structure as `prompt_leaderboard` with `role: "copy"`
- `payload.voter_leaderboard` (array) - cached leaderboard rows for voter role
  - Same structure as `prompt_leaderboard` with `role: "voter"`
- `payload.gross_earnings_leaderboard` (array) - cached vault balance leaderboard across all roles
  - `player_id` (UUID string)
  - `username` (string)
  - `gross_earnings` (integer) - change in vault balance for weekly, or total vault balance for all-time
  - `total_rounds` (integer) - total rounds played across all roles
  - `rank` (integer)
- `payload.generated_at` (ISO 8601 string) - timestamp when snapshot was calculated
- TTL: 3600 seconds (1 hour) per write
- Refresh triggers: automatically recomputed when phrasesets finalize, and on-demand when cache miss occurs
- Note: Role leaderboards are ranked by win rate (descending) with ties broken alphabetically by username. Gross earnings leaderboard ranks by vault balance (weekly: change in vault, all-time: total vault). Personalization flags (`is_current_player`) are added at request time; the shared cache only stores objective rankings.
- AI players (email ending in `@quipflip.internal`) are excluded from all leaderboards.
- Computation: All role leaderboards and gross earnings leaderboard are computed concurrently using `asyncio.gather` for performance.

### AIPhraseCache
- `cache_id` (UUID, primary key)
- `prompt_round_id` (UUID, foreign key to rounds.round_id, unique, indexed, cascade delete)
- `original_phrase` (string, max 100 chars) - denormalized from prompt round
- `prompt_text` (string, max 500 chars, nullable) - denormalized from prompt round
- `validated_phrases` (JSON) - list of 3-5 validated copy phrases
- `generation_provider` (string, max 50 chars) - AI provider used ('openai' or 'gemini')
- `generation_model` (string, max 100 chars) - specific model identifier
- `created_at` (timestamp, indexed)
- `used_for_backup_copy` (boolean, default false) - whether cache was used for AI backup copies
- `used_for_hints` (boolean, default false) - whether cache was used for player hints
- Indexes: `prompt_round_id` (unique), `created_at`
- Constraints: Unique `prompt_round_id` - one cache per prompt round
- Relationships: `prompt_round`, `metrics`
- Note: Stores pre-validated copy phrases for reuse. Generated once per prompt_round, eliminates redundant AI API calls. Backup copies consume phrases (removed from list), hints don't consume phrases (all players get same hints).

### AIMetric
- `metric_id` (UUID, primary key)
- `operation_type` (string, indexed) - 'copy_generation', 'vote_generation', or 'hint_generation'
- `provider` (string, indexed) - 'openai' or 'gemini'
- `model` (string) - model identifier (e.g., 'gpt-5-nano', 'gemini-2.5-flash-lite')
- `success` (boolean, indexed) - whether operation succeeded
- `latency_ms` (integer, nullable) - response time in milliseconds
- `error_message` (string, nullable) - error details if failed
- `estimated_cost_usd` (float, nullable) - estimated cost in USD
- `prompt_length` (integer, nullable) - prompt length in characters
- `response_length` (integer, nullable) - response length in characters
- `validation_passed` (boolean, nullable) - for copy generation: whether phrase passed validation
- `vote_correct` (boolean, nullable) - for vote generation: whether AI vote was correct
- `cache_id` (UUID, nullable, foreign key to ai_phrase_cache.cache_id, set null on delete, indexed) - links to phrase cache used/generated
- `created_at` (timestamp, indexed)
- Indexes: `metric_id`, `operation_type`, `provider`, `success`, `created_at`, `cache_id`, composite `(created_at, success)`, composite `(operation_type, provider)`, composite `(operation_type, created_at)`
- Relationships: `phrase_cache`
- Note: Tracks AI usage, costs, performance, and success rates for analytics and optimization

### Hint (DEPRECATED)
- `hint_id` (UUID, primary key)
- `prompt_round_id` (UUID, references rounds.round_id, cascade delete, indexed via composite)
- `hint_phrases` (JSON) - array of AI-generated hint phrases (1-3 strings)
- `created_at` (timestamp with timezone, default now(), indexed)
- `generation_provider` (string, max 20 chars) - AI provider used ('openai' or 'gemini')
- `generation_model` (string, max 100 chars, nullable) - specific model identifier
- Indexes: composite `(prompt_round_id, created_at)`
- Constraints: Unique `prompt_round_id` - one hint record per prompt round
- Relationships: `prompt_round` (references Round, back_populates="hints")
- Note: **DEPRECATED - replaced by AIPhraseCache.** Stores AI-generated copy hints for copy rounds to assist players. Hints are cached to avoid regeneration costs and are free to request during active copy rounds. New implementations should use AIPhraseCache instead, which provides both hints and backup copies from a single generation.

### FlaggedPrompt
- `flag_id` (UUID, primary key)
- `prompt_round_id` (UUID, references rounds.round_id, cascade delete, indexed)
- `copy_round_id` (UUID, nullable, references rounds.round_id, set null on delete, indexed)
- `reporter_player_id` (UUID, references players.player_id, cascade delete, indexed)
- `prompt_player_id` (UUID, references players.player_id, cascade delete, indexed)
- `status` (string, max 20 chars, default 'pending', indexed) - 'pending', 'confirmed', 'dismissed'
- `created_at` (timestamp with timezone, default now())
- `reviewed_at` (timestamp with timezone, nullable)
- `reviewer_player_id` (UUID, nullable, references players.player_id, set null on delete, indexed)
- `original_phrase` (string, max 100 chars) - the flagged phrase
- `prompt_text` (string, max 500 chars, nullable) - prompt text for context
- `previous_phraseset_status` (string, max 20 chars, nullable) - phraseset status before flagging
- `queue_removed` (boolean, default false) - whether the prompt was removed from queue
- `round_cost` (integer) - cost of the flagged round
- `partial_refund_amount` (integer) - amount refunded to reporter
- `penalty_kept` (integer) - penalty amount kept from reporter
- Indexes: `prompt_round_id`, `copy_round_id`, `reporter_player_id`, `prompt_player_id`, `reviewer_player_id`, `status`
- Relationships: `reporter`, `prompt_player`, `reviewer`, `prompt_round`, `copy_round`
- Note: Tracks player-reported flags on prompt phrases during copy rounds for admin review

### SystemConfig
- `key` (string, max 100 chars, primary key) - configuration key name
- `value` (text) - configuration value as string
- `value_type` (string, max 20 chars) - data type: 'int', 'float', 'string', 'bool'
- `description` (text, nullable) - human-readable description of the setting
- `category` (string, max 50 chars, nullable) - configuration category: 'economics', 'timing', 'validation', 'ai'
- `updated_at` (timestamp with timezone, default now()) - last update timestamp
- `updated_by` (string, max 100 chars, nullable) - player_id of admin who updated
- Note: Stores dynamic system configuration values that can be updated without code deployment. Values override environment variable defaults.

### UserActivity
- `player_id` (UUID, primary key)
- `username` (string, max 255 chars) - denormalized for quick lookups
- `last_action` (string, max 100 chars) - human-readable description of last action
- `last_action_category` (string, max 50 chars, default 'other') - action category (e.g., `round_prompt`, `review`, `stats`, `quests`, `economy`, `tutorial`, `account`, `notifications`, `feedback`)
- `last_action_path` (text) - API endpoint path of last action
- `last_activity` (timestamp with timezone) - UTC timestamp of last activity
- Indexes: `player_id`, `last_activity`
  - `last_activity`: **BRIN index on PostgreSQL** (Block Range Index, optimal for monotonically increasing timestamps, space-efficient) / **B-tree index on SQLite** (for local development)
- Relationships: Implicitly references `player` (not a formal foreign key relationship to avoid cascading issues)
- Note: Tracks real-time user online status for "Who's Online" feature. Distinct from phraseset_activity which logs historical review events. Records updated on each authenticated API call. Users shown as "online" if `last_activity` is within last 30 minutes. The index on `last_activity` provides efficient querying for the 30-minute activity window and enables fast sorting for the online users list.

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
`prompt_text` stored in both Prompt and Phraseset tables:
- **Pros**: Faster queries, no joins needed for display
- **Cons**: Data duplication
- **Decision**: Denormalize for read performance (game is read-heavy)

### JSON Progress Tracking
Quest progress stored as JSON field:
- **Pros**: Flexible for different quest types, easy to extend
- **Cons**: Less structured, requires application-level validation
- **Decision**: Use JSON for flexibility in quest system

### Activity Logging
PhrasesetActivity uses flexible JSON payload:
- **Pros**: Can track diverse event types without schema changes
- **Cons**: Queries on payload data are less efficient
- **Decision**: Use JSON for flexibility in activity tracking and future analytics.
- **Common activity types**: `vote_submitted`, `third_vote_reached`, `fifth_vote_reached`, `finalized`, and `finalization_error` (raised when a phraseset is closed due to missing round references).

### Wallet/Vault Split
Player balances split into wallet (spendable) and vault (accumulated earnings):
- **Wallet**: Used for all spending (round entry costs, etc.). Quest rewards and bonuses go 100% to wallet.
- **Vault**: Receives 30% of net earnings from rounds. Used for leaderboard rankings.
- **Earnings Split**: When a player earns more than their entry cost (net > 0), 70% of net goes to wallet, 30% to vault. If net ≤ 0, all gross earnings return to wallet.
- **Pros**: Creates a permanent wealth accumulation metric for leaderboards, encourages strategic play for net profit
- **Cons**: Slightly more complex transaction logic
- **Decision**: Implement split system to create meaningful long-term player progression and competitive leaderboards based on skill rather than volume.
