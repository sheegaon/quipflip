# **Echo Chamber — Game Rules (Developer Spec)**

*Complete & Updated*

*Last updated: today*

---

# **1. Overview**

Echo Chamber is a semantic-matching game where players answer a prompt (e.g., *“Name something people forget at home”*).
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

   * Screen with OpenAI moderation or blacklist

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

Echo Chamber rewards matching not just many clusters, but **popular clusters**.

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

Each prompt is pre-seeded with 40–60 AI-generated answers:

* Validate using Quipflip validator
* On-topic check
* Moderation
* Clustering
* Ensure each initial cluster has multiple variants if possible

This ensures a robust initial semantic landscape.

---

# **11. Data Model (Summary)**

## `echo_answer`

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

## `echo_cluster`

* `cluster_id`
* `prompt_id`
* `centroid_embedding`
* `size`
* `example_answer_id` (representative)
* (`cluster_weight` is derived)

## `echo_round`

* `round_id`
* `player_id`
* `prompt_id`
* `snapshot_answer_ids`
* `snapshot_cluster_ids`
* `matched_clusters`
* `strikes`
* `created_at`

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
