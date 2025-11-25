# Data Model Documentation Index

Shared building blocks live in `backend/models/*_base.py`, while game-specific models live in `backend/models/qf` (Quipflip) and `backend/models/ir` (Initial Reaction). Use the dedicated game guides alongside this index when exploring schemas or planning migrations.

## Where to Look

- [Quipflip Data Models](QF_DATA_MODELS.md) – complete reference for Quipflip tables and their relationships under `backend/models/qf`.
- [Initial Reaction Data Models](IR_DATA_MODELS.md) – companion reference for IR tables under `backend/models/ir`.

## Core Base Models

Each game-specific package imports these bases and adds its own entities (e.g., `Round`, `Phraseset`, and `Vote` for Quipflip; `BackronymSet`, `BackronymEntry`, and `BackronymVote` for Initial Reaction). Consult the game guides for full field-level definitions.

### PlayerBase
- `player_id` (UUID, primary key)
- `username` (string, unique) - display name for the player
- `username_canonical` (string, unique) - lowercase form for lookups and uniqueness checking
- `email` (string, unique) - player email for authentication
- `password_hash` (string) - bcrypt hashed password
- `wallet` (integer, default 1000) - current spendable currency balance for entering rounds and transactions
- `vault` (integer, default 0) - accumulated long-term currency balance from net earnings, used for leaderboard rankings
- `created_at` (timestamp with timezone) - UTC timestamp of account creation
- `last_login_date` (timestamp with timezone, nullable) - UTC timestamp for last login tracking
- `is_guest` (boolean, default false) - whether this is a guest account with auto-generated credentials
- `is_admin` (boolean, default false) - admin privileges flag for administrative access
- `locked_until` (timestamp with timezone, nullable) - account lock expiration time for temporary bans/suspensions
- `consecutive_incorrect_votes` (integer, default 0) - tracks incorrect votes for guest accounts
- `vote_lockout_until` (timestamp with timezone, nullable) - guest vote lockout expiration when too many incorrect votes
- `tutorial_completed` (boolean, default false) - whether player has finished tutorial
- `tutorial_progress` (string, default 'not_started') - current tutorial step
- `tutorial_started_at` (timestamp with timezone, nullable) - when tutorial was started
- `tutorial_completed_at` (timestamp with timezone, nullable) - when tutorial was completed

**Properties**: `balance` - computed total liquid balance (wallet + vault)
**Authentication**: JWT access/refresh tokens with separate refresh token table
**Guest Accounts**: Auto-generated credentials with vote lockout protection for incorrect votes

### TransactionBase
- `transaction_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `amount` (integer) - transaction amount (negative for charges, positive for payouts)
- `type` (string, indexed) - transaction type identifier (e.g., 'round_entry', 'vote_payout', 'daily_bonus')
- `reference_id` (UUID, nullable, indexed) - references related entity (round_id, phraseset_id, vote_id, quest_id, etc.)
- `created_at` (timestamp with timezone, indexed) - UTC timestamp of transaction
- `wallet_type` (string, default "wallet") - target account ("wallet" or "vault")
- `wallet_balance_after` (integer, nullable) - wallet balance after transaction for audit trail
- `vault_balance_after` (integer, nullable) - vault balance after transaction for audit trail

**Purpose**: Complete audit trail for all currency movements across both games
**Indexing**: Optimized for player transaction history and temporal queries

### RefreshTokenBase
- `token_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `token_hash` (string, indexed) - hashed refresh token for security
- `expires_at` (timestamp with timezone) - token expiration time
- `created_at` (timestamp with timezone) - UTC timestamp of token creation
- `revoked_at` (timestamp with timezone, nullable) - when token was manually revoked

**Methods**: `is_active()` - checks if token is valid (not expired or revoked)
**Security**: Stores hashed tokens only, supports manual revocation for logout/security

