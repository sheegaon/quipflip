# **ThinkLink — Game Rules**

# **1. Core Concept**

ThinkLink is a semantic-guessing game.
Players receive a **prompt** (e.g., “Name something people forget at home”) and submit short phrases.
The goal is to submit answers that **semantically match** prior players’ answers.

Players can guess repeatedly, earning points and coins as they match more of the “crowd.”
Bad guesses accumulate **strikes**; three strikes end the round.

Scoring is based on how much of the crowd’s **weighted semantic space** the player covers.

---

# **2. Prompts and Answer Corpus**

### 2.1 Prompt Set

The game maintains a curated set of prompts. Each prompt accumulates a corpus of prior player answers.

### 2.2 Active Answer Cap (K = 1000)

Each prompt maintains **up to 1000 “active” answers**:

* Active answers are used for matching, clustering, and scoring.
* When a prompt exceeds 1000 answers:

  * Low-usefulness / low-weight / oldest answers are marked **inactive**.
  * Inactive answers remain stored but do **not** influence gameplay.

### 2.3 AI Seeding

Each prompt is initially seeded with AI-generated answers:

* Validated using Quipflip’s phrase validator
* Topic-checked
* Moderated
* Clustered (see below)
* Ensured to cover diverse semantic ideas

---

# **3. Phrase Validation**

ThinkLink **reuses the Quipflip phrase validator**.
Every submission must satisfy:

1. **Dictionary + Structure**

   * 2–5 words
   * Letters A–Z and spaces only
   * All words appear in the NASPA dictionary
   * 4–100 characters total

2. **No repeated significant words**
   Prevents trivial variants like “PHONE → MY PHONE → CELL PHONE.”

3. **Moderation**

   * Rejection of obscene or disallowed text (OpenAI moderation or blacklist)

4. **On-Topic Check**

   * Embed both prompt + submission using OpenAI `text-embedding-3-small`
   * Require `cos(prompt, answer) ≥ threshold` (≈ 0.35–0.45)

5. **Self-Similarity Guard**

   * A submission must not be too similar to the player’s own earlier guesses in this round
   * Reject if similarity ≥ **0.80**

Rejected submissions **do not** consume strikes.

---

# **4. Round Lifecycle**

A round is defined as **(player, prompt, frozen snapshot)**.

### 4.1 Snapshot at Round Start

When the round begins, the system freezes:

* Up to **1000 active answers** for the prompt
* Their embeddings
* Their cluster assignments
* Their weights

This snapshot is used for all matching during the round.
New answers from other players do **not** affect the ongoing round.

### 4.2 Guess Loop

For each submission:

1. Validate phrase (Quipflip rules)
2. Embed via OpenAI small
3. Compute cosine similarity vs **all snapshot answers**
4. Detect matched clusters
5. Update player’s matched clusters
6. If **zero** matches occur → **strike**
7. If ≥ 1 match → no strike

Player may guess indefinitely or quit at any time.
The round ends at **3 strikes** or manual quit.

---

# **5. Clustering (Semantic Bucketing)**

Clustering organizes answers into semantic groups (“idea buckets”).
Matching is always done against all answers; clustering only controls **scoring**.

### 5.1 When Clustering Happens

Clustering is performed **only when a new answer is added to the corpus** (not during rounds).

### 5.2 Assignment Procedure

Given a newly accepted answer:

1. Compute embedding
2. Compare to all existing **cluster centroids**
3. If similarity ≥ **0.75**, join that cluster
4. If similarity ≥ **0.90**, treat as near-duplicate (no special logic required unless desired)
5. Otherwise, create a new cluster

### 5.3 Updating Centroids

Clusters update via incremental running mean:

```
new_centroid = (old_centroid * size + new_embedding) / (size + 1)
```

### 5.4 Cluster Usefulness & Pruning

To maintain K=1000 active answers:

* Track for each answer:

  * `shows`
  * `contributed_matches`
* Compute usefulness = contributed_matches / (shows + smoothing)
* Remove least-useful answers first when pruning to 1000 active entries
* Maintain cluster diversity when pruning

---

# **6. Weighted Coverage (Scoring Basis)**

Weighted coverage rewards matching semantically **popular** ideas, not just distinct ones.

### 6.1 Answer Weights

For each answer `j`:

```
answer_players_j = number of distinct players who submitted this exact answer
raw_eff_j = min(answer_players_j, RAW_CAP=20)
w_answer_j = 1 + log(1 + raw_eff_j)
```

### 6.2 Cluster Weights

For each cluster `c`:

```
cluster_weight_c = sum(w_answer_j for answers j in cluster c)
```

Total mass in snapshot:

```
W_total = sum(cluster_weight_c for all clusters)
```

---

# **7. Matching During a Round**

### 7.1 Match Threshold

An answer matches a snapshot answer if:

```
cos(submission, snapshot_answer) > 0.55
```

### 7.2 Cluster-Level Matching

Matching is applied cluster-by-cluster:

* If any answer within a cluster is matched, the **cluster is marked matched**
* Multiple answers in same cluster do not add extra credit
* Maintain `matched_clusters` set during the round

---

# **8. End-of-Round Scoring**

At the end of the round:

```
p = sum(cluster_weight_c for c in matched_clusters) / W_total
```

where:

* `p` ∈ [0, 1]
* `p` is the player’s weighted percent of crowd coverage

### 8.1 Payout Curve

Entry fee: **100 coins**
Max gross payout: **300 coins**

Convex curve:

```
gross = round(300 * (p ** 1.5))
gross = min(max(gross, 0), 300)
```

### 8.2 Vault Split

Coins above 100 count as “winnings.”

```
if gross <= 100:
    wallet_award = gross
    vault_award = 0
else:
    extra = gross - 100
    vault_award = int(extra * 0.30)
    wallet_award = gross - vault_award
```

### 8.3 Net Outcome

Player’s net wallet impact:

```
net_wallet = wallet_award - 100
vault += vault_award
```

---

# **9. Strikes & Termination**

A **strike** occurs when:

* A submission is valid
* AND it matches **zero** snapshot answers (all cosine ≤ 0.55)

The round terminates when:

* Player has **3 strikes**, or
* Player manually quits, or
* The player has matched 100% of the crowd (optional auto-end)

---

# **10. Performance Guarantees**

* Using OpenAI small embeddings:

  * 1536-d vectors
  * ≤ 1000 dot-product comparisons per submission
  * Efficient even on modest CPU
* Storage:

  * ~6 KB per embedding → ~6 MB per fully populated prompt
  * Pruning ensures bounded memory usage
* Cluster maintenance compares only to **centroids**, not the full answer set
* Matching compares to **all 1000 answers** for accuracy

---

# **11. Summary**

ThinkLink is a semantic-guessing game built on four pillars:

1. **Quipflip-grade phrase validation**
2. **Semantic matching** against up to 1000 active answers
3. **Clustered + weighted scoring**, rewarding popular ideas
4. **Predictable gameplay** through snapshot freezing and strike rules

The combination produces:

* Transparent gameplay
* Real-time feedback
* Rich semantic diversity
* Fair, bounded computational cost
