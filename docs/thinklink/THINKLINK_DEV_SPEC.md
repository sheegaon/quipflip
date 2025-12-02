# **ThinkLink — Game Rules (Developer Spec)**

*Last updated: 2025-12-02*

---

# **1. Overview**

ThinkLink is a semantic-matching game where players answer a prompt (e.g., *“Name something people forget at home”*).
The objective is to guess answers that **semantically match** the crowd’s prior answers.

Key mechanics:

* Players can make **unlimited guesses**
* Valid guesses with **no matches** cause **strikes**
* **3 strikes** ends the round
* Scoring is based on **weighted coverage** of the crowd’s answer space
* The embedding model is **OpenAI `text-embedding-3-small` (1536-dim)**
* Cosine similarity drives all semantic comparisons
* Each prompt has a maximum of **K = 1000 active answers**

---

# **2. Prompts and Corpus**

## 2.1 Prompt lifecycle

* ~300 prompts are curated and seeded with AI-generated answers.
* New player answers extend each prompt’s answer corpus.
* Only **active answers** (max 1000 per prompt) participate in gameplay and scoring.

## 2.2 Active corpus cap (K = 1000)

For each prompt:

* Maintain **up to 1000 active answers**.
* Answers above this limit are marked **inactive** and excluded from gameplay:

  * Removed based on *low usefulness*, *low weight*, and/or *age*.
* Inactive answers remain stored for history but do not influence play.

---

# **3. Phrase Validation (Reuses Quipflip Validator)**

All player submissions must pass **the same phrase validation system used by Quipflip**.

This includes:

1. **Word & dictionary rules**

   * 2–5 words
   * Letters + spaces only (A–Z)
   * All words must exist in the NASPA dictionary
   * No punctuation/emojis/numbers
   * 4–100 characters total

2. **No repeating significant words**

   * Prevents trivial variants like “PHONE → MY PHONE → CELL PHONE”

3. **Moderation**

   * Screen with OpenAI moderation API, re-use username moderation code.

4. **On-topic check**

   * Compute embeddings for prompt & answer
   * Require cosine similarity ≥ `TOPIC_THRESHOLD` (e.g., 0.35–0.45)

5. **Self-similarity guard**

   * A valid submission must differ semantically from player’s own prior guesses
   * If similarity ≥ **0.80** to any prior guess in this round → reject
   * Rejections **do not** incur strikes

Invalid answers never count as guesses and never produce strikes.

---

# **4. Round Structure**

A round is defined as **(player, prompt, snapshot)**.

## 4.1 Snapshot at round start

At round start, the system freezes:

* Up to **K = 1000 active answers**
* Their embeddings
* Their cluster assignments
* Their cluster weights

This snapshot remains constant for the entire round.
New answers from other players are ignored for this round.

## 4.2 Guess loop

Each guess:

1. Validate phrase (using Quipflip validator)
2. If valid → embed using OpenAI small
3. Compute cosine similarity vs **all snapshot answers** (≤1000)
4. Determine which clusters (if any) were newly matched
5. Update `matched_clusters`
6. If **zero** snapshot answers exceed match threshold (sim > 0.55) → **strike**

The round ends when:

* Player quits voluntarily
* Player accumulates **3 strikes**

---

# **5. Clustering (Detailed)**

Clustering organizes answers into semantic “idea buckets” so that:

* Synonyms do not inflate scoring
* Scoring rewards coverage of *ideas*, not individual phrasings

Clustering is **separate from matching**:

* **Matching uses all answers**
* **Clustering uses only cluster centroids**

## 5.1 When clustering happens

Clustering only occurs **when a new answer is added to the corpus** (outside rounds).

## 5.2 Cluster assignment algorithm (online)

Let `e_new` = embedding for newly accepted answer (after validation).

1. Retrieve **all cluster centroids** for this prompt (usually few: ~50–200).

2. Compute cosine similarity between `e_new` and each centroid.

3. Let:

   * `sim_max` = highest similarity
   * `best_cluster` = cluster with highest similarity

4. Use thresholds:

   * `CLUSTER_JOIN_THRESHOLD = 0.75`
     → join this cluster
   * `CLUSTER_DUPLICATE_THRESHOLD = 0.90`
     → (optional) treat as near-duplicate variant
   * else → create new cluster using `e_new` as centroid

5. Update centroid using running mean:

```python
new_centroid = (old_centroid * n + e_new) / (n + 1)
```