### DailyBonusBase
- `bonus_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `amount` (integer, default 100) - bonus amount awarded
- `claimed_at` (timestamp with timezone) - UTC timestamp when bonus was claimed
- `date` (date, indexed) - date for which the bonus was claimed

**Purpose**: Tracks daily login rewards and prevents duplicate claims per day
**Constraints**: Typically enforced at application level for one bonus per player per day

### QuestBase
- `quest_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `quest_type` (string, indexed) - quest type identifier (e.g., 'streak_3', 'quality_votes')
- `status` (string, indexed, default 'active') - quest status ('active', 'completed', 'claimed')
- `progress` (JSON) - flexible progress tracking object with mutable dictionary support
- `reward_amount` (integer) - currency reward for completing the quest
- `created_at` (timestamp with timezone) - UTC timestamp of quest creation
- `completed_at` (timestamp with timezone, nullable) - when quest objectives were met
- `claimed_at` (timestamp with timezone, nullable) - when reward was claimed by player

**Enums**: 
- `QuestStatus`: ACTIVE, COMPLETED, CLAIMED
- `QuestCategory`: STREAK, QUALITY, ACTIVITY, MILESTONE

### QuestTemplateBase
- `template_id` (string, primary key) - unique template identifier
- `name` (string) - human-readable quest name
- `description` (string) - quest description for UI display
- `reward_amount` (integer) - base reward amount for this quest type
- `target_value` (integer) - target value for quest completion
- `category` (string) - quest category for organization

**Purpose**: Defines reusable quest configurations that can be instantiated for players

### SurveyResponseBase
- `response_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `survey_id` (string, indexed) - identifies the survey form
- `payload` (JSON) - flexible survey response data structure
- `created_at` (timestamp with timezone) - UTC timestamp of response submission

**Purpose**: Collects beta feedback and user research data with flexible schema

### NotificationBase
- `notification_id` (UUID, primary key)
- `player_id` (UUID, indexed) - references the player account
- `notification_type` (string) - notification type identifier for client handling
- `data` (JSON, nullable) - notification payload data
- `created_at` (timestamp with timezone) - UTC timestamp of notification creation

**Purpose**: WebSocket push notifications for real-time game events and updates

### UserActivityBase
- `player_id` (UUID, primary key) - references the player account
- `username` (string) - denormalized username for efficient "who's online" queries
- `last_action` (string) - description of most recent user action
- `last_action_category` (string, default "other") - categorized action type for analytics
- `last_action_path` (string) - API endpoint path of last action
- `last_activity` (timestamp with timezone) - UTC timestamp of last API activity

**Purpose**: Powers "Who's Online" feature by tracking recent user activity (typically 30-minute window)
**Performance**: Single record per user, updated on each authenticated API call

### AIMetricBase
- `metric_id` (UUID, primary key)
- `operation_type` (string, indexed) - AI operation type ("copy_generation", "vote_generation", "hint_generation", "backronym_generation")
- `provider` (string, indexed) - AI provider identifier ("openai", "gemini")
- `model` (string) - specific model version (e.g., "gpt-5-nano", "gemini-2.5-flash-lite")
- `success` (boolean, indexed) - whether the AI operation succeeded
- `latency_ms` (integer, nullable) - response time in milliseconds
- `error_message` (string, nullable) - error details if operation failed
- `estimated_cost_usd` (float, nullable) - estimated cost in USD for cost tracking
- `prompt_length` (integer, nullable) - length of prompt in characters
- `response_length` (integer, nullable) - length of AI response in characters
- `created_at` (timestamp with timezone, indexed) - UTC timestamp of AI operation

**Purpose**: Comprehensive AI usage analytics for cost monitoring, performance tracking, and provider comparison
**Analytics**: Supports operational dashboards and AI cost optimization

### SystemConfigBase
- `key` (string, primary key) - configuration key identifier
- `value` (text) - configuration value as string
- `value_type` (string) - data type indicator ('int', 'float', 'string', 'bool')
- `description` (text, nullable) - human-readable description of the setting
- `category` (string, nullable) - configuration category ('economics', 'timing', 'validation', 'ai')
- `updated_at` (timestamp with timezone) - UTC timestamp of last update
- `updated_by` (string, nullable) - player_id of admin who made the change

**Purpose**: Dynamic configuration management for feature flags, economic parameters, and operational settings
**Security**: Typically restricted to admin access with audit trail of changes
