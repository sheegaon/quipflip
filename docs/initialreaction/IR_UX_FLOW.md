# **Initial Reaction — Rapid Mode UX Flow**

*(Applies to both guest and registered players, with guest-specific rules highlighted.)*

## **Overview**

This document describes the end-to-end user experience flow for a **Rapid Backronym Battle** in *Initial Reaction*. Rapid rounds finalize quickly (≈2 minutes per phase) and rely heavily on AI to ensure continuous gameplay. The flow is designed to minimize confusion, keep players engaged, and streamline onboarding — especially for **guest players**, who have restricted voting privileges unless they are participants.

---

# **1. Dashboard Entry**

### **Registered players**

* See a standard dashboard with:

  * Wallet balance
  * Vault balance
  * Option: **“Backronym Battle (Rapid)”**
  * Voting options for ongoing sets **if allowed** (only when they are eligible voters)

### **Guest players**

* See a simplified dashboard:

  * **No voting options** (guests cannot vote on sets they didn’t participate in)
  * Only one actionable item: **“Start Backronym Battle”**
* Goal: funnel them into creation first.

---

# **2. Start a Backronym Battle**

When the player taps **Backronym Battle**:

* Backend returns a random **3–5 letter word**.
* The UI transitions immediately into the **Backronym Creation Screen**.

---

# **3. Backronym Creation Screen**

### **Features**

* The target word is displayed as large letter tiles.
* For each letter, the player must type a matching word.
* Front-end behavior:

  * Displays each typed letter as a tile.
  * First letter forced to **Capitalized**, rest lowercase in tile view.
  * If typed first letter doesn’t match the required initial → **tile turns red**.
  * While typing a word → **tiles remain yellow** (pending).
  * When user presses **space**, that word is:

    1. Sent to the backend for validation.
    2. Tile color updates to **green** (valid) or **red** (invalid).
* The player pays **100 InitCoins** upon submitting the full backronym.
* After submission, the player does **not** return to dashboard.

### **Post-submit transition**

Player is automatically taken to the **Set Tracking Screen**.

---

# **4. Set Tracking Screen (Live Progress View)**

This screen is central to the rapid-round experience.

### **What the player sees**

* “X of 5 backronyms submitted”
* A countdown timer (typically 2 minutes)
* Updates as:

  * Human players submit backronyms
  * AI fills remaining slots at the 2-minute mark

### **Behavior**

* Players cannot start a new backronym while an active one is pending.
* The goal is to anchor them until voting begins.
* Once the set reaches **5 total entries**, the UI transitions automatically to voting.

---

# **5. Voting Phase**

### **Eligibility**

* **Participants (creators):**

  * Automatically eligible to vote
  * **No voting cost**
* **Non-participants (registered accounts):**

  * Must pay **10 InitCoins**
  * Guests are not allowed to vote unless they are participants

### **Voting Screen**

* All five backronyms are shown in **random order**.
* The player’s own backronym:

  * Is marked “yours”
  * Is disabled (cannot vote for it)
* Non-participant voters see a 10-InitCoin fee confirmation before accessing submissions.
* Timer: ~2 minutes.

### **After vote submission**

UI shows a **Vote Tracking View**, displaying:

* Vote counts as they come in
* Countdown timer to finalization

---

# **6. Finalization**

A round finalizes when:

* All 5 creators have voted, **or**
* The 2-minute voting timer expires (AI votes fill remaining slots)

### **Finalization rules**

* AI ensures at least **5 total votes**
* Prize pool is computed and payouts applied:

  1. Non-participant winners get **20 InitCoins** (from the pool)
  2. Remaining pool split among creators **proportionally by vote share**
  3. **30% vault skim** applied to each creator’s net winnings

---

# **7. Results Screen**

Once finalized, the player is shown:

* Final vote percentages
* Winning backronym highlighted
* Their vote highlighted
* Detailed InitCoin breakdown:

  * Payout amount
  * Vault contribution
  * Net gain

This screen completes the gameplay loop. When dismissed, the player returns to the dashboard.

---

# **Summary Diagram (High-Level)**

```
Dashboard
   ↓
Backronym Creation
   ↓
Set Tracking (wait for 5 entries)
   ↓
Voting (participant = free, non-participant = 10 InitCoins)
   ↓
Vote Tracking
   ↓
Finalize (AI-assisted)
   ↓
Results & Payouts
   ↓
Dashboard
```

---

# **Notes for MVP Implementation**

* UX flow described here is **Rapid mode only**.
* All transitions are **push-forward only** (never dump the user back to the dashboard mid-round).
* Guests follow the same flow but:

  * Cannot vote unless they are creators
  * Have a simplified dashboard
* Backend polling (REST) is sufficient for tracking; WebSockets not required.
