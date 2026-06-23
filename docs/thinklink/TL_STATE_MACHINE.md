# ThinkLink state machine

> Current implementation notes for the TL workstream.

## Aggregates

| Aggregate | States | Owning command |
| --- | --- | --- |
| Round | `active`, `completed`, `abandoned` | `start_round`, `submit_guess`, `abandon_round`, `finalize_round` |
| Corpus answer | `active`, `inactive` | `admin/import`, `prune_corpus`, cluster maintenance |

## Round lifecycle

| State | Actor / public command | Owning backend command | Preconditions | Status / version predicate | Deadline / late behavior | Rows written | Ledger movement keys | Returned projection | Forbidden fields | Duplicate / concurrent / stale outcome | Reconnect projection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | Player starts a round | `start_round` | Player has enough wallet balance; a prompt with active answers exists | One active round per player via the active-round unique index | No authoritative deadline is exposed; the round ends by strikes, quit, or 100% coverage | `tl_round`, `tl_transaction`, `tl_player_data` | `round_entry` | Start response returns round id, prompt text, snapshot size, and snapshot weight | Prompt ids, answer embeddings, cluster weights, and other internal corpus details are not returned | Duplicate starts are blocked by the active-round constraint; restart restores the same active round | Reconnect restores round id, prompt text, snapshot counts, and current score state |
| `active` | Player submits a guess | `submit_guess` | Round belongs to player; guess validates; guess is on topic; self-similarity passes | Round must still be active when the owning command evaluates it | Zero-match valid guesses add a strike; 3 strikes ends the round; 100% coverage also ends the round | `tl_guess`, `tl_round`, `tl_answer` stats via finalization, `tl_transaction` via payout | No new ledger movement on strike-only guesses; payout keys are only written on completion | Submit-guess response returns match boolean, newly matched cluster count, coverage, strikes, and round status | No embeddings, answer ids, cluster ids, or weights are exposed | Duplicate or stale submissions are rejected by round state checks; stale finalizer is a no-op | Reconnect reconstructs strike count, coverage, and final status from durable rows |
| `completed` | Player quits or the round auto-completes | `abandon_round` / `finalize_round` | Round is active at command entry; quit now scores the current coverage instead of refunding a penalty | Conditional update on `status == active` makes completion stale-safe | Manual quit closes the round at current coverage with no 95-coin refund; 3 strikes also close the round; auto-complete is only at exactly 100% coverage | `tl_round`, `tl_guess`, `tl_answer`, `tl_transaction` | `round_payout_wallet`, `round_payout_vault`, `round_entry` | Round details return prompt text, snapshot size, final coverage, payout, and strike count | Prompt ids, answer embeddings, cluster ids, and snapshot weights are not returned | Duplicate completion attempts are no-ops; duplicate payouts are prevented by idempotency keys and the active-round guard | Reconnect restores final coverage, payout, and strike count |
| `abandoned` | Legacy terminal state | `abandon_round` | Historic rows may still carry this state | No new code path should produce it | Deprecated; current quit flow completes the round instead | Legacy only | Legacy only | Legacy detail rows only | Same privacy rules as above | Legacy stale rows are read-only | Reconnect reads legacy rows as completed history |

## Match threshold decisions

- Match boundary: `cosine_similarity > 0.55`
- Self-similarity rejection: `>= 0.80`
- Auto-complete: exactly 100% coverage
- Manual quit: current coverage, no refund

## Mutation callers

- `backend/routers/tl/rounds.py`: command
- `backend/services/tl/round_service.py`: command owner
- `backend/services/tl/scoring_service.py`: command owner for completion and payout
- `backend/services/tl/matching_service.py`: pure matching helper
- `backend/services/tl/clustering_service.py`: corpus maintenance / admin path
- `backend/services/tl/prompt_service.py`: discovery-only snapshot source
- `frontend/tl/src/pages/*`: projections only

