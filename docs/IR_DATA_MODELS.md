# Initial Reaction Data Model Specification

This guide covers the Initial Reaction models inside `backend/models/ir`, which extend the shared foundations documented in [DATA_MODELS.md](DATA_MODELS.md). Wallets, tokens, quests, notifications, and other shared primitives come from the base modules and are not repeated here.

---

## Overview

Initial Reaction (“IR”) mirrors Quipflip’s round/phraseset pattern with entities specialized for backronyms:

* **BackronymSet** – the unit of play for one 3–5 letter word; collects 5 creator entries and fans into a voting phase.
* **BackronymEntry** – a creator’s backronym for the set word (one token per letter).
* **BackronymVote** – a single-choice vote tied to a set; supports participant and non-participant voters.
* **BackronymObserverGuard** – snapshot for eligibility gating (non-participant voters must have accounts created before the first participant).

All economics (coins, vault skim, prize calculation order) are enforced by services and ledgered in the shared **Transaction** table. Payout claiming and “results viewed” idempotency reuse **ResultView**.

---

## Enums

### `IRSetStatus`

* `open` – collecting creator entries (≤5)
* `voting` – 5 entries locked; accepting votes (participant + up to 5 non-participants)
* `finalized` – voting closed; payouts computed; results immutable

### `IRMode`

* `standard` – human-first; AI fills after long timeout
* `rapid` – fast-fill; AI engages at 2-minute windows

---

## BackronymSet

Represents the lifecycle of one random **3–5 letter word**.

| Field                          | Type                              | Notes                                                      |
| ------------------------------ | --------------------------------- | ---------------------------------------------------------- |
| `set_id`                       | UUID (PK)                         | Primary key                                                |
| `word`                         | VARCHAR(5)                        | Uppercase; 3–5 letters; dictionary-sourced                 |
| `mode`                         | ENUM(`standard`,`rapid`)          | Queue segregation & timeout policy                         |
| `status`                       | ENUM(`open`,`voting`,`finalized`) | State machine                                              |
| `entry_count`                  | INT                               | Cached count of creator entries (0–5)                      |
| `vote_count`                   | INT                               | Total votes (participant + non-participant)                |
| `non_participant_vote_count`   | INT                               | For cap enforcement (max 5)                                |
| `total_pool`                   | INT                               | Final pool at close (creators + non-participant fees)      |
| `vote_contributions`           | INT                               | Sum(10) from non-participant voters                        |
| `non_participant_payouts_paid` | INT                               | Sum(20) paid to correct non-participants                   |
| `creator_final_pool`           | INT                               | `total_pool - non_participant_payouts_paid` at finalize    |
| `first_participant_joined_at`  | TIMESTAMP                         | When 1st creator entered set (for gating snapshot linkage) |
| `created_at`                   | TIMESTAMP                         | Set creation                                               |
| `finalized_at`                 | TIMESTAMP NULL                    | Set finalization                                           |
| `last_human_entry_at`          | TIMESTAMP NULL                    | For rapid AI fill trigger                                  |
| `last_human_vote_at`           | TIMESTAMP NULL                    | For standard timeout trigger                               |

**Indexes**

* `ix_ir_set_status_created` → (`status`, `created_at`)
* `ix_ir_set_mode_status` → (`mode`, `status`)
* `ix_ir_set_finalized_at` → (`finalized_at`)
* `ix_ir_set_word_status` → (`word`, `status`) (serving outstanding sets first)
* `ix_ir_set_last_human_vote` → (`last_human_vote_at`)

**Constraints**

* `word` length 3–5, A–Z only.
* `entry_count` ∈ [0,5]; `non_participant_vote_count` ∈ [0,5].
* `status` transitions enforced by service layer: `open→voting→finalized`.

**Notes**

* `creator_final_pool` is computed at finalize; persisted for audit & ResultView consistency.
* AI behavior and minimum votes are service-level guarantees; not a schema constraint.

---

## BackronymEntry

One creator’s backronym for the set word. Exactly **N tokens** for **N letters**, all dictionary-valid. Grammar not required; repeats allowed.

| Field                | Type                            | Notes                                     |
| -------------------- | ------------------------------- | ----------------------------------------- |
| `entry_id`           | UUID (PK)                       | Primary key                               |
| `set_id`             | UUID (FK → BackronymSet.set_id) | Partition key                             |
| `player_id`          | UUID (FK → Player.player_id)    | Creator                                   |
| `backronym_text`     | JSONB                           | Array of `N` uppercase strings, N∈{3,4,5} |
| `is_ai`              | BOOL (default false)            | AI-submitted                              |
| `submitted_at`       | TIMESTAMP                       | Creation time                             |
| `vote_share_pct`     | NUMERIC(6,3) NULL               | Filled at finalize (0–100)                |
| `received_votes`     | INT (default 0)                 | Count at finalize                         |
| `forfeited_to_vault` | BOOL (default false)            | True if creator didn’t vote               |

**Indexes**

* `ix_ir_entry_set` → (`set_id`)
* `ix_ir_entry_player_set` → (`player_id`, `set_id`)
* `ix_ir_entry_submitted` → (`submitted_at`)

