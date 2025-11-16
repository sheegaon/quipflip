# Initial Reaction — Game Rules

## Overview

**Initial Reaction** is an asynchronous multiplayer word game where players invent clever *backronyms* for randomly generated short words, then vote on which backronym deserves to win. The game uses the same in-game economy, wallet, and vault structure as **Quipflip**, with InitCoins earned and spent across rounds.

Players compete in two modes:

* **Standard Mode:** waits for human participants; AI fills only if rounds stall.
* **Rapid Mode:** AI fills after short timeouts for fast-paced play.

---

## Round Types

There are two round types:

### 1. Backronym Round

* Cost: **100 InitCoins**
* Player is served a **random 3–5 letter English word** from the standard dictionary (same validator as Quipflip).
* The player must create a *backronym* — one word per letter, each word validated against the dictionary.
* Grammar doesn’t matter; only that all words are valid.
* Repeated words are allowed.
* The backronym must have exactly the same number of words as letters in the given word.
* When **five backronyms** have been submitted for a prompt word, that set proceeds to voting.

### 2. Voting Round

* Once a backronym set reaches five entries, voting opens.
* Only the five backronym creators and **non-participant voters** who registered **before** the first participant joined can vote.
* Players **cannot vote for their own backronym.**
* Voters choose **one** favorite backronym; order is randomized for each voter.
* Non-participant voters:

  * Pay **10 InitCoins** to vote.
  * Win **20 InitCoins** if their choice matches the most popular backronym.
  * A backronym set accepts up to **five non-participant voters.**
  * Their entry fees (10 InitCoins each) go into the shared prize pool.
  * Their winnings (20 InitCoins each) come **out of** the same pool before creator payouts are calculated.

* Participants (backronym creators) vote for free.

---

## Prize Pool and Payouts

* Each backronym creator pays 100 InitCoins → total **500 InitCoins** from creators.
* Each non-participant voter pays 10 InitCoins → adds up to **50 InitCoins** more.
* Total prize pool = **550 InitCoins** in the example above.

**Payout order:**

1. Non-participant winners (up to 5 × 20 = 100 InitCoins) are paid from the pool first.
2. The remaining pool is split among the five backronym creators in proportion to their received votes.
3. Players must cast their own votes to receive their share of winnings.

   * If a backronym creator doesn’t vote before round finalization, their share is forfeited to the vault.
4. **30% of each player’s net winnings** are automatically added to their **vault** (same as Quipflip).

---

## Round Finalization

* The voting phase finalizes when:

  * **All five backronym creators** have voted, or
  * The **timeout** period expires.

### Timeout Windows

| Mode              | Trigger                                       | Timeout Duration              |
| ----------------- | --------------------------------------------- | ----------------------------- |
| **Rapid Mode**    | 2 minutes after the last backronym submission | AI votes fill remaining slots |
| **Standard Mode** | 30 minutes after the last human vote          | AI votes fill remaining slots |

* AI voters ensure a minimum of **five total votes**.
* Once finalized, payouts are distributed automatically, and results become viewable.

---

## Queues and Matchmaking

* Separate queues exist for **Standard** and **Rapid** play.
* The **backronym queue** prioritizes outstanding words before generating new ones:

  * If any active word sets are missing backronyms, those prompts are served first.
  * New random words are only served when no open backronym sets exist in that mode.

---

## AI Behavior

* The AI system mirrors Quipflip’s backup and stale handlers.
* AI submits backronyms and votes under special “bot” accounts marked with a **bot icon**.
* AI backronyms and votes follow the same rules as human entries.
* AI prompt templates weight responses toward **coherence, humor, and wordplay quality.**
* AI participates automatically:

  * **Standard Mode:** when timeouts expire.
  * **Rapid Mode:** after 2 minutes, ensuring 5 total entries per set.

---

## Progress and Results

Players can view a **Backronym Progress Screen** showing:

* Each word they’re currently competing on.
* Number of total entries (out of 5).
* Live countdowns for rapid rounds.
* When voting opens, an immediate “Vote Now” button appears.

Once finalized:

* Results show all five backronyms with their vote percentages.
* AI participants are marked clearly.
* Rewards are automatically credited on result view.

---

## Leaderboards

Two independent leaderboards:

1. **Creator Leaderboard**

   * Ranked by total **vault contributions** (30% of net winnings).
   * Reflects total long-term performance.

2. **Voter Leaderboard**

   * Ranked by **correct vote percentage** (how often they picked the most popular backronym).
   * Ties broken by total correct votes.

---

## Economy Summary

| Action               | Cost                | Potential Reward           | Notes                     |
| -------------------- | ------------------- | -------------------------- | ------------------------- |
| Backronym entry      | 100 InitCoins           | Proportional share of pool | Must vote to claim        |
| Non-participant vote | 10 InitCoins            | 20 InitCoins if correct        | Max 5 per round           |
| AI entry             | —                   | No wallet impact           | Backup participation only |
| Vault contribution   | 30% of net winnings | —                          | Automatic                 |
| Daily login bonus    | Same as Quipflip    | —                          | Optional cross-game bonus |

---

## Anti-Cheat and Limits

* No player can vote for their own backronym.
* Duplicate entries (same player submitting multiple backronyms for one word) disallowed.
* Guests limited by IP rate caps (mirroring Quipflip).
* AI players excluded from leaderboards.

---

## Practice and Review

* **Practice Mode:** future feature for viewing past completed sets.
* **Observers:** can view finalized rounds only (no live access).

---

Would you like me to:

1. Format this for repo insertion (section headers, consistent with Quipflip’s markdown style), or
2. Add a **“Game Flow Diagram”** section visualizing how a backronym moves from creation → voting → payout (for docs/marketing)?
