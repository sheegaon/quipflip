# MemeMint “Circles” Feature — Product Specification (MVP)

## 1. High-Level Summary

We’re introducing **Circles** to MemeMint: persistent social groups whose members’ memes and captions are preferentially shown to each other during play. Circles create the feeling of “being in a room with people you know,” but without requiring real-time coordination or lobbies.

Key principles:

* A **Circle** is a persistent group of users.
* A player may belong to multiple Circles.
* When you play MemeMint, the system **prioritizes content created by people in your Circles**.
* If Circle content isn’t available or eligible, the system **falls back to the global pool** seamlessly.
* **No extra system bonus** is awarded when voting for someone in your Circle, preventing coordinated farming.

Circles are **MemeMint-only** for MVP—no cross-game social graph is required yet.

---

## 2. Core Intent of “Circle”

“Circle” conveys:

* A persistent social cluster.
* Non-competitive, non-ranked.
* Your Circle’s creative output is surfaced to you more often.
* Works intuitively with multiple memberships (“your circles”).

This aligns with the feature’s actual behavior better than “Team,” which implies competition or structure the feature doesn’t have.

---

## 3. Goals and Non-Goals

### 3.1 Goals

* Make MemeMint feel more social and personal.
* Boost the frequency with which players encounter **captions from people they know**.
* Retain all global discovery mechanisms when Circle content is sparse or exhausted.
* Preserve fairness: no mechanical advantages or extra MC yields for Circle-based voting.

### 3.2 Non-Goals (MVP)

* No private Circles in MVP (all Circles are discoverable).
* No Circle chat.
* No Circle-specific leaderboards, vaults, or currencies.
* No “play in Circle mode” toggle — gameplay is global but biased toward Circle content.
* No moderation tooling beyond simple add/remove.

---

## 4. Key Concepts & Definitions

### **Circle**

A persistent, named group of MemeMint players.

### **Circle Admin**

The user who created the Circle. They can:

* Add any user instantly.
* Remove any member.
* Approve join requests.
* Optionally rename the Circle (if supported).

(MVP may treat the founder as the sole admin.)

### **Circle Member**

Any user belonging to the Circle.

### **Circle-Mate**

For player **P**, any user who shares **any** Circle with P.
Circles form a **union**: if P and Q share one or more Circles, Q is a Circle-mate from the standpoint of gameplay.

### **Circle-Participating Image (for P)**

An image containing ≥1 **eligible** caption authored by any Circle-mate of P.
If all such captions are already seen or authored by P, the image is treated as having **no Circle content**.

---

## 5. Gameplay Effects of Circles

Circles affect only **image and caption selection** in voting rounds.

All other mechanics (entry fee, riff logic, pick logic, vault behavior, global stats) remain unchanged, except for the system bonus suppression rule (Section 6).

### 5.1 Baseline Behavior (Current MemeMint)

For reference, today MemeMint:

1. Picks a random image with ≥5 eligible captions.
2. Picks 5 eligible captions using a quality_score-weighted random.
3. Player votes; winner’s author(s) receive:

   * 5 MC from vote entry fee.
   * * a 3× system writer bonus.

### 5.2 New Image Prioritization with Circles

When selecting an image for player **P**:

1. Identify all **eligible images** (same criteria as today: active image, ≥5 eligible captions).
2. Filter to images where P has at least one Circle-mate who produced an eligible caption.

   * This produces the “Circle-participating image list.”
3. Behavior:

   * **If the list is non-empty** → Pick randomly **from the Circle-participating list** only.
   * **If the list is empty** → Fall back to **global random selection** as today.

This preserves randomness while prioritizing Circle content.

### 5.3 New Caption Prioritization with Circles

Once an image is selected:

1. Compute all eligible captions for P (same rules as today: not P’s own, not previously seen).
2. Partition them into:

   * **Circle captions** (authored by Circle-mates)
   * **Global captions** (all others)

Let `k = number of Circle captions`.

**Case A — k ≥ 5**

* Select **all 5** captions from the Circle captions only.
* Use the same quality_score-weighted random algorithm, but applied only to Circle captions.

**Case B — 0 < k < 5**

* Show **all k** Circle captions.
* Fill the remaining **5 – k** slots with Global captions chosen via the existing weighted algorithm.

**Case C — k = 0**

* Behave exactly as global mode today: weighted random from all global eligible captions.

