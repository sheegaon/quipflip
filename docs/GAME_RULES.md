# Game Rules

## Overview
Quipflip revolves around three sequential round types—prompt creation, copywriting, and voting—that funnel player fees into a shared prize pool before redistributing winnings based on how voters respond. All economic values, timers, and behavioral limits are configurable via `backend.config.Settings`, so this document references the setting names (for example `prompt_cost`) instead of hard-coded numbers.

## Economy and Rewards
### Core balances and income
- New accounts begin with `starting_balance`, which is set when `PlayerService.create_player` persists a player record.
- Players can claim a once-per-day stipend worth `daily_bonus_amount`, provided they are not guests and have not already collected it on the same UTC day.

### Round entry costs and refunds
- Starting a prompt round immediately deducts `prompt_cost` through `TransactionService` and allocates `prompt_round_seconds` before expiration, followed by a `grace_period_seconds` extension for submissions.
- Copy rounds charge either `copy_cost_normal` or the discounted `copy_cost_discount` determined by the queue state, assign `copy_round_seconds` to respond, and apply the same grace period on submission.
- Vote rounds deduct `vote_cost`, last `vote_round_seconds`, and also permit `grace_period_seconds` past the timer for a final submission window.
- Abandoning or timing out of a prompt or copy round refunds the original fee minus `abandoned_penalty`; copy round abandonments also return the prompt to the queue and log a cooldown marker.

### Prize pools and payouts
- When two copies are submitted, `RoundService.create_phraseset_if_ready` seeds a phraseset’s `total_pool` with `prize_pool_base`. Any `system_contribution` recorded when discounts apply is stored alongside the phraseset for reporting but is not folded into the distributable pool.
- Every vote adds `vote_cost` to the pool; correct voters immediately receive `vote_payout_correct`, and that payout is subtracted from the pool’s running total.
- Final payouts divide the remaining `total_pool` in proportion to `correct_vote_points` for the original phrase versus `incorrect_vote_points` for each copy. If no votes were cast, contributors split the pot evenly.

## Round Lifecycle
### Prompt rounds
- Players can start a prompt round only if they have at least `prompt_cost`, are not already in another round, and have fewer than the configured cap of outstanding prompts (`max_outstanding_quips` for registered players, `guest_max_outstanding_quips` for guests).
- Submissions are validated against the configured phrase rules before the prompt is queued for copy rounds.

### Copy rounds
- Copy rounds pull prompts FIFO from the queue, skipping flagged entries, the player’s own prompts, prompts already copied by that player, and prompts the player abandoned within the configured cooldown window (tracked via `PlayerAbandonedPrompt`).
- The queue service activates the discount price when more than `copy_discount_threshold` prompts are waiting; the difference between `copy_cost_normal` and the discounted price is tracked as a `system_contribution`.
- Copy submissions must satisfy the phrase validator, avoid matching the original or the other copy, and trigger phraseset creation once two valid copies exist.

### Vote rounds
- Vote availability excludes phrasesets a player helped create and any set they have already voted on. Remaining sets are prioritized: phrasesets at or beyond `vote_closing_threshold` (using `fifth_vote_at`) first, then those between `vote_minimum_threshold` and `vote_closing_threshold`, and finally sets under `vote_minimum_threshold` picked at random.
- Starting a vote round charges `vote_cost`, opens a timer governed by `vote_round_seconds`, and randomizes phrase order per player.
- Voters cannot select phrasesets they contributed to, must choose from the three provided phrases, and receive `vote_payout_correct` only when selecting the original phrase.

### Submission deadlines and penalties
- Prompt, copy, and vote submissions all respect `grace_period_seconds` beyond their nominal timers; attempts after that window raise a `RoundExpiredError`.
- Automatic timeout handling mirrors manual abandonment: prompt rounds refund `prompt_cost - abandoned_penalty`, copy rounds refund their entry fee minus `abandoned_penalty`, return prompts to the queue, and log abandonments for cooldown tracking.

## Voting Finalization and Scoring
- `_update_vote_timeline` marks when a phraseset hits `vote_minimum_threshold`, transitions to `closing` at `vote_closing_threshold`, and schedules `closes_at` using `vote_closing_window_minutes`.
- `check_and_finalize` automatically finalizes phrasesets when any of the following are true: the vote count reaches `vote_max_votes`, the closing window duration (`vote_closing_window_minutes`) expires after hitting `vote_closing_threshold`, or the minimum window (`vote_minimum_window_minutes`) expires after reaching `vote_minimum_threshold`.
- Finalization records activity, updates prompt round status, and issues `prize_payout` transactions based on the proportional scoring logic described earlier. Contributors’ `ResultView` rows are created or updated later when they open the results screen.

