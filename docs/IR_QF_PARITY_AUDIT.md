# IR vs. Quipflip Backend Parity Audit

## Brainstorm: Additional parity hotspots
These are the comparison buckets that still merit scrutiny beyond the already closed gaps:

1. **Lifecycle payouts** – verify that Initial Reaction (IR) finalization triggers the same scoring + ledger writes that Quipflip’s `VoteService` performs when a phraseset closes.
2. **Prize-pool persistence** – confirm IR’s set service actually maintains `total_pool`, `vote_contributions`, and other accounting columns promised by the data-model doc (Quipflip mutates these on every vote).
3. **Queue durability** – ensure the IR queues that drive entry/voting priorities are as durable and multi-process-safe as the Redis-backed Quipflip queues.
4. **Stats/leaderboard math** – double-check that IR statistics aggregate the same transaction types Quipflip tracks so earnings/expenses and leaderboards stay accurate.
5. **Daily bonus atomicity** – compare IR’s daily bonus flow with Quipflip’s to make sure the “claimed” flag and the wallet credit can’t get out of sync.

## Detailed findings
### 1. Payouts are never triggered for finalized IR sets
* `IRBackronymSetService.finalize_set` only flips the status/`finalized_at` timestamp and dequeues the set; it never calls into the scoring/ledger layer.【F:backend/services/ir/ir_backronym_set_service.py†L318-L345】
* `IRScoringService.process_payouts` exists and would create the creator/non‑participant transactions, but nothing invokes it (the router only calls `get_payout_summary` for read-only display).【F:backend/services/ir/ir_scoring_service.py†L183-L258】【F:backend/routers/ir.py†L900-L925】
* In contrast, Quipflip’s `_finalize_phraseset` immediately calculates payouts, creates wallet/vault transactions through `TransactionService`, and commits the results as part of finalization.【F:backend/services/vote_service.py†L870-L994】

**Impact:** IR players never receive InitCoin payouts after a set finalizes, so balances and vault standings will remain frozen despite the vote/entry costs being debited.

**Status (2024-03-28):** Fixed. `IRBackronymSetService.finalize_set` now calculates payouts, updates the persisted pool columns, and immediately calls `IRScoringService.process_payouts` so creator/non-participant rewards hit the ledger when the set locks.【F:backend/services/ir/ir_backronym_set_service.py†L128-L205】

### 2. Prize-pool columns on `ir_backronym_sets` stay at zero
* The data-model spec explicitly calls for `total_pool`, `non_participant_payouts_paid`, and `creator_final_pool` to be persisted on finalize for auditing.【F:docs/IR_DATA_MODELS.md†L180-L213】
* `IRBackronymSetService.add_entry`/`add_vote` only touch `entry_count`, `vote_count`, and `non_participant_vote_count`; they never adjust `total_pool`, `vote_contributions`, or `non_participant_payouts_paid`. Those fields therefore remain their default zero values even after paid entries/votes happen.【F:backend/services/ir/ir_backronym_set_service.py†L135-L199】【F:backend/services/ir/ir_backronym_set_service.py†L236-L316】
* Quipflip updates `phraseset.total_pool`, `vote_contributions`, and `vote_payouts_paid` every time a vote is processed, so downstream views and audits can trust what’s stored in the DB.【F:backend/services/vote_service.py†L540-L581】

**Impact:** Any API or analytics consumer that reads `IRBackronymSet.total_pool` (e.g., `/sets/{id}/results`) will see `0`, making prize reporting inconsistent with the in-memory calculations.

**Status (2024-03-28):** Fixed. Human entries/votes now increment `total_pool`/`vote_contributions` when they are recorded, and finalization overwrites the persisted audit fields with the totals calculated by `IRScoringService` so downstream reads match the ledger.【F:backend/services/ir/ir_backronym_set_service.py†L95-L205】

### 3. IR queues are process-local lists, not shared infrastructure
* `IRQueueService` keeps `_entry_queue`/`_voting_queue` as module-level Python lists and only falls back to querying the DB if the list is empty.【F:backend/services/ir/ir_queue_service.py†L19-L190】
* Quipflip’s `QueueService` pushes/pops to Redis via `queue_client`, so every API worker participates in the same FIFO ordering and restarts don’t drop queued items.【F:backend/services/queue_service.py†L16-L90】

**Impact:** Each IR API instance has its own private queue ordering that is lost on restart, so multi-worker deployments will hand out sets inconsistently and the “entry priority” UX promised in the docs can’t be enforced.

**Status (2024-03-28):** Fixed. `IRQueueService` now uses the shared `queue_client` namespaces (`queue:ir:entry_sets`/`queue:ir:voting_sets`) with Redis-backed push/pop/remove helpers so every process participates in the same durable FIFO ordering.【F:backend/services/ir/ir_queue_service.py†L1-L210】

### 4. Player stats misclassify vote costs and understate expenses
* `IRStatisticsService.get_player_stats` only treats transactions of type `"ir_backronym_entry"` or `"ir_vote_cost"` as expenses.【F:backend/services/ir/ir_statistics_service.py†L81-L107】
* The ledger never emits `"ir_vote_cost"`; the vote debits are recorded as `IRTransactionService.VOTE_ENTRY`, i.e., `"ir_vote_entry"`.【F:backend/services/ir/transaction_service.py†L23-L80】【F:backend/routers/ir.py†L841-L868】

**Impact:** Non-participant voters will see `total_expenses`/`net_earnings` that omit their 10 IC vote fees, so the dashboard and leaderboards can’t match Quipflip’s accounting.

**Status (2024-03-28):** Fixed. The statistics service now references `IRTransactionService`’s canonical type constants so vote debits recorded as `ir_vote_entry` are treated as expenses in earnings math.【F:backend/services/ir/ir_statistics_service.py†L10-L71】

### 5. Daily bonus claims can record without paying the wallet
* `IRDailyBonusService.claim_bonus` inserts the `ir_daily_bonuses` row inside an `async with self.db.begin()` block and only afterwards calls `IRTransactionService.credit_wallet`. If the wallet credit raises (e.g., due to a transient DB issue), the `IRDailyBonus` row is already committed, so the player is marked as “claimed” without ever receiving funds.【F:backend/services/ir/ir_daily_bonus_service.py†L33-L69】
* Quipflip’s `PlayerService.claim_daily_bonus` creates the bonus row and immediately calls the transaction helper before committing, keeping the write atomic inside the same DB transaction.【F:backend/services/player_service.py†L150-L190】

**Impact:** A failed wallet credit leaves the system thinking the bonus was claimed, blocking retries and diverging ledgers between games.

**Status (2024-03-28):** Fixed. The bonus and wallet credit now occur inside the same DB transaction via `IRTransactionService.credit_wallet_in_transaction`, so either both writes land or both roll back, matching Quipflip’s atomic flow.【F:backend/services/ir/ir_daily_bonus_service.py†L27-L69】【F:backend/services/ir/transaction_service.py†L45-L119】
