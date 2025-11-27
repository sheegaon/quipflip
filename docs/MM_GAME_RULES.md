# Meme Mint Caption Game — Dev Game Rules

_Working title: Meme Mint_

---

## 1. Overview

This game is an asynchronous meme-caption battler built on the existing Crowdcraft / MemeCoin economy.

Core loop per round:

1. System picks **one image** and **5 captions** for that image.
2. Player **pays an entry fee**, sees the image + 5 captions, and **votes for their favorite**.
3. The **authors of the winning caption** (riff + parent, or original) get paid in MemeCoins.
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

- `lifetime_earnings_gross` — total MemeCoins “earned” by this caption before vault split.
- `lifetime_to_wallet` — total MemeCoins actually credited to wallets for this caption.
- `lifetime_to_vault` — total “burned” MemeCoins attributed to this caption (for leaderboards).

### 2.3 Player

- `player_id`
- `wallet_balance` — spendable MemeCoins.
- `vault_contribution` — cumulative MemeCoins burned in the vault attributable to this player.
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

- Currency: **MemeCoins** (`MC`), same as the rest of the ecosystem.
- Every player has:
  - **Wallet** — spendable MC.
  - **Vault contribution** — *non-spendable* cumulative amount of MC burned on their behalf for leaderboards.

The **vault** itself is a global sink. Coins sent to vault are removed from circulation but still counted in per-player `vault_contribution`.

### 3.2 Starting balance and daily bonus

- **Starting wallet balance**: `STARTING_BALANCE = 500 MC`.
- **Daily bonus**:
  - `DAILY_BONUS_AMOUNT = 100 MC`.
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
    - If `free_captions_remaining_today > 0`, cost = `0 MC`, then decrement.
  - Subsequent submissions that day pay normal caption submission fee.

---

## 4. Round Flow (Voting Round)

Each **round** is an `(image, player)` interaction.

Parameters:

- `CAPTIONS_PER_ROUND = 5`
- `ROUND_ENTRY_COST = 5 MC`

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
  ```

* Selection weight:

  ```text
  weight = max(quality_score, MIN_QUALITY_WEIGHT)^ALPHA
  ```

  with defaults like `MIN_QUALITY_WEIGHT = 0.05`, `ALPHA ∈ [0.5, 1]`.

* Draw 5 captions without replacement according to this weight.

### 4.3 Entry fee

* Before showing anything, the player must have at least `ROUND_ENTRY_COST`.
* On round start:

  * Deduct `ROUND_ENTRY_COST = 5 MC` from `wallet_balance`.
* This 5 MC becomes the **base payout** for the caption authors of the chosen caption (see 4.5).

### 4.4 Player vote

* Player sees:

  * The image.
  * The 5 chosen captions (order randomized).
* Player must pick **exactly one** as their favorite.
* Once they vote:

  * `shows` is incremented for all 5 captions.
  * `picks` is incremented for the chosen caption.
  * `seen_captions[player, image]` is updated with the 5 caption IDs.

### 4.5 Writer payouts from entry fee

Immediately after the vote, we distribute the 5 MC entry fee based on the chosen caption’s type.

Parameter:

* `RIFF_SPLIT_RATIO = 0.6` (riff author share of earnings vs parent)

Let `C` be the chosen caption.

* If `C.kind == "original"`:

  * `base_payout = 5 MC` to `C.author_player_id`.
* If `C.kind == "riff"`:

  * Let `riff_author = C.author_player_id`

  * Let `parent_author = C.parent_caption.author_player_id`

  * Split 5 MC:

    ```text
    riff_base = round(5 * RIFF_SPLIT_RATIO)  # default: 3
    parent_base = 5 - riff_base              # default: 2
    ```

  * `riff_base` → riff author.

  * `parent_base` → parent author.

> **System captions:**
> If `author_player_id` is `null` or a designated `system_player_id`, the same formulas apply, but payouts go to a configurable “system account” or directly to the vault. Default: **100% of author-side payouts from system captions go to vault**.

Base payouts are subject to the **caption earnings / vault split** (Section 6). I.e., they increment `lifetime_earnings_gross` for affected captions and may be partially redirected to vault once that caption passes 100 MC in gross earnings.

### 4.6 System writer bonus (3×)

Parameter:

* `WRITER_BONUS_MULTIPLIER = 3` (configurable)

For each winning vote, the system mints an additional writer bonus:

* `writer_bonus_total = WRITER_BONUS_MULTIPLIER * ROUND_ENTRY_COST`
* With defaults: `3 * 5 = 15 MC` minted.

This `writer_bonus_total` is split **across the same authors** and in the same proportions as the base payout:

* Original caption:

  ```text
  15 MC → original author
  ```

* Riff caption:

  ```text
  riff_bonus   = round(writer_bonus_total * RIFF_SPLIT_RATIO)  # default: 9
  parent_bonus = writer_bonus_total - riff_bonus               # default: 6
  ```

Again, these amounts feed into the caption’s `lifetime_earnings_gross` and are split wallet/vault per Section 6.

### 4.7 Voter bonuses

#### 4.7.1 “Local crowd favorite” bonus (3 coins)

Player may receive a **3 MC bonus** from system for picking the “most popular” caption among the 5 shown.

Definitions:

* For each of the 5 captions in this round, compute `global_vote_count` = total `picks` across all players so far (before this vote).
* A round is **eligible** for this bonus only if:

  * At least **3 of the 5 captions** have `global_vote_count > 0`.
  * There is a **strictly unique maximum** `global_vote_count` among the 5 (no tie for top).

Let `C_top` be the caption with the highest `global_vote_count` at the time of this vote.

* If the player’s chosen caption is `C_top` in an eligible round:

  * System mints `3 MC`:

    * `2 MC` → player’s wallet.
    * `1 MC` → vault.
  * Vault contribution is **attributed to the player** for leaderboards.

Notes:

* This bonus is **per vote**; multiple players can get it for the same caption over time.
* If conditions fail (fewer than 3 with >0 votes, or tie for top), **no one** gets this bonus for that vote.

#### 4.7.2 “First voter” bonus (2 coins)

For each caption, the **first time ever** it receives a vote:

* The voting player gets `2 MC` minted to their wallet.

Implementation details:

* On a caption’s first vote event:

  * Check `caption.first_vote_awarded`:

    * If `false`:

      * Set to `true`.
      * Credit `2 MC` to that voter’s wallet.
    * If `true`:

      * No additional action.

Fairness note:

* Because players never see their own captions (selection filter), they generally cannot farm this by self-voting.
* In case of near-simultaneous votes, the “first” is determined by **earliest server timestamp**.

---

## 5. Caption Submission

After voting, the player is offered the option to submit a caption for the same image.

### 5.1 Costs

Parameters:

* `CAPTION_SUBMISSION_COST = 100 MC`
* `FREE_CAPTIONS_PER_DAY = 1` (Section 3.3)

Flow:

1. Check if the player wants to submit.
2. If they do:

   * If `free_captions_remaining_today > 0`:

     * `cost = 0 MC`.
     * Decrement `free_captions_remaining_today`.
   * Else:

     * Ensure `wallet_balance >= CAPTION_SUBMISSION_COST`.
     * Deduct `CAPTION_SUBMISSION_COST` from wallet.
3. Create the caption (Section 5.2).

Submission fees are **pure sinks** for that player’s wallet. They do **not** go into any pool.

### 5.2 Riff detection via cosine similarity

Let `C_new` be the new caption text.

Let `S` be the set of 5 captions that were shown in this round.

Compute sentence embeddings and cosine similarity between `C_new` and each caption `C_i ∈ S`:

* `sim_i = cosine_similarity(embedding(C_new), embedding(C_i.text))`

Define:

* `SIM_THRESHOLD = 0.5`

Then:

1. Compute `s_max = max(sim_i)` over `i ∈ S`.
2. Let `C_parent` = caption with the highest `sim_i` (ties broken arbitrarily but consistently).
3. Classification:

   * If `s_max > SIM_THRESHOLD`:

     * `C_new.kind = "riff"`
     * `C_new.parent_caption_id = C_parent.caption_id`
   * Else:

     * `C_new.kind = "original"`
     * `C_new.parent_caption_id = null`

New caption initialization:

* `shows = 0`
* `picks = 0`
* `first_vote_awarded = false`
* `quality_score` computed via `(picks + 1)/(shows + 3)` → initial `1/3`.
* `lifetime_earnings_gross = 0`
* `lifetime_to_wallet = 0`
* `lifetime_to_vault = 0`
* `status = active`

There is **no guarantee** the author will ever be shown their own caption or that it will be shown immediately to anyone.

---

## 6. Caption Earnings and Vault Split

For every caption payout (base + writer bonus), we apply **caption-level earnings accounting**.

### 6.1 Per-caption earnings threshold

Rule:

* For each caption, the **first 100 MC of gross earnings** are credited entirely to player wallets.
* After `lifetime_earnings_gross >= 100 MC`, future earnings are split:

  * `50%` to wallets.
  * `50%` to vault.

Parameter:

* `CAPTION_WALLET_THRESHOLD = 100 MC`
* `POST_THRESHOLD_WALLET_SHARE = 0.5`

### 6.2 Applying the split

For a single payout event of `amount` coins to a given author (original or riff/parent share):

Let:

* `earned_so_far = caption.lifetime_earnings_gross`
* `threshold = CAPTION_WALLET_THRESHOLD`

Then:

1. Compute `room_to_threshold = max(0, threshold - earned_so_far)`.

2. Wallet portion:

   ```text
   wallet_part = min(amount, room_to_threshold) \
                 + max(0, amount - room_to_threshold) * POST_THRESHOLD_WALLET_SHARE
   ```

3. Vault portion:

   ```text
   vault_part = amount - wallet_part
   ```

4. Update caption stats:

   ```text
   caption.lifetime_earnings_gross += amount
   caption.lifetime_to_wallet      += wallet_part
   caption.lifetime_to_vault       += vault_part
   ```

5. Update player stats:

   * Author’s `wallet_balance += wallet_part`.
   * Author’s `vault_contribution += vault_part`.
   * Global vault balance increased by `vault_part` (coins burned).

This same logic applies both to:

* Base payouts from `ROUND_ENTRY_COST`.
* Writer bonus payouts from `WRITER_BONUS_MULTIPLIER`.

System captions:

* If `author_player_id` is `null/system`:

  * We can either bypass this and send **100% to vault** directly, or apply the same logic against a `system_player_id`.
  * Default: **all author payouts for system captions → vault**, no wallet/scoring impact.

---

## 7. Caption Lifecycle and Retirement

### 7.1 Quality score

Quality is a simple smoothed rate:

```text
quality_score = (picks + QUALITY_PRIOR_NUM) / (shows + QUALITY_PRIOR_DEN)
```

Defaults:

* `QUALITY_PRIOR_NUM = 1`
* `QUALITY_PRIOR_DEN = 3`

### 7.2 Retirement

Parameters:

* `CAPTION_MIN_SHOWS_BEFORE_RETIREMENT = 5`
* `CAPTION_MIN_QUALITY = 0.05`

Retirement rule:

* When `shows >= CAPTION_MIN_SHOWS_BEFORE_RETIREMENT` and:

  * either `picks == 0` or `quality_score < CAPTION_MIN_QUALITY`,
  * mark `caption.status = retired`.

Retired captions:

* Remain in DB for stats/leaderboards.
* **Never** appear in future caption selection.
* Keep earning no further coins.

---

## 8. Player Constraints and Anti-Abuse (v1)

### 8.1 Visibility rules

* A player **never** sees:

  * Their own captions for an image.
  * The same caption twice for a given image.

Implementation:

* Caption selection always filters by:

  * `author_player_id != current_player_id`
  * `caption_id NOT IN seen_captions[current_player_id, image_id]`

### 8.2 First-voter and crowd-favorite bonuses

* First-voter bonus is structurally hard to farm because:

  * You can’t see your own caption.
  * Captions are served randomly to many players; no guarantee of early exposure.
* Crowd-favorite bonus uses **global popularity** at vote time, not just this round’s votes, so local collusion is less predictable.

For v1, we **omit** explicit rate limiting or complex anti-cheat. Those can be added later without changing game rules.

---

## 9. Tunable Parameters (Summary)

All of the following should live in config, NOT hard-coded:

* **Economy**

  * `STARTING_BALANCE = 500 MC`
  * `DAILY_BONUS_AMOUNT = 100 MC`
  * `ROUND_ENTRY_COST = 5 MC`
  * `WRITER_BONUS_MULTIPLIER = 3`
  * `CAPTION_SUBMISSION_COST = 100 MC`
  * `FREE_CAPTIONS_PER_DAY = 1`
  * `CAPTION_WALLET_THRESHOLD = 100 MC`
  * `POST_THRESHOLD_WALLET_SHARE = 0.5`
  * `RIFF_SPLIT_RATIO = 0.6`

* **Round / selection**

  * `CAPTIONS_PER_ROUND = 5`
  * `MIN_QUALITY_WEIGHT = 0.05`
  * `ALPHA` (quality weighting exponent, e.g. 0.7)

* **Riff detection**

  * `SIM_THRESHOLD = 0.5`

* **Caption lifecycle**

  * `QUALITY_PRIOR_NUM = 1`
  * `QUALITY_PRIOR_DEN = 3`
  * `CAPTION_MIN_SHOWS_BEFORE_RETIREMENT = 5`
  * `CAPTION_MIN_QUALITY = 0.05`

* **Daily logic**

  * UTC vs local-time handling of “day” boundaries.
