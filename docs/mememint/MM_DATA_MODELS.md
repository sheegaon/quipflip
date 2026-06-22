# MemeMint Data Models

> **Document type:** Implementation reference
> **Status:** Review-required — models/migrations are implemented truth
> **Audience:** Backend maintainers

This guide documents the MemeMint–specific tables housed under `backend/models/mm` and explains how they extend the shared base models defined in `DATA_MODELS.md`. MemeMint uses the unified `Player` model with explicit per-game data and adds additional tables for images, captions, rounds, player state, and social features.

## Architecture Note

MemeMint uses the **unified Player model with explicit per-game data** pattern. `Player` remains global and game-agnostic; all MM balances and state live in `MMPlayerData` and are loaded explicitly (e.g., via `PlayerService.snapshot_player_data(game_type="mm")`). Legacy `Player.wallet/vault` shims may mirror MM data only while `auth_emit_legacy_fields` is enabled during the migration.

**MMPlayerData** contains MemeMint-specific player state:
- `player_id` (UUID, PK, FK to players.player_id)
- `wallet` (integer, default 1000)
- `vault` (integer, default 0)
- Game-specific state fields for MM

---

## 1. Relationship to Shared Models

MemeMint uses the unified `Player` authentication model and adds game-specific state:

* Reuses:

  * `Player` for unified cross-game accounts, credentials, and admin status.
  * `MMPlayerData` for MM-specific wallet, vault, and player state.
  * `TransactionBase` as the global ledger.
  * `SystemConfigBase` for tunable parameters.
* Adds:

  * A small set of `mm_*` tables for images, captions, rounds, player state, and social groups.
  * New **transaction `type` values** and **system config keys** (documented in Section 3).
  * Social features with `mm_circle`, `mm_circle_member`, and `mm_circle_join_request` tables for player groups.

All balance changes (entry fees, payouts, bonuses) must still flow through `TransactionBase`.

---

## 2. MemeMint Tables

All tables are logically under the `mm` namespace, e.g. `mm_image`, `mm_caption`, etc.

### 2.1 `mm_image` — Meme Image Catalog

Stores the images used for caption rounds.

* `image_id` (UUID, primary key)

* `source_url` (string, not null)

  * Canonical URL used by the frontend to render the image.

* `thumbnail_url` (string, nullable)

  * Optional smaller version for list/grid views.

* `attribution_text` (string, nullable)

  * For copyright/credit display (e.g., “Photo by X on Y”).

* `tags` (JSONB, nullable)

  * Array of strings such as `["office", "cat", "reaction"]` for future targeting.

* `status` (string, default `'active'`)

  * `'active'` — eligible for round selection.
  * `'disabled'` — never selected; kept for history.

* `created_at` (timestamp with timezone, default now())

* `created_by_player_id` (UUID, nullable, references `players.player_id`)

  * Set if user-upload or admin-upload; null for seed/system images.

* **Indexes:**

  * `image_id` (PK)
  * `status`
  * Optional: GIN index on `tags` for tag-based queries.

* **Relationships:**

  * `captions` (one-to-many) → `mm_caption.image_id`
  * `vote_rounds` (one-to-many) → `mm_vote_round.image_id`

* **Notes:**

  * Image selection logic uses `status = 'active'`.
  * Tags/attribution are for UX and filtering, not core game logic.

---

### 2.2 `mm_caption` — Caption Core + Stats

Represents a single caption tied to one image, with lifecycle stats and economy aggregates.

* `caption_id` (UUID, primary key)

* `image_id` (UUID, references `mm_image.image_id`, indexed, not null)

* `author_player_id` (UUID, references `players.player_id`, nullable, indexed)

  * `NULL` means system/AI-authored caption.

* `kind` (string, not null)

  * `'original'` — first caption authored directly for an image.
  * `'riff'` — caption that riffs on another caption.

* `parent_caption_id` (UUID, nullable, references `mm_caption.caption_id`, indexed)

  * Set only for `kind = 'riff'`; `NULL` for originals.