**Constraints**

* **Unique** `(player_id, set_id)` – one entry per creator per set.
* `json_schema`: `backronym_text` length must equal `length(word)` of parent set; each token A–Z[2..15] chars (same validator rules as Quipflip).
* Foreign-key cascade delete on `set_id`.

**Notes**

* Self-vote prohibition is enforced at `BackronymVote` submission time (service).

---

## BackronymVote

A **single-choice** vote over the five entries of a set. Supports both participant voters (creators) and up to **five** non-participant voters per set.

| Field                  | Type                                | Notes                                     |
| ---------------------- | ----------------------------------- | ----------------------------------------- |
| `vote_id`              | UUID (PK)                           | Primary key                               |
| `set_id`               | UUID (FK → BackronymSet.set_id)     | Partition key                             |
| `player_id`            | UUID (FK → Player.player_id)        | Voter                                     |
| `chosen_entry_id`      | UUID (FK → BackronymEntry.entry_id) | The selected entry                        |
| `is_participant_voter` | BOOL                                | True if voter is one of the five creators |
| `is_ai`                | BOOL (default false)                | AI-submitted                              |
| `is_correct_popular`   | BOOL NULL                           | For non-participants only (20 InitCoin win)   |
| `created_at`           | TIMESTAMP                           | Vote time                                 |

**Indexes**

* `ix_ir_vote_set` → (`set_id`)
* `ix_ir_vote_player_set` → (`player_id`, `set_id`)
* `ix_ir_vote_created` → (`created_at`)

**Constraints**

* **Unique** `(player_id, set_id)` – one vote per player per set.
* **Check**: `chosen_entry_id` must belong to the same `set_id`.
* **Service rule**: voter cannot select their own entry (enforced in service).
* **Service rule**: cap **non-participant** votes at 5 per set; reject 6th.

**Notes**

* `is_participant_voter` flags creator compliance (must vote to claim).
* `is_correct_popular` populated at finalize for non-participant payout (+20).

---

## BackronymObserverGuard

Eligibility snapshot to gate non-participant voters: they must have **account creation time ≤ snapshot**.

| Field                          | Type                                | Notes                                                    |
| ------------------------------ | ----------------------------------- | -------------------------------------------------------- |
| `set_id`                       | UUID (PK, FK → BackronymSet.set_id) | One row per set                                          |
| `first_participant_created_at` | TIMESTAMP                           | The earliest `Player.created_at` among the five creators |

**Indexes**

* `pk_ir_guard_set_id` (primary key)

**Notes**

* Set when the first entry is committed.
* Service checks `voter.account_created_at ≤ first_participant_created_at` before allowing a non-participant vote.

---

## Reused Models (no schema changes)

* **Player** – accounts, auth, `created_at` used for observer gating.
* **Round (unified)** – not used directly by IR (IR exposes its own `/ir/rounds/*` endpoints).
* **Transaction (Ledger)** – all debits/credits; include `reference_id = set_id` for IR entries and votes; types:

  * `ir_backronym_entry`, `ir_vote_entry`, `ir_vote_payout`, `ir_creator_payout`, `vault_contribution`
* **ResultView** – idempotent prize collection & “view results” tracking per creator (`phraseset_id` analog replaced by `set_id`).
* **AIMetric / AIPhraseCache** – reused with `game="initial_reaction"`; caches for IR prompts and voting prompts.

---

## Prize Accounting (service-level; persisted for audit)

On **finalize**:

1. **Pool assembly**

   * Creator fees: `100 × 5 = 500`
   * Non-participant fees: `10 × k`, `k ≤ 5`
   * `total_pool = 500 + 10k` → persist on set

2. **Non-participant payouts first**

   * Winners get `20` each, debited from `total_pool`
   * Persist `non_participant_payouts_paid = 20 × winners`

3. **Creator split**

   * `creator_final_pool = total_pool - non_participant_payouts_paid`
   * Split **pro-rata** by vote share across 5 entries
   * Require each creator to have cast a vote; otherwise **forfeit** their share → mark `forfeited_to_vault=true` on entry; ledger transfer to vault

4. **Vault skim**

   * On each positive creator payout, ledger **30% of net** to vault (same rule as Quipflip)
   * Store `vote_share_pct` and `received_votes` on entries for replayability

5. **ResultView**

   * Emit one `ResultView` per creator (idempotent claim).
   * Non-participant winnings are paid immediately on finalize (no claim step).

**Conservation check** (property-tested):
Sum(all ledger debits) == Sum(all ledger credits + vault).

---

## Leaderboards (computed, not stored)

* **Creator Leaderboard** – rank by **vaulted earnings** (cumulative 30% skim on net IR winnings). Ties: higher total earnings, then earlier member_since.
* **Voter Leaderboard** – rank by **correct-vote percentage** over IR non-participant votes. Ties: more total correct votes, then recency.

AI accounts (emails ending `@quipflip.internal`) are **excluded**.

---

## Admin Config (shared keyspace; referenced by services)

