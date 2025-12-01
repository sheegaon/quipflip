# **ThinkLink — Quick Facts (Developer Edition)**

### **Core Idea**

Guess short phrases that semantically match what prior players wrote for the same prompt.
You earn coins based on how much of the “crowd idea space” you cover.

---

# **Gameplay Loop**

* Player gets a prompt.
* Player submits short phrases (validated like Quipflip).
* Each valid guess is compared against **all active answers** for that prompt.
* If the guess matches **no** active answers → **strike**.
* Three strikes end the round.
* Player may quit anytime.

---

# **Phrase Validation (same as Quipflip)**

* 2–5 words
* A–Z letters + spaces only
* All words in dictionary
* No repeated significant words
* On-topic semantic check → must resemble the prompt
* Moderation check
* Must not be too similar to the player’s previous guesses

Rejected phrases **do not** cause strikes.

---

# **Snapshots**

At round start the system freezes:

* Up to **1000 active answers**
* Their embeddings
* Their cluster mappings
* Their weights

All matching/scoring uses this snapshot.

---

# **Matching**

* Embed submission with OpenAI `text-embedding-3-small`
* Compare to all snapshot answers (≤1000) via cosine similarity
* **Match** = similarity > **0.55**
* Any matched answers add their **cluster** to the player's matched set
* Multiple answers in the same cluster count once

---

# **Clustering (Used for Scoring, Not for Matching)**

* Happens **only** when new answers are added to the corpus
* New answer compares to **cluster centroids**, not all answers
* Join cluster if similarity ≥ 0.75
* Else create new cluster
* Centroid = running mean of embeddings
* Clustering compresses synonyms into “idea buckets”

---

# **Weighted Coverage (Scoring Metric)**

Each answer has a weight:

```
w = 1 + log(1 + min(#distinct_players, 20))
```

Cluster weight = sum of its answer weights
Total snapshot weight = sum of all cluster weights

Player’s coverage:

```
p = (weight of matched clusters) / (total snapshot weight)
```

---

# **Payout**

* Entry cost: **100 coins**
* Max gross payout: **300 coins**
* Gross payout curve:

```
gross = 300 * (p ** 1.5)
```

Rounded and clamped to [0, 300].

### Vault Split

* If gross ≤ 100 → player keeps all (entry refund / small loss)
* If gross > 100 → 30% of (gross - 100) goes to vault

Net wallet change = wallet_award – 100.

---

# **Strikes**

* A valid submission with **no matches** → **1 strike**
* 3 strikes ends the round
* Invalid submissions never consume strikes

---

# **Performance Constraints**

* Max 1000 answers per prompt
* ~6MB per fully populated prompt
* ~1000 cosine operations per guess
* Clustering uses centroids only (fast)
* Matching uses all answers (accurate)