## 5.3 Cluster usefulness & pruning

Each answer tracks:

* `shows` = # times used in snapshots
* `contributed_matches` = # times it helped players match its cluster

Usefulness:

```text
usefulness = contributed_matches / (shows + smoothing)
```

When reducing active answers to K=1000:

* Drop answers with low usefulness and/or low weight first
* Preserve cluster diversity by not dropping all members of a cluster

---

# **6. Weighted Coverage (“Crowd Mass”)**

ThinkLink rewards matching not just many clusters, but **popular clusters**.

## 6.1 Per-answer weights

Each answer `j` tracks:

```text
answer_players_j = number of distinct players who submitted this exact answer
```

Define:

```text
RAW_CAP = 20
raw_eff_j = min(answer_players_j, RAW_CAP)
w_answer_j = 1 + log(1 + raw_eff_j)
```

## 6.2 Per-cluster weight

```text
cluster_weight_c = Σ w_answer_j  for all answers j in cluster c
```

Total mass in snapshot:

```text
W_total = Σ cluster_weight_c
```

---

# **7. Matching & Coverage During a Round**

While the round progresses:

* Maintain `matched_clusters` (a set)
* Whenever a guess matches one or more snapshot answers (sim > 0.55):

  * Mark their **clusters** as matched
  * Multiple answer matches within the same cluster count only once

End-of-round coverage:

```text
p = ( Σ(cluster_weight_c for c in matched_clusters) ) / W_total
```

---

# **8. Payout & Vault Split**

Entry cost: **100 coins**

Maximum gross payout: **300 coins** (net +200 possible)

## 8.1 Gross payout curve

Convex curve rewarding deep coverage:

```python
gross = round(300 * (p ** 1.5))
gross = clamp(gross, 0, 300)
```

## 8.2 Vault split

Coins above 100 are “winnings.”

```python
if gross <= 100:
    wallet_award = gross
    vault_award = 0
else:
    extra = gross - 100
    vault_award = int(extra * 0.30)
    wallet_award = gross - vault_award
```

Wallet net change:

```
net_wallet = wallet_award - 100
vault += vault_award
```

---

# **9. Strikes & End Conditions**

A **strike** occurs when:

* Submission is **valid**, but
* Matches **zero** snapshot answers above threshold (sim ≤ 0.55)

Three strikes ends the round.
Players may quit at any time.

No max-guess limit, except strike-based termination.

---

# **10. AI Seeding for Prompts**

Each prompt will be pre-seeded with 40–60 AI-generated answers:

* Validate using Quipflip validator
* On-topic check
* Moderation
* Clustering
* Ensure each initial cluster has multiple variants if possible

This ensures a robust initial semantic landscape. Infrastructure for AI seeding must allow import/updates via CSV, similar to Quipflip `prompts.csv` and `prompt_completions.csv`. Create import script in `main.py`.

---

# **11. Data Model (Summary)**

## `tl_answer`

* `answer_id`
* `prompt_id`
* `text`
* `embedding` (1536 vector)
* `cluster_id`
* `answer_players_count`
* `shows`
* `contributed_matches`
* `is_active`
* `created_at`

## `tl_cluster`

* `cluster_id`
* `prompt_id`
* `centroid_embedding`
* `size`
* `example_answer_id` (representative)
* (`cluster_weight` is derived)

## `tl_round`

* `round_id`
* `player_id`
* `prompt_id`
* `snapshot_answer_ids`  — frozen at round start
* `snapshot_cluster_ids` — frozen at round start
* `matched_clusters`     — set of cluster_ids matched so far
* `strikes`
* `created_at`
* `ended_at`             — timestamp when round actually ended (strikes, quit, or timer)
* `challenge_id` (nullable, FK → `tl_challenge.challenge_id`)
* `final_coverage` (nullable float, 0–1) — p at end of round
* `gross_payout` (nullable int, 0–300)  — gross coins for this round

## `tl_challenge`

Represents a single head-to-head challenge wrapping two standard ThinkLink rounds.

* `challenge_id`
* `prompt_id`
* `initiator_player_id`
* `opponent_player_id`
* `initiator_round_id` (nullable FK → `tl_round.round_id`)
* `opponent_round_id`  (nullable FK → `tl_round.round_id`)
* `status` — enum: `"pending" | "active" | "completed" | "cancelled" | "expired"`
* `time_limit_seconds` (int, default **300** = 5 minutes)
* `started_at` (nullable)   — when both rounds started / timer began
* `ends_at` (nullable)      — `started_at + time_limit_seconds`
* `completed_at` (nullable)
* `winner_player_id` (nullable on tie or double-bust)
* `initiator_final_coverage` (nullable float, 0–1)
* `opponent_final_coverage`  (nullable float, 0–1)
* `initiator_gross_payout`   (nullable int, 0–300)
* `opponent_gross_payout`    (nullable int, 0–300)

