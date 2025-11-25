# Meme Mint Caption Game — Dev Game Rules

_Working title: Meme Mint_

---

## 1. Overview

This game is an asynchronous meme-caption battler built on the existing Crowdcraft / Flipcoin economy.

Core loop per round:

1. System picks **one image** and **5 captions** for that image.
2. Player **pays an entry fee**, sees the image + 5 captions, and **votes for their favorite**.
3. The **authors of the winning caption** (riff + parent, or original) get paid in coins.
4. The system may pay additional **voter bonuses**.
5. After voting, player can optionally **submit a new caption** for that image (original or riff).
6. Images and captions are replayable indefinitely; bad captions are retired over time.

All numbers below are **configurable** but documented with concrete defaults.

---

## 2. Core Entities

### 2.1 Image

- `image_id`
- Metadata (URL, attribution, tags, etc.)
- Status: `active | disabled`

### 2.2 Caption

- `caption_id`
- `image_id`
- `author_player_id` (nullable for system/AI captions)
- `kind`: `original | riff`
- `parent_caption_id` (nullable; set for riff)
- `created_at`
- `status`: `active | retired | removed`

Stats (for selection + lifecycle):

- `shows` — times this caption was shown in a 5-caption set.
- `picks` — times this caption was selected as favorite.
- `first_vote_awarded` — boolean flag for the “first voter” bonus.
- `quality_score` — derived metric, e.g. `(picks + 1) / (shows + 3)`.

Economy stats (per caption):

- `lifetime_earnings_gross` — total coins “earned” by this caption before vault split.
- `lifetime_to_wallet` — total coins actually credited to wallets for this caption.
- `lifetime_to_vault` — total “burned” coins attributed to this caption (for leaderboards).

### 2.3 Player

- `player_id`
- `wallet_balance` — spendable Flipcoins.
- `vault_contribution` — cumulative coins burned in the vault attributable to this player.
- `created_at`
- Daily state:
  - `has_claimed_daily_bonus_today` (UTC)
  - `free_captions_remaining_today` (int; usually 0 or 1)

Per-image per-player state:

- `seen_captions[image_id]` — set of `caption_id`s already shown for that image.
- No explicit limit; used to avoid showing the same caption twice.

---

## 3. Economy

### 3.1 Currency and balances

- Currency: **Flipcoins** (`FC`), same as the rest of the ecosystem.
- Every player has:
  - **Wallet** — spendable FC.
  - **Vault contribution** — *non-spendable* cumulative amount of FC burned on their behalf for leaderboards.

The **vault** itself is a global sink. Coins sent to vault are removed from circulation but still counted in per-player `vault_contribution`.

### 3.2 Starting balance and daily bonus

- **Starting wallet balance**: `STARTING_BALANCE = 500 FC`.
- **Daily bonus**:
  - `DAILY_BONUS_AMOUNT = 100 FC`.
  - Can be claimed **once per UTC day** by non-guest accounts.
  - **Not available on day 1**:  
    - If `now_utc.date() == floor(player.created_at_utc).date()`, they are **ineligible** to claim the daily bonus.
  - From day 2 onwards:
    - Claiming daily bonus immediately credits `DAILY_BONUS_AMOUNT` to `wallet_balance`.

### 3.3 Free caption submissions per day

- Each player gets `FREE_CAPTIONS_PER_DAY = 1`.
- Only applies to **caption submissions** (Section 5).
- Typical flow:
  - On first caption submission of the UTC day:
    - If `free_captions_remaining_today > 0`, cost = `0 FC`, then decrement.
  - Subsequent submissions that day pay normal caption submission fee.

---

## 4. Round Flow (Voting Round)

Each **round** is an `(image, player)` interaction.

Parameters:

- `CAPTIONS_PER_ROUND = 5`
- `ROUND_ENTRY_COST = 5 FC`

### 4.1 Image selection

At round start, the system selects an `image_id` such that:

- `image.status == active`
- There exist **at least `CAPTIONS_PER_ROUND` captions** for that image that:
  - Are `status == active`
  - Are **not authored** by the player
  - Are **not** in `seen_captions[player, image]`

If no such image exists, the game may:

- Return “no rounds available” or
- Fallback to a different mode (out of scope here).

### 4.2 Caption selection for a round

For the chosen `image_id`, candidate captions are:

- All captions where:
  - `status == active`
  - `author_player_id != player_id` (never show a player their own caption)
  - `caption_id NOT IN seen_captions[player, image]`

From these candidates, the system selects `CAPTIONS_PER_ROUND` captions, using a **weighted random**:

- Each caption has a `quality_score`:

  ```text
  quality_score = (picks + 1) / (shows + 3)