**Key principle:**
Circle captions **override** higher-quality global captions. Quality weighting only applies **within** the Circle or global pools after the Circle-first split.

---

## 6. System Bonus Suppression for Circle Votes

To prevent coordinated Circle-based farming of the 3× system writer bonus:

### Current behavior

Winner’s author(s) get:

* Base 5 MC from entry fee.
* * System writer bonus (currently 15 MC total).

### New rule

If a user **P** votes for a caption, and **any** of that caption’s earning authors is a **Circle-mate** of P:

* The system writer bonus is **suppressed** for that author.

This is evaluated **per earning author**:

* If riff: riff author and parent author are evaluated separately.
* Example:

  * Riff author is P’s Circle-mate → riff author gets no system bonus share.
  * Parent author is **not** P’s Circle-mate → parent still gets their system bonus share.

The base 5 MC payout is always unaffected.

---

## 7. Circle Membership and Management (MVP UX)

A new **Circles** page is added to MemeMint.

### 7.1 Structure of the Circles Page

**1. My Circles**
List the Circles the user belongs to. Each shows:

* Name
* Member count
* “Open” button

**2. Create a Circle**
Simple form:

* Name (unique)
* Optional short description
  Creator becomes admin + first member.

**3. Discover Circles**
A browsable list of all Circles:

* All Circles are discoverable in MVP.
* Shows name, description, member count.
* “Request to Join” button.

**4. Circle Detail View**
Shows:

* Members list
* Circle-mate indicator on known users (optional)
* If viewer is admin:

  * Add member (enter username)
  * Remove member
  * Approve/deny join requests
  * Rename Circle (optional)

### 7.2 Membership Rules

* **Joining**

  * Users tap “Request to Join.”
  * Admin approves/denies.
  * Admins may also instantly add any user.

* **Leaving**

  * Any member can leave anytime.

* **Immediate effect**

  * Joining: all existing content from Circle members instantly becomes Circle-prioritized (subject to eligibility).
  * Leaving: those players immediately cease being Circle-mates.

* **Deletion**

  * MVP can omit Circle deletion, or allow an admin to delete it entirely—your choice; not required by the spec.

### 7.3 All Circles Are “Public” in MVP

* “Public” means:

  * Discoverable.
  * Anyone can request to join.
  * Admin approval still required.

We do **not** implement private or invite-only modes in MVP.

---

## 8. Voting Round UI Changes

### 8.1 During Voting

We intentionally **hide** Circle affiliation during voting to avoid bias or social pressure.

* Captions appear with no Circle indicator.
* No author names shown (same as today).

### 8.2 After Voting (Reveal)

After vote is cast and results are revealed:

* Show all five captions with:

  * Winning caption marked.
  * Authors’ display names.
  * **Circle icon** beside authors who are Circle-mates of the viewer.
  * Existing **Bot icon** remains for AI captions.

This mirrors current post-vote behavior but with a new “Circle” badge.

---

## 9. Multiple Circles

* A user may belong to many Circles.
* Circle-mates = **union of all members across all your Circles**.
* We do *not* visually distinguish which Circle a Circle-mate comes from.
* Circle prioritization logic treats all Circles equally.

---

## 10. Edge Cases & Clarifications

1. **User with no Circles**

   * Experience is identical to today.

2. **Inactive Circle**

   * If your Circles aren’t producing eligible captions, system falls back to global naturally.

3. **Previously seen captions**

   * Circle prioritization respects the “not previously seen” rule.

4. **Caption authorship changes or membership changes after creation**

   * Circle relationship is evaluated at the moment of the round/vote—not at caption creation time.

5. **Bots**

   * Bots are never Circle-mates.

6. **Images with insufficient total captions**

   * Must still meet global eligibility: ≥5 eligible captions in total.

---

## 11. Ordering of Filters — Conceptual Model

The clean model is:

1. Compute eligible images (global rules).
2. Identify Circle-participating images.
3. Prefer those if any exist; otherwise global.
4. Within chosen image:

   * Compute eligible captions.
   * Partition Circle vs global.
   * Fill 5 slots as per rules.

This keeps the feature bolt-on and avoids rewriting core logic.

---

## 12. Out-of-Scope (MVP)

* Circle chat
* Circle badges on profiles
* Circle leaderboards or aggregated vault stats
* Circle quests
* Private Circles
* Circle-specific modes (“play only with Circle X”)