* `text` (string, not null)

  * Caption text, typically length-limited (e.g. 1–240 chars).

* `status` (string, default `'active'`, indexed)

  * `'active'` — eligible for selection in rounds.
  * `'retired'` — no longer selected but kept for history/stats.
  * `'removed'` — removed for moderation or policy reasons; must not be shown again.

* `created_at` (timestamp with timezone, default now())

**Selection / performance stats:**

* `shows` (integer, default 0, not null)

  * Number of times this caption was displayed in a round (in the 5-caption set).

* `picks` (integer, default 0, not null)

  * Number of times this caption was chosen as the favorite in a round.

* `first_vote_awarded` (boolean, default false, not null)

  * Has the special “first voter bonus” for this caption already been given?

* `quality_score` (float, default 0.0, not null)

  * Denormalized rating used for weighted round selection, e.g.
    `quality_score = (picks + 1) / (shows + 3)`
  * Updated whenever `shows` or `picks` changes.

**Economy aggregates (per caption):**

* `lifetime_earnings_gross` (integer, default 0, not null)

  * Total MemeCoins “earned” by this caption before wallet/vault split.

* `lifetime_to_wallet` (integer, default 0, not null)

  * Total MemeCoins credited to all players’ **wallets** due to this caption.

* `lifetime_to_vault` (integer, default 0, not null)

  * Total MemeCoins contributed to the **vault** that are attributed to this caption.

* **Indexes:**

  * `caption_id` (PK)
  * `(image_id, status)`
  * `author_player_id`
  * `parent_caption_id`
  * `(status, quality_score DESC)` for selection

* **Relationships:**

  * `image` → `mm_image`
  * `author` → `players` (nullable)
  * `parent_caption` → `mm_caption` (nullable)
  * `vote_rounds` (indirect via `mm_vote_round.caption_ids_shown` and `chosen_caption_id`)
  * `seen_records` → `mm_caption_seen`

* **Notes:**

  * Stats (`shows`, `picks`, `quality_score`) are denormalized to keep selection queries fast.
  * Economy aggregates are denormalized counters to support caption-level leaderboards and analytics.
  * Moderation tooling will typically act by toggling `status` and/or editing `text`.

---

### 2.3 `mm_vote_round` — Paid Voting Round

Represents a single “vote on 5 captions for this image” interaction for one player, including entry cost and payouts.

* `round_id` (UUID, primary key)

* `player_id` (UUID, references `players.player_id`, indexed, not null)

* `image_id` (UUID, references `mm_image.image_id`, indexed, not null)

* `caption_ids_shown` (JSONB, not null)

  * Ordered array of 5 `caption_id`s as shown to this player.

* `chosen_caption_id` (UUID, nullable, references `mm_caption.caption_id`, indexed)

  * Selected favorite; `NULL` if round was abandoned before vote.

* `created_at` (timestamp with timezone, default now(), indexed)

Economy snapshot for this round:

* `entry_cost` (integer, not null)

  * MemeCoins charged to `wallet` for entering this round (copied from config at time of creation).
* `payout_to_wallet` (integer, default 0, not null)

  * Total net MemeCoins credited to this player’s wallet as a result of this round (voter bonuses, etc.).
* `payout_to_vault` (integer, default 0, not null)

  * Total MemeCoins sent to this player’s vault attributable to this round (if any).

Flags and lifecycle:

* `first_vote_bonus_applied` (boolean, default false, not null)

  * True if this round’s vote triggered the caption’s first-vote bonus.

* `result_finalized_at` (timestamp with timezone, nullable)

  * When all related payouts were finalized (for delayed processing if ever needed).

* `abandoned` (boolean, default false, not null)

  * True if the player started the round but did not submit a vote.

* **Indexes:**

  * `round_id` (PK)
  * `(player_id, created_at DESC)`
  * `(image_id, created_at DESC)`
  * `chosen_caption_id`

* **Relationships:**

  * `player` → `players`
  * `image` → `mm_image`
  * `chosen_caption` → `mm_caption` (nullable)
  * `transactions` → `transactions.reference_id = round_id` for entry + payouts