* `ir_backronym_entry_cost` = 100
* `ir_vote_cost` = 10
* `ir_vote_reward_correct` = 20
* `ir_non_participant_vote_cap` = 5
* `ir_standard_timeout_minutes_after_last_human_vote` = 30
* `ir_rapid_fill_delay_minutes_after_last_human_entry` = 2
* `ir_rapid_voting_timeout_minutes_after_last_human_vote` = 2
* `vault_fraction` = 0.30

---

## API Relationships (high level)

* **Create entry** → debits 100 → `BackronymEntry` row → may flip `BackronymSet.status → voting` when 5th arrives.
* **Start vote** → debits 10 for non-participant path → `BackronymVote` row (participant/non-participant).
* **Finalize** → writes pool arithmetic, pays non-participant winners, splits creator pool pro-rata, applies vault, writes `ResultView`.
* **Claim** (creators) → idempotent via `ResultView`.

---

## Alembic Sketch

```sql
-- backronym_set
CREATE TABLE backronym_set (
  set_id UUID PRIMARY KEY,
  word VARCHAR(5) NOT NULL,
  mode VARCHAR(8) NOT NULL CHECK (mode IN ('standard','rapid')),
  status VARCHAR(10) NOT NULL CHECK (status IN ('open','voting','finalized')),
  entry_count INT NOT NULL DEFAULT 0,
  vote_count INT NOT NULL DEFAULT 0,
  non_participant_vote_count INT NOT NULL DEFAULT 0,
  total_pool INT NOT NULL DEFAULT 0,
  vote_contributions INT NOT NULL DEFAULT 0,
  non_participant_payouts_paid INT NOT NULL DEFAULT 0,
  creator_final_pool INT NOT NULL DEFAULT 0,
  first_participant_joined_at TIMESTAMP NOT NULL,
  created_at TIMESTAMP NOT NULL,
  finalized_at TIMESTAMP NULL,
  last_human_entry_at TIMESTAMP NULL,
  last_human_vote_at TIMESTAMP NULL
);

-- backronym_entry
CREATE TABLE backronym_entry (
  entry_id UUID PRIMARY KEY,
  set_id UUID NOT NULL REFERENCES backronym_set(set_id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(player_id),
  backronym_text JSONB NOT NULL,
  is_ai BOOLEAN NOT NULL DEFAULT FALSE,
  submitted_at TIMESTAMP NOT NULL,
  vote_share_pct NUMERIC(6,3),
  received_votes INT NOT NULL DEFAULT 0,
  forfeited_to_vault BOOLEAN NOT NULL DEFAULT FALSE,
  UNIQUE (player_id, set_id)
);

-- backronym_vote
CREATE TABLE backronym_vote (
  vote_id UUID PRIMARY KEY,
  set_id UUID NOT NULL REFERENCES backronym_set(set_id) ON DELETE CASCADE,
  player_id UUID NOT NULL REFERENCES players(player_id),
  chosen_entry_id UUID NOT NULL REFERENCES backronym_entry(entry_id),
  is_participant_voter BOOLEAN NOT NULL,
  is_ai BOOLEAN NOT NULL DEFAULT FALSE,
  is_correct_popular BOOLEAN,
  created_at TIMESTAMP NOT NULL,
  UNIQUE (player_id, set_id)
);

-- guard
CREATE TABLE backronym_observer_guard (
  set_id UUID PRIMARY KEY REFERENCES backronym_set(set_id) ON DELETE CASCADE,
  first_participant_created_at TIMESTAMP NOT NULL
);

-- indexes (sketch)
CREATE INDEX ix_ir_set_status_created ON backronym_set (status, created_at);
CREATE INDEX ix_ir_set_mode_status ON backronym_set (mode, status);
CREATE INDEX ix_ir_set_finalized_at ON backronym_set (finalized_at);
CREATE INDEX ix_ir_set_word_status ON backronym_set (word, status);
CREATE INDEX ix_ir_set_last_human_vote ON backronym_set (last_human_vote_at);

CREATE INDEX ix_ir_entry_set ON backronym_entry (set_id);
CREATE INDEX ix_ir_entry_player_set ON backronym_entry (player_id, set_id);
CREATE INDEX ix_ir_entry_submitted ON backronym_entry (submitted_at);

CREATE INDEX ix_ir_vote_set ON backronym_vote (set_id);
CREATE INDEX ix_ir_vote_player_set ON backronym_vote (player_id, set_id);
CREATE INDEX ix_ir_vote_created ON backronym_vote (created_at);
```

---

## Validation Rules (summary)

* **Word source**: same dictionary + validator as Quipflip.
* **Backronym shape**: length(backronym_text) == length(set.word); each token passes dictionary validation; 2–15 chars; A–Z only (stored uppercase).
* **Voting**: single choice; randomized order per voter; service prevents self-vote; non-participant cap=5; observer gating verified against guard.

---

## Design Notes

* The schema keeps Quipflip tables untouched and relies on the same horizontal services (ledger, vault, AI, metrics).
* Pool arithmetic and vault skims are persisted on the set and entries for replayability, while the **Transaction** table remains the source of truth.
* AI accounts are flagged via `is_ai` and excluded from leaderboards.
* All finalize math is idempotent; re-runs reconcile against the ledger and `ResultView`.