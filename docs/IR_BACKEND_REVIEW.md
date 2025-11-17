# Initial Reaction Backend Review

This document compares the current backend implementation to the intended Initial Reaction (IR) design described in `IR_DATA_MODELS.md`, `IR_GAME_RULES.md`, `IR_MVP_PLAN.md`, and `IR_UX_FLOW.md`. It highlights alignment gaps and proposes next steps.

## Observations vs. Intent

- **Voting capacity and lifecycle** – The services finalize a set after only five total votes and do not track non-participant vote limits beyond a simple counter, which conflicts with the intended "5 participants + up to 5 non-participants" model and minimum vote expectations. The data model also calls for additional pool bookkeeping (vote contributions, non-participant payouts) that is not persisted on the set today.【F:backend/services/ir/ir_backronym_set_service.py†L256-L329】【F:docs/IR_DATA_MODELS.md†L24-L75】
- **Observer gating for non-participants** – The spec introduces `BackronymObserverGuard` snapshots to restrict non-participant voting to accounts created before the first participant. The current `add_entry` flow never writes that guard, so eligibility cannot be enforced.【F:backend/services/ir/ir_backronym_set_service.py†L137-L180】【F:docs/IR_DATA_MODELS.md†L11-L76】
- **Payout computation and claim rules** – Finalize uses a simple rake plus pro-rata payout without requiring creators to vote, without persisting total pool fields, and without ResultView idempotency hooks. The spec requires a fixed pool assembly, early non-participant payouts, forfeiture to the vault when creators skip voting, and ResultView emission per creator.【F:backend/services/ir/ir_scoring_service.py†L40-L177】【F:docs/IR_DATA_MODELS.md†L180-L214】
- **AI and timeout handling** – While the data model and MVP plan describe rapid/standard timeouts, AI backfill, and vote timers, the implemented services only set timestamps and rely on manual polling for stalled sets; there is no automation to inject AI entries or votes or to finalize after timeouts.【F:backend/services/ir/ir_backronym_set_service.py†L137-L207】
- **Queue durability** – Queue state is kept in in-memory lists for entry and voting sets, so a process restart or multi-worker deployment would lose ordering guarantees, contrary to the persistent matchmaking expectations in the plans.【F:backend/services/ir/ir_queue_service.py†L14-L98】
- **Reward gating** – Vote eligibility does not enforce the participant-vote requirement or observer rule, and guest vote caps are only partially checked; this diverges from the UX and rules that expect capped, pre-qualified non-participant votes and mandatory creator participation before payout.【F:backend/services/ir/ir_vote_service.py†L34-L129】【F:docs/IR_DATA_MODELS.md†L170-L214】

## Recommended Next Steps

1. **Align vote lifecycle with design**
   - Persist `vote_contributions`, `non_participant_payouts_paid`, `creator_final_pool`, and track non-participant votes separately from participant counts.
   - Finalize after five participant votes plus up to five non-participant votes or after configured timeouts; preserve these totals on the set.
2. **Implement observer gating**
   - Create `BackronymObserverGuard` rows when the first entry arrives and enforce `created_at` gating inside `check_vote_eligibility` for non-participants.
3. **Enforce creator-vote requirement and forfeiture**
   - Require creators to cast votes before payout; mark `forfeited_to_vault` on entries and ledger vault transfers for non-voters.
   - Record `vote_share_pct`, `received_votes`, and `creator_final_pool` at finalize for replayability.
4. **Automate timeouts and AI backfill**
   - Add scheduled tasks/workers to move stalled sets forward by injecting AI entries/votes per rapid/standard timers and finalizing when timers expire.
5. **Harden queueing**
   - Move entry/voting queues to durable storage (e.g., DB tables) so matchmaking survives restarts and scales horizontally.
6. **Result claim flow**
   - Emit `ResultView` records per creator and gate `GET /sets/{set_id}/results` payouts on that claim path to match the UX plan.