* **Notes:**

  * All economic activity tied to a round should use `TransactionBase.reference_id = round_id`.
  * `caption_ids_shown` allows re-deriving `shows` and `mm_caption_seen` if necessary.

---

### 2.4 `mm_caption_seen` — Per-Player Caption History

Tracks which captions a player has already been shown for each image to avoid repeats.

* `player_id` (UUID, references `players.player_id`, not null)

* `caption_id` (UUID, references `mm_caption.caption_id`, not null)

* `image_id` (UUID, references `mm_image.image_id`, not null)

* `first_seen_at` (timestamp with timezone, default now(), not null)

* **Primary Key:**

  * Composite `(player_id, caption_id)`

* **Indexes:**

  * `(player_id, image_id)`
  * `caption_id`

* **Relationships:**

  * `player` → `players`
  * `caption` → `mm_caption`
  * `image` → `mm_image`

* **Notes:**

  * Round creation logic must filter candidate captions for `(player_id, image_id)` where `caption_id` is **not** present in this table.
  * After each round, one row per shown caption is inserted (if missing).
  * `image_id` is technically derivable from `caption_id` but denormalized for faster queries.

---

### 2.5 `mm_player_daily_state` — Free Caption Quotas

Tracks per-player daily quota for **free caption submissions** (separate from the global daily bonus system).

* `player_id` (UUID, references `players.player_id`, not null)

* `date` (date, not null)

  * UTC calendar date.

* `free_captions_used` (integer, default 0, not null)

* `created_at` (timestamp with timezone, default now(), not null)

* `updated_at` (timestamp with timezone, default now(), not null)

  * Updated whenever `free_captions_used` changes.

* **Primary Key:**

  * Composite `(player_id, date)`

* **Indexes:**

  * `(date)` if daily aggregates are needed (optional; PK usually enough).

* **Relationships:**

  * `player` → `players`

* **Notes:**

  * On caption submission, the service layer:

    * Loads or creates `(player_id, today)` row for `today = now_utc.date()`.
    * If `free_captions_used < FREE_CAPTIONS_PER_DAY`, the submission is **free** and increments `free_captions_used`.
    * Otherwise, a `mm_caption_submission_fee` transaction is charged.
  * This table is only about **caption submission quotas**, not daily wallet bonuses (which use shared daily-bonus models).

---

### 2.6 `mm_caption_submission` — Submission Log (Optional)

This table is **optional** but recommended for debugging, moderation, and analytics. It separates “submission attempts” from “accepted captions”.

* `submission_id` (UUID, primary key)

* `player_id` (UUID, references `players.player_id`, indexed, not null)

* `image_id` (UUID, references `mm_image.image_id`, indexed, not null)

* `caption_id` (UUID, references `mm_caption.caption_id`, nullable, indexed)

  * Set when submission is accepted and stored as a caption.

* `submission_text` (string, not null)

  * Raw text provided by the player before moderation/normalization.

* `status` (string, not null)

  * `'accepted'` — caption became an `mm_caption`.
  * `'rejected'` — failed validation or moderation.

* `rejection_reason` (string, nullable)

  * Short code or description (e.g. `policy_violation`, `too_long`).

* `used_free_slot` (boolean, default false, not null)

  * Whether this submission consumed a free daily caption slot.

* `created_at` (timestamp with timezone, default now(), not null)

* **Indexes:**

  * `player_id`
  * `image_id`
  * `caption_id`
  * Composite `(status, created_at)`

* **Relationships:**

  * `player` → `players`
  * `image` → `mm_image`
  * `caption` → `mm_caption` (nullable)

* **Notes:**

  * For MVP, you can skip this table and rely solely on `mm_caption`.
  * If you later add async moderation or automated filters, this table becomes more useful.

---

### 2.7 `mm_circle` — Player Groups / Circles

Represents a social group or "circle" in MemeMint where players can organize, collaborate, and share content.

* `circle_id` (UUID, primary key)

* `name` (string(100), not null, unique)

  * Display name for the circle.

