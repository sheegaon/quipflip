# Initial Reaction state machine

> Current implementation notes for the IR workstream.
>
> This page records the behavior the code now relies on. The explicit assignment-row
> migration described in the transition plan is still the eventual target; the current
> code keeps assignment implicit in the start/submit flow.

## Aggregates

| Aggregate | States | Owning command |
| --- | --- | --- |
| Backronym set | `open`, `voting`, `finalized` | `start_game`, `submit_backronym`, `submit_vote`, `finalize_set` |

## Set lifecycle

| State | Actor / public command | Owning backend command | Preconditions | Status / version predicate | Deadline / late behavior | Rows written | Ledger movement keys | Returned projection | Forbidden fields | Duplicate / concurrent / stale outcome | Reconnect projection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `open` | Player starts game, then submits a backronym | `start_game` / `submit_backronym` | Set exists or is created; backronym validates against the chosen word length | `BackronymSet.status == open`; entry uniqueness is DB-backed | No authoritative deadline on the open state; submission is the only charge point | `ir_backronym_sets`, `ir_backronym_entries`, `ir_transactions`, `ir_backronym_observer_guard` | `ir_backronym_entry` | Start response returns set id, word, mode, status. Submit response returns entry id, set id, status | Other players’ entry ids, vote ids, payout fields, internal queue state | Duplicate submit is blocked by set-entry uniqueness / service checks; stale open-set work is rejected by status checks | Reopening the page reconstructs the same open set and existing submitted entry state |
| `voting` | Player votes | `submit_vote` / `finalize_set` | Set is voting; entry exists; player has not already voted; non-participant eligibility passes | `BackronymSet.status == voting`; vote uniqueness is `player_id + set_id` | Standard mode resets `voting_finalized_at` to 30 minutes after the last human vote; rapid mode uses the rapid timer. Late commands after finalization are no-ops | `ir_backronym_votes`, `ir_transactions`, `ir_backronym_sets`, `ir_result_views` | `ir_vote_entry`, `ir_vote_payout`, `ir_creator_payout`, `ir_vault_contribution` | Vote response returns vote id and set id only; status view returns counts only | Other players’ vote ids, authorship of specific entries before finalization, payout breakdowns before finalization | Duplicate vote is rejected; stale finalizer is no-op; payout processing is idempotent by ledger key | Reconnect reconstructs the same voting set, counts, and deadlines from durable rows |
| `finalized` | Automatic finalization or result collection | `finalize_set` / `claim_result` | Voting is complete or a deadline command wins; result views are claimable | `BackronymSet.status == finalized` and `finalized_at` set | Late vote/submit commands are rejected; result claiming is read-only | `ir_transactions`, `ir_result_views`, `ir_backronym_sets` | Same as above; result-view claims are separate read-side rows | Finalized results and payout summaries only | Pre-finalization authorship, origin relationships, and vote ids remain hidden | Re-running finalization is a no-op; ledger keys prevent duplicate payouts | Reconnect restores finalized result state and claim status |

## Mutation callers

- `backend/routers/ir/game.py`: command
- `backend/services/ir/backronym_set_service.py`: command owner
- `backend/services/ir/vote_service.py`: command owner / validation
- `backend/services/ir/scoring_service.py`: command owner for payouts
- `backend/services/ir/result_view_service.py`: discovery + claim path
- `backend/services/ir/daily_bonus_service.py`: external-work / unrelated
- `backend/main.py` background cycles: discovery-only

