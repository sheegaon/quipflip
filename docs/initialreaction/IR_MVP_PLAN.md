# ⚡ MVP GOAL

> **Document type:** Historical implementation plan
> **Status:** Historical — use IR game rules and current code
> **Audience:** Maintainers seeking design context

A single playable mode of *Initial Reaction* where:

* Players click **Backronym Battle**.
* They get a random 3- to 5-letter word.
* They enter a backronym (100-InitCoin cost).
* AI fills remaining slots until there are 5 entries total.
* Voting opens automatically (2-minute timer).
* Players vote (10-InitCoin cost, 20-InitCoin reward if they choose the most popular).
* AI fills votes if needed; results + payouts finalize automatically.
* Players see results and payouts in their same wallet/vault UI.

Everything else (leaderboards, standard mode, daily challenges, analytics dashboards, etc.) is deferred.

---

# 🔧 Step-by-Step MVP Plan

### **1. Fork & Scaffold**

* Create a new folder: `backend/services/ir/`
  Copy-paste minimal service scaffolding from `services/round_service.py` and `services/phraseset_service.py`.
* Add a new router: `backend/routers/ir_routes.py`.
  Mount under `/api/ir/*`.
* Reuse **Player**, **Transaction**, **Wallet**, **ResultView**, **AIService**, **Validator**, **Vault** exactly as-is.
* Create **two new models only:**

  * `BackronymSet` (subset of spec: just `set_id`, `word`, `status`, `created_at`, `finalized_at`).
  * `BackronymEntry` (creator_id, backronym_text, is_ai, submitted_at).
    → No separate `Vote` table yet; votes can be transient JSON in memory or simple `votes` JSONB on the set.

### **2. Simplify the game flow (stateless MVP loop)**

**a. Round creation**

```python
POST /ir/start
→ debits 100f, generates random 3–5 letter word
→ creates BackronymSet row if none open with that word
→ returns {set_id, word}
```

**b. Player submission**

```python
POST /ir/{set_id}/submit
→ validate N words for N letters (reuse PhraseValidator)
→ store entry (BackronymEntry)
→ if len(entries) == 5: trigger voting phase
→ else: spawn AI to fill to 5 after 2 minutes
```

**c. Voting phase**

* AI immediately submits enough entries to reach 5 after 2 minutes.
* When 5 exist → mark set `voting`.
* Shuffle entries per voter; return all five to anyone who pays 10f.
* Voting window = 2 minutes.

**d. Finalization**

* After 2 minutes from last human vote:

  * AI votes to ensure ≥5 total.
  * Count votes.
  * Non-participant wins = any voter who picked most-popular entry (20f each).
  * Remaining pool split pro-rata among creators.
  * 30% vault skim.
  * Write ledger txns; mark set `finalized`.

**e. Results view**

* `GET /ir/{set_id}/results` returns winners, votes, payouts.

That’s it — one vertical slice, no background workers required beyond the existing AI service.

---

### **3. Leverage Existing Infrastructure**

| QuipFlip Component                  | Reuse Strategy                                                                                        |
| ----------------------------------- | ----------------------------------------------------------------------------------------------------- |
| **FastAPI app**                     | Add `include_router(ir_routes, prefix="/api/ir")`                                                     |
| **AIService**                       | New prompt builder: `build_backronym_prompt(word)` and `build_vote_prompt(entries)`                   |
| **Validator**                       | Same local/remote phrase validator for per-word checks                                                |
| **Transactions**                    | Use same `TransactionService` (types: `ir_entry`, `ir_vote_entry`, `ir_payout`, `vault_contribution`) |
| **Wallet/Vault**                    | Identical; no schema changes                                                                          |
| **JWT/Auth**                        | Already reusable                                                                                      |
| **Frontend wallet, balance, toast** | No changes required                                                                                   |

---

### **4. Frontend MVP (Vite/React)**

Reusing 80% of your existing QuipFlip UI:

1. **New route:** `/backronym-battle`

2. **Step 1: Word screen**

   * Show tiles for random word (e.g., `F.R.O.G.`).
   * Input chips for each letter.
   * Button “Submit” (calls `/ir/{set_id}/submit`).
   * After submit, show “Waiting for others (or AI)...”.

3. **Step 2: Voting screen**

   * After 2 minutes or via poll `/ir/{set_id}/status`, show 5 entries randomized.
   * User pays 10f and chooses one.
   * Show small countdown “Voting ends in 2:00”.

4. **Step 3: Results screen**

   * Show 5 backronyms with vote % bars.
   * Highlight winner and your vote.
   * “+Xf” summary; vault contribution in tooltip.

5. **UI reuses:**

   * InitCoin counter
   * Toast system
   * Modals and button components
   * Theme colors from QuipFlip

6. **AI placeholders**: show a small 🤖 icon on AI entries.

---

### **5. AI Prompts for MVP**

**Generation Prompt:**

> “Generate 5 funny, coherent backronyms for the word {WORD}. Each backronym should contain {N} words, one per letter, all common English words. Format: each on a new line.”

**Voting Prompt:**

> “Given the word {WORD} and these 5 backronyms, choose the one that is most clever or meaningful. Return only the full backronym text.”

Use the same async OpenAI/Gemini wrappers you already have; log in `ai_metrics` with `game='ir'`.

---

### **6. Scheduler**

* You don’t need a new worker queue.
* Use the existing “AI backup” cycle pattern with reduced delay:

  * Run every minute.
  * Find sets where `status='open'` and `age > 2min` → AI fill to 5.
  * Find sets where `status='voting'` and `age > 2min` → AI fill votes and finalize.

---

### **7. Scope Cuts**

✅ MVP **includes**:

* Rapid rounds only
* AI entry + AI voting
* Wallet integration
* Result view with payouts
* Simple frontend loop
* Basic metrics

❌ MVP **defers**:

* Standard (human-first) mode
* Non-participant caps beyond 5 (hard-code 5)
* Observer gating (anyone can vote)
* Leaderboards
* Vault view (already exists globally)
* Feedback, quests, or achievements
* Admin dashboards

---

### **8. Deployment Checklist**

* Add same-origin routing for `/ir` on the Cloudflare host.
* Add `IR_ENABLED=true` env var.
* Add `AI_IR_MODEL=gpt-4o-mini` or equivalent.
* Migrate schema (2 tables only).
* Deploy backend to the Mac host.
* Deploy frontend branch `ir-mvp` behind the Cloudflare tunnel.
* Smoke test: one human + AI complete round end-to-end.

---

### **9. Timeline (if you start from current QuipFlip base)**

| Phase                              | Duration | Deliverable                              |
| ---------------------------------- | -------- | ---------------------------------------- |
| **Backend schema + services**      | 1–2 days | 2 models, 1 router, reuse AI + validator |
| **Frontend loop (3 screens)**      | 2–3 days | playable UX                              |
| **AI prompt tuning & payout math** | 1 day    | coherent AI output + correct InitCoin flow   |
| **Polish + deploy**                | 1 day    | MVP live                                 |

**≈ 1 working week total.**

---

### **10. Success Criteria for MVP**

* ✅ Human can enter 1 backronym and see round complete with AI players.
* ✅ Wallet balance correctly debits 100f, adds payout after result.
* ✅ AI fills to 5 entries and votes reliably within 2 minutes.
* ✅ Result screen shows vote breakdown and vault skim.
* ✅ No manual resets or admin triggers required.