* `description` (text, nullable)

  * Optional longer description of the circle's purpose.

* `created_by_player_id` (UUID, references `players.player_id`, indexed, not null)

  * The player who created the circle (the circle creator/owner).

* `created_at` (timestamp with timezone, default now(), not null)

* `updated_at` (timestamp with timezone, default now(), not null)

  * Last modification timestamp.

* `member_count` (integer, default 1, not null)

  * Cached count of active members in the circle (including creator).

* `is_public` (boolean, default true, not null)

  * Whether circle is discoverable or invite-only.

* `status` (string, default 'active', not null)

  * `'active'` — circle is operating normally.
  * `'archived'` — circle has been deactivated.
  * `'deleted'` — circle was deleted (soft-delete).

* **Indexes:**

  * `circle_id` (PK)
  * `created_by_player_id`
  * `(status, created_at DESC)` for listing active circles
  * `name` (unique)

* **Relationships:**

  * `creator` → `players` (created_by_player_id)
  * `members` ← `mm_circle_member` (circle_id)
  * `join_requests` ← `mm_circle_join_request` (circle_id)

---

### 2.8 `mm_circle_member` — Circle Membership

Tracks membership of a player in a circle.

* `member_id` (UUID, primary key)

* `circle_id` (UUID, references `mm_circle.circle_id`, indexed, not null)

  * The circle this membership belongs to.

* `player_id` (UUID, references `players.player_id`, indexed, not null)

  * The player who is a member.

* `joined_at` (timestamp with timezone, default now(), not null)

  * When this player joined the circle.

* `role` (string, default 'member', not null)

  * `'creator'` — the circle creator (one per circle).
  * `'admin'` — designated administrator (optional).
  * `'member'` — regular member.

* **Indexes:**

  * `member_id` (PK)
  * `(circle_id, player_id)` unique constraint
  * `player_id`
  * `joined_at`

* **Constraints:**

  * Unique constraint on `(circle_id, player_id)` to prevent duplicate memberships.

* **Relationships:**

  * `circle` → `mm_circle`
  * `player` → `players`

---

### 2.9 `mm_circle_join_request` — Pending Circle Join Requests

Tracks pending requests from players who want to join a circle.

* `request_id` (UUID, primary key)

* `circle_id` (UUID, references `mm_circle.circle_id`, indexed, not null)

  * The circle being requested to join.

* `player_id` (UUID, references `players.player_id`, indexed, not null)

  * The player requesting to join.

* `status` (string, default 'pending', not null)

  * `'pending'` — awaiting circle creator/admin approval.
  * `'approved'` — approved and member added to `mm_circle_member`.
  * `'denied'` — rejected by circle creator/admin.

* `requested_at` (timestamp with timezone, default now(), not null)

  * When the join request was created.

* `reviewed_at` (timestamp with timezone, nullable)

  * When the circle creator/admin reviewed the request (approved or denied).

* `reviewed_by_player_id` (UUID, references `players.player_id`, nullable)

  * The admin/creator who approved or denied the request.

* **Indexes:**

  * `request_id` (PK)
  * `(circle_id, status)` for listing pending requests
  * `player_id`
  * `requested_at`

* **Constraints:**

  * Unique constraint on `(circle_id, player_id)` to prevent duplicate join requests.

* **Relationships:**

  * `circle` → `mm_circle`
  * `player` → `players`
  * `reviewed_by` → `players` (nullable)

* **Notes:**

  * Upon approval, circle creator should create a corresponding `mm_circle_member` record and delete/archive the request.
  * Upon denial, request is marked as denied and may be deleted or archived for audit purposes.

---

## 3. Economy Integration

These are **not new tables**, but rules for how MemeMint uses the shared economic models.

### 3.1 `TransactionBase` Types

MemeMint introduces new values for `TransactionBase.type`. Suggested conventions:

**Round-related:**

* `mm_round_entry`

  * Negative amount from `wallet`.
  * `reference_id = mm_vote_round.round_id`.
* `mm_voter_bonus`

  * Positive amount to `wallet` for voting-related rewards.
  * `reference_id = mm_vote_round.round_id`.
