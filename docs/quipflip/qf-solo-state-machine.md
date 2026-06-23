# QuipFlip Solo State Machine

> **Document type:** Current implementation
> **Status:** Implemented baseline
> **Last verified:** 2026-06-23

This page records the authoritative QuipFlip solo lifecycle implemented by the
backend. The server owns assignment, deadlines, eligibility, money movement,
submission, voting, and finalization. In-memory queues are rebuildable discovery
accelerators; SQLite rows, constraints, lifecycle versions, and ledger keys are
the durable authority.

## Round lifecycle

| Round type | Start | Active command | Terminal states | Money |
| --- | --- | --- | --- | --- |
| Prompt | Select an unseen enabled prompt and create one active round | Submit, abandon, or expire | `submitted`, `abandoned`, `expired` | Entry keyed by round ID; abandon/expiry refund keyed by round ID |
| Copy | Select an eligible submitted prompt and claim copy slot 1 or 2 | Submit, flag, abandon, or expire | `submitted`, `abandoned`, `expired` | Entry keyed by copy round ID; refund keyed by round ID |
| Vote | Select an open non-contributor phraseset not previously voted by the player | Submit, abandon, expire, or phraseset finalization | `submitted`, `abandoned`, `expired` | Entry keyed by vote round ID; correct-vote payout keyed by vote ID |

Only one active round may exist per player. Copy slots are unique per prompt.
Those rules are enforced by partial unique indexes, not process locks.

## Phraseset lifecycle

```text
open -> closing -> finalized
  |                    ^
  +--------------------+
```

- A phraseset is created once two valid copy rounds are submitted.
- Vote threshold timestamps and server deadlines decide when it can finalize.
- Finalization is the only prize-distribution path.
- Contributor payouts use role-scoped keys:
  `qf:prize:<phraseset-id>:<role>:<wallet-type>`.
- An interrupted active vote round is refunded only while it remains inside its
  grace window. A vote already timed out forfeits its entry fee.
- Replaying an existing ledger key verifies player, amount, type, reference, and
  wallet before returning the original movement.

## Reconnect and disclosure

- `qf_player_data.active_round_id` is a reconnect pointer updated in the same
  transaction as the round.
- Assignment tokens are stable and unique.
- Vote choices are persisted per vote round so reconnect preserves order.
- Copy responses expose the submitted phrase to imitate, but not its originating
  prompt.
- Vote responses do not identify which choice is original before submission.
- Contributor identity and full relationships are exposed only by finalized
  result/history projections.

## Coordination

Prompt, copy, vote, and abandon writes do not hold synchronous process locks
across asynchronous database work. Queue rebuilding uses a local `asyncio.Lock`
only to avoid duplicate work; losing that lock or the queue does not change
durable ownership or ledger state.

## Verification anchors

- `tests/test_lifecycle_invariants.py`
- `tests/test_round_service.py`
- `tests/test_vote_service.py`
- `tests/test_qf_current_round.py`
- `tests/test_copy_availability_regression.py`
- `tests/test_flagging_cache_invalidation.py`
- `tests/sqlite_integration/test_production_sqlite.py`