### Scoring workflow
1. When a phraseset is built, its `total_pool` starts at `prize_pool_base`; any `system_contribution` from discounted copy entries is tracked separately and not added to this balance.
2. Each vote charges `vote_cost` and increases `vote_contributions`. Correct voters are immediately credited `vote_payout_correct`, which is subtracted from `total_pool` so only the remaining balance is shared among contributors.
3. The scoring service counts how many voters chose the original versus each copy. The original earns `correct_vote_points` per correct vote, while each copy earns `incorrect_vote_points` for every voter they fooled. These points determine the share of the remaining pool that each participant receives.
4. If everyone had zero points (no votes or only invalid submissions), the pool is split evenly across prompt, copy1, and copy2 contributors.

### Worked example
Imagine a phraseset where the pool currently holds `prize_pool_base + (5 * vote_cost) - (3 * vote_payout_correct)` because five players voted and three of them already collected the correct-vote stipend (any `system_contribution` from copy discounts is tracked separately). If three voters picked the original phrase, one chose copy 1, and one chose copy 2:

- The original earns `3 * correct_vote_points`.
- Copy 1 earns `1 * incorrect_vote_points`.
- Copy 2 earns `1 * incorrect_vote_points`.

The scoring service multiplies each point total by the remaining pool, divides by the combined points, and rounds down. Any leftover Flipcoins caused by flooring remain stored in the phraseset’s `total_pool` and are not redistributed.

## Player Limits and Penalties
- Players may only hold one active round at a time, must have enough balance to cover the relevant cost, and cannot participate while `locked_until` is in the future (used for moderation actions).
- Abandoning a copy round or letting it time out logs a `PlayerAbandonedPrompt` record; future copy assignments skip prompts abandoned within `abandoned_prompt_cooldown_hours`.

### Guest Account Restrictions
Guest accounts ("play without registration") face several restrictions designed to prevent abuse while allowing casual exploration:

**Economic limitations:**
- Cannot claim the daily bonus (`daily_bonus_amount`), which is reserved for registered players
- Begin with the same `starting_balance` as registered players but have no income source beyond round payouts

**Activity restrictions:**
- Limited to `guest_max_outstanding_quips` active prompts (typically 3) versus `max_outstanding_quips` (typically 10) for registered players
- Subject to stricter rate limits: 50 requests per minute (general) and 10 votes per minute, compared to 100 and 20 for registered players

**Vote lockout protection:**
- A vote lockout automatically triggers after `guest_vote_lockout_threshold` consecutive incorrect votes, lasting `guest_vote_lockout_hours`
- During lockout, guests cannot start new vote rounds; the error code `vote_lockout_active` is returned
- The lockout resets automatically when the timer expires, clearing `vote_lockout_until` and resetting `consecutive_incorrect_votes` to zero
- Correct votes immediately reset the consecutive incorrect count, preventing lockout

**Account lifecycle:**
- Inactive guest accounts (no login for 30+ days) have their usernames recycled by appending " X" to allow reuse by new players
- Guest accounts with no rounds played after a configurable number of days (default varies) are permanently deleted along with associated data
- Guests can upgrade to full accounts by providing an email and password through the account upgrade flow, which validates password strength and checks for email conflicts before converting the `is_guest` flag and updating credentials

## Phrase Validation Rules
- The backend either calls the remote Phrase Validation API (`use_phrase_validator_api`) or falls back to the bundled validator. Both enforce word-count bounds (`phrase_min_words`, `phrase_max_words`), per-word length (`phrase_min_char_per_word`, `phrase_max_char_per_word`), overall length (`phrase_max_length`), and dictionary membership, while permitting a short list of connecting words.
- Significant words—defined by `significant_word_min_length`—cannot be reused from the original, other copies, or the prompt, and similar words above `word_similarity_threshold` are rejected. Phrases too similar overall are blocked when their similarity score exceeds `similarity_threshold`.
- Prompt submissions are additionally checked against the prompt text, and copy submissions must differ from both the original and any existing copy; both checks share the same validator logic.

## AI Assistance and Automation
The [AI Service guide](AI_SERVICE.md) details how automated players stay aligned with live game rules. The system provides two complementary AI systems:

### Backup AI (Recent Content)
- Provider selection honors `ai_provider`, `openai_api_key`, and `gemini_api_key`, choosing `ai_openai_model` or `ai_gemini_model` and enforcing `ai_timeout_seconds` for each request.
- `AIService.generate_copy_phrase` mirrors human copy creation by building prompts, generating text through the selected model, and submitting phrases only after the same validator approves them. Retries occur when similarity checks fail, and every attempt records metrics so moderators can audit outcomes.
- `AIService.generate_vote_choice` evaluates a shuffled phraseset, selects a phrase using model-specific prompts, and submits the vote through `VoteService` so entry fees, lockouts, and payouts behave exactly like a human vote.
- `AIService.run_backup_cycle` waits `ai_backup_delay_minutes` before acting on stalled rounds, processes up to `ai_backup_batch_size` prompts or phrasesets per pass, and typically sleeps for `ai_backup_sleep_minutes` between runs. During a cycle it creates or reuses the AI player (`ai_copy_backup@quipflip.internal`), fills missing copies, submits system votes once a phraseset already has at least one human vote, and leaves detailed telemetry in `ai_metrics` for review.

### Stale AI (Abandoned Content)
The stale AI handler provides a safety net for content that has been waiting for an extended period:
- **Activation Threshold**: Content must be at least `ai_stale_threshold_days` old (default: 3 days, minimum 3)
- **Scope**: Handles both prompts waiting for copies AND phrasesets waiting for votes
- **Independence**: Unlike the backup AI, the stale handler can act even when only AI players have participated, ensuring no content is permanently abandoned
- **Players**: Uses two dedicated AI accounts - `ai_stale_handler@quipflip.internal` for copies and `ai_stale_voter@quipflip.internal` for votes
- **Processing**: Processes ALL stale content in each cycle (no batch size limit)
- **Frequency**: Runs every `ai_stale_check_interval_hours` (default: 12 hours)
- **Metrics**: All operations are tracked separately with `operation_type` set to `"stale_copy"` or `"stale_vote"`
- **Error Recovery**: Failed copy attempts re-enqueue the prompt for retry; both successes and failures are logged with comprehensive metrics

The stale handler complements the backup AI by ensuring content doesn't remain abandoned while allowing ample time for human participation.

## Queue Dynamics and Discounts
- Prompt rounds are enqueued for copy players once a prompt phrase is submitted and remain until two valid copies arrive or the prompt is flagged or abandoned. Copy abandonments requeue the prompt automatically, and cooldown tracking prevents the same player from receiving it again immediately.
- Phrasesets ready for voting are added to a separate queue that determines whether vote rounds are available. Vote availability checks also trigger automatic finalization so players do not enter stale rounds, and they respect vote-priority ordering (`vote_closing_threshold`, then `vote_minimum_threshold`, then random selection).

## Configuration Reference by Purpose
- **Economy:** `starting_balance`, `daily_bonus_amount`, `prompt_cost`, `copy_cost_normal`, `copy_cost_discount`, `vote_cost`, `vote_payout_correct`, `prize_pool_base`, `abandoned_penalty`.
- **Player limits:** `max_outstanding_quips`, `guest_max_outstanding_quips`, `guest_vote_lockout_threshold`, `guest_vote_lockout_hours`, `abandoned_prompt_cooldown_hours`.
- **Timing:** `prompt_round_seconds`, `copy_round_seconds`, `vote_round_seconds`, `grace_period_seconds`, `ai_timeout_seconds`, `ai_backup_delay_minutes`, `ai_backup_batch_size`, `ai_backup_sleep_minutes`.
- **Voting thresholds:** `vote_max_votes`, `vote_minimum_threshold`, `vote_minimum_window_minutes`, `vote_closing_threshold`, `vote_closing_window_minutes`, `correct_vote_points`, `incorrect_vote_points`.
- **Phrase validation:** `use_phrase_validator_api`, `phrase_validator_url`, `phrase_min_words`, `phrase_max_words`, `phrase_max_length`, `phrase_min_char_per_word`, `phrase_max_char_per_word`, `significant_word_min_length`, `similarity_threshold`, `word_similarity_threshold`.
- **AI providers:** `ai_provider`, `ai_openai_model`, `ai_gemini_model`, `openai_api_key`, `gemini_api_key`, `ai_stale_handler_enabled`, `ai_stale_threshold_days`, `ai_stale_check_interval_hours` (environment-driven).