* `mm_first_vote_bonus`

  * Positive amount to `wallet` (or vault) for being first to pick a caption.
  * `reference_id = mm_vote_round.round_id`.

**Caption payouts (authors):**

* `mm_caption_payout_wallet`

  * Positive amount to `wallet`, attribution to caption author.
  * `reference_id = mm_caption.caption_id`.
* `mm_caption_payout_vault`

  * Positive amount to `vault` attributed to the same caption, representing the vault sink.

If you share payouts between original and riff caption:

* `mm_caption_riff_share_wallet`
* `mm_caption_riff_share_vault`

(Alternatively, reuse `mm_caption_payout_*` and decide split in service layer; types are mostly for reporting.)

**Submission-related:**

* `mm_caption_submission_fee`

  * Negative wallet transaction for paid caption submissions (when no free slot).

**System / promo:**

* `mm_mm_promo_credit` (optional)

  * Positive wallet transactions for meme-mint-specific promotions.

* **Conventions:**

  * `wallet_type = 'wallet'` for spendable MemeCoins.
  * `wallet_type = 'vault'` for vault contributions.
  * `reference_id` should point to the logically closest entity (round or caption) for auditability.

---

### 3.2 `SystemConfigBase` Keys

MemeMint relies on `SystemConfigBase` for tunable parameters. Suggested keys and semantics:

Economy:

* `mm_round_entry_cost` (int, default `5`)

  * Wallet cost to start a voting round.
* `mm_captions_per_round` (int, default `5`)

  * Number of captions displayed per round (kept in sync with client).
* `mm_free_captions_per_day` (int, default `1`)

  * Free caption submissions per player per UTC day.
* `mm_caption_submission_cost` (int, default maybe `10`)

  * Wallet cost for caption submissions beyond free quota.
* `mm_house_rake_vault_pct` (float, default e.g. `0.5`)

  * Fraction of caption earnings routed to vault vs wallets.

Validation:

* `mm_riff_similarity_threshold` (float, default `0.7`)

  * Maximum cosine similarity allowed between riff caption and parent caption. Riffs with similarity >= threshold are rejected as too similar.

Quality / lifecycle:

* `mm_min_quality_score_active` (float, optional)

  * Auto-retire captions that underperform below this quality.
* `mm_retire_after_shows` (int, optional)

  * Auto-retire captions after N shows irrespective of quality.
* `mm_max_captions_per_image` (int, optional)

  * Soft limit to avoid over-saturating any given image.

Misc:

* `mm_starting_wallet_override` (int, optional)

  * If set, service layer can override default `PlayerBase.wallet` for MemeMint–only registrations (e.g. 500 MC).
* `mm_daily_bonus_amount` (int, optional)

  * If the meme-mint daily bonus differs from global default; otherwise reuse existing key.

All config rows should set:

* `category = 'economics'` or `'validation'` as appropriate.
* `value_type = 'int'` or `'float'` etc.

---

### 3.3 Use of `PlayerBase` and Daily Bonus

* `PlayerBase.wallet` and `PlayerBase.vault` are used exactly as in other games:

  * Wallet = spendable MemeCoins within MemeMint.
  * Vault = global sink used for ecosystem-wide leaderboards.
* Starting balances and daily bonuses for MemeMint are configured via `SystemConfigBase` and implemented in the service layer; the schema does not change.
* Per-player free caption quota is tracked in `mm_player_daily_state` (this doc), not in the base player record.

---

## 4. Summary

New schema objects for MemeMint:

* `mm_image` — catalog of meme images.
* `mm_caption` — captions with stats and economy aggregates.
* `mm_vote_round` — per-player voting rounds (entry + payouts).
* `mm_caption_seen` — per-player caption history to prevent repeats.
* `mm_player_daily_state` — per-player daily free-caption quotas.
* `mm_caption_submission` — optional log for submission attempts.

Everything else (players, transactions, system config, daily bonus) is reused from the shared base models and governed by the transaction types and config keys defined above.