---

# **12. Performance & Scaling Notes**

* Each valid submission does:

  * 1 embedding → 1536-d vector
  * ≤ 1000 cosine comparisons for matching
    (fast on any normal CPU via NumPy/PyTorch)

* Storage:

  * 1536-dim float32 → ~6 KB per answer
  * Max ~6 MB per prompt at K=1000
  * Fully manageable with pruning

* Cluster assignment compares only to **cluster centroids**, not all answers.

* Matching always compares to **all snapshot answers** for accuracy.

---

# **13. Head-to-Head Challenge Mode**

## 13.1 Concept

Head-to-head is a thin wrapper on top of **standard ThinkLink rounds**.

A challenge is:

> (initiator_player, opponent_player, shared_prompt, shared_snapshot, time_limit = 5 minutes)

Key properties:

* Each player plays a **normal `tl_round`** with all the usual rules:
  * Same phrase validation
  * Same strike logic (3 strikes ends the round)
  * Same weighted coverage and payout curve
* The two rounds:
  * Share the **same `prompt_id`**
  * Share the **same snapshot** of answers + clusters (frozen once at challenge start)
* Additional constraints / UI:
  * **5-minute hard time limit** for both players
  * **Challenge modal** shows:
    * Countdown timer
    * Live coverage % for both players as progress bars
  * **Results screen** at the end compares their performance in detail

Economics are unchanged: each player pays the normal ThinkLink entry cost (100 coins) and gets an individual payout via the standard curve (Section 8). The “competition” is purely about who achieved higher coverage / payout.

---

## 13.2 Challenge lifecycle

### 13.2.1 Creation (`status = "pending"`)

1. Player A taps **“Challenge”** in the ThinkLink UI and selects Player B.
2. Backend:
   * Verifies both players exist and are not currently in an active ThinkLink round.
   * Creates a `tl_challenge` row with:
     * `status = "pending"`
     * `initiator_player_id`, `opponent_player_id`
3. Prompt selection:
   * Use the **same prompt-selection logic** as standard ThinkLink single-player.
   * Store `prompt_id` on `tl_challenge`.

At this point, **no rounds** exist yet and **no coins are charged**.

### 13.2.2 Acceptance and start (`status = "active"`)

When Player B accepts:

1. Build a **single snapshot** for the chosen prompt, as in Section 4.1:
   * Up to K = 1000 active answers
   * Their embeddings
   * Cluster assignments
   * Cluster weights

2. Initialize two `tl_round` rows with **identical snapshot data**:

   * `round_id` A for `initiator_player_id`
   * `round_id` B for `opponent_player_id`
   * `prompt_id` = `tl_challenge.prompt_id`
   * `snapshot_answer_ids` / `snapshot_cluster_ids` copied from the shared snapshot
   * `matched_clusters = ∅`, `strikes = 0`
   * `challenge_id` = `tl_challenge.challenge_id` on both rounds

3. Set challenge timing:

   * `tl_challenge.time_limit_seconds = 300` (configurable, default 5 minutes)
   * `started_at = now`
   * `ends_at = started_at + time_limit_seconds`
   * `status = "active"`

4. Charge entry for both players exactly as for normal ThinkLink rounds (100 coins each).

The timer starts **only** when both rounds are created and `started_at` is set.

### 13.2.3 Round progression

From the engine’s perspective, **each player’s loop is unchanged** (see Section 4.2):

* Validate phrase
* Embed
* Compare vs snapshot answers
* Update `matched_clusters`
* Add a strike on a valid guess with zero matches

Additional **challenge-specific** behaviour:

* After every accepted guess (valid + embedded), recompute **current coverage**:

```text
  current_p = (Σ cluster_weight_c for c in matched_clusters) / W_total
````

* Persist `final_coverage` and `gross_payout` to `tl_round` when the round ends.
* Update an in-memory/live challenge state used for the progress modal:

  * `coverage_initiator_live` (0–1)
  * `coverage_opponent_live` (0–1)
  * `strikes_initiator`
  * `strikes_opponent`

This live state is exposed via WebSocket events or a simple polling endpoint (implementation detail).

### 13.2.4 End conditions for a challenge

Each individual `tl_round` ends when:

* Player quits voluntarily, **or**
* Player reaches **3 strikes**, **or**
* `now >= tl_challenge.ends_at` (time limit hit)

The **challenge** moves to `completed` when:

* Both rounds have ended **or**
* `now >= ends_at` and at least one round has ended (any remaining round is forced closed at `ends_at` with its current coverage).

On challenge completion:

1. Compute each player’s **final coverage** from their `tl_round.final_coverage`.

2. Compute each player’s **gross payout** via the standard curve (Section 8), if not already stored.

3. Determine winner:

   ```text
   if initiator_final_coverage > opponent_final_coverage:
       winner_player_id = initiator_player_id
   elif opponent_final_coverage > initiator_final_coverage:
       winner_player_id = opponent_player_id
   else:
       winner_player_id = NULL  # tie
   ```

4. Write summary stats back to `tl_challenge`:

   * `initiator_final_coverage`, `opponent_final_coverage`
   * `initiator_gross_payout`, `opponent_gross_payout`
   * `winner_player_id`
   * `completed_at = now`
   * `status = "completed"`

---

## 13.3 Time limit and enforcement

**Server-side enforcement**

* Any submission attempt after `now >= ends_at` for a challenge-linked `tl_round` returns an error (e.g. `ROUND_EXPIRED`) and is ignored.
* A background job or on-request check ensures that if the client “misses” the exact deadline, the round is still finalized correctly using the last valid state.

**Client-side display**

* Challenge modal shows a countdown derived from `ends_at`:

  * `remaining_seconds = max(0, floor(ends_at - now_client_synced))`
* When timer hits zero:

  * Input is disabled and the UI transitions to a “Time’s up” state while waiting for final results.

---

## 13.4 Live progress modal

The challenge modal is a **non-blocking overlay** that can be opened at any time during the round.

Minimum contents:

* Prompt text (truncated if long)
* 5-minute countdown timer
* Two coverage bars:

  ```text
  [Player A username]  [██████████......]  63%
  [Player B username]  [██████..........]  27%
  ```

Rules:

* Coverage %= `current_p * 100`, rounded to 1 decimal place or nearest integer.
* Updates are **event-driven** (e.g., via WebSocket) whenever either player’s `matched_clusters` changes.
* No details about **which clusters** are matched by either player are exposed here — only the aggregate coverage %, strikes count, and an optional “guesses made” counter.

Optional extras (still compatible with spec):

* Small indicators for strikes:

  * e.g., `●●○` for 2 strikes out of 3
* Guesses count per player.

---

## 13.5 Results screen

After the challenge completes, both players see a **shared results view** plus their existing single-round ThinkLink results.

Minimum data to display:

* Prompt text
* For each player:

  * Username
  * Final coverage % (derived from `final_coverage`)
  * Gross payout (0–300) and net wallet change
  * Strikes used
  * Total guesses submitted
* Winner banner:

  * “You won!” / “You lost” / “It’s a tie!”

Optional extra detail (still within this spec):

* Show a short breakdown of the player’s performance:

  * Number of clusters matched vs total clusters in snapshot
  * A few example clusters they hit (using `tl_cluster.example_answer_id`) and their weights
* “Rematch” CTA that creates a new `tl_challenge` with roles swapped or same opponent.

Implementation:

* The results screen can reuse the normal ThinkLink single-round result payload, plus an extra `challenge_summary` struct sourced from `tl_challenge`.

---

## 13.6 Edge cases & failure handling

* **Opponent never accepts**:

  * If `status = "pending"` and no acceptance within a configurable timeout (e.g. 15 minutes), set `status = "expired"` and never create `tl_round` records or charge coins.
* **Opponent disconnects mid-round**:

  * Their round simply times out at `ends_at`, using whatever `matched_clusters` they had reached.
* **Both players bust early (3 strikes)**:

  * Challenge completes as soon as both `tl_round` records are ended.
  * Winner still determined by coverage; tie allowed.
* **Client clock skew**:

  * Timer is driven off server timestamps (`started_at` + `time_limit_seconds`).
  * Client periodically refreshes `remaining_seconds` from server, but actual enforcement is server-side.

Head-to-head mode is completely additive: if you ignore `tl_challenge` and `tl_round.challenge_id`, all existing ThinkLink behavior is unchanged.