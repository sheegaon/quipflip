# Workstream C - QuipFlip Solo Hardening

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Make QuipFlip solo assignment, submission, voting, deadlines, scoring, and money
movement transactional, private, retry-safe, and recoverable after restart.

## Starting point

QuipFlip is the broadest and most complete game surface. Its highest-risk gaps are
prompt/copy queue authority, candidate selection outside the decisive transaction,
active-round races, timeout/refund idempotency, and protocol fields that may expose
stable internal relationships.

## Dependencies and boundaries

- Requires workstream A's deterministic and SQLite integration harness.
- Uses the shared invariants and command boundaries defined in workstream B.
- Party Mode is excluded and planned in workstream D.
- Preserve the economy and gameplay intent in
  [QF game rules](../quipflip/QF_GAME_RULES.md).

## Phase C0 - Contract and regression baseline

- [ ] Complete the QF solo state-machine and mutation inventory from B0.
- [ ] Map prompt, copy, vote, timeout, finalization, refund, and payout rules to
      existing tests and missing coverage.
- [ ] Capture regressions for concurrent prompt claims.
- [ ] Capture regressions for concurrent copy claims.
- [ ] Capture regressions for concurrent vote claims and duplicate votes.
- [ ] Capture regressions for more than one active assignment per player.
- [ ] Capture regressions for queue/cache loss and process restart.
- [ ] Capture regressions for duplicate submission and stale finalization.
- [ ] Capture regressions for contributor vote exclusion.
- [ ] Capture regressions for duplicate refund and payout.

Gate:

- [ ] Each identified failure has a focused reproducible test before its behavior
      changes.

## Phase C1 - Pure QuipFlip rules

- [ ] Extract prompt and copy eligibility into pure functions.
- [ ] Extract copy discount/pricing into pure functions.
- [ ] Extract vote eligibility and contributor exclusion into pure functions.
- [ ] Extract scoring and tie behavior into pure functions.
- [ ] Extract prize-pool allocation into pure functions.
- [ ] Pass clock and seeded randomness explicitly.
- [ ] Add boundary, tie, zero-entry, insufficient-funds, and seeded property-style
      cases.
- [ ] Reconcile every discovered rule discrepancy with the canonical game rules.

Gate:

- [ ] Core eligibility, pricing, scoring, and payout rules run without FastAPI,
      SQLAlchemy, network access, or wall-clock time.

## Phase C2 - Transactional assignment

- [ ] Define the single prompt-assignment command.
- [ ] Define the single copy-assignment command.
- [ ] Select candidates and conditionally claim them inside the decisive
      transaction.
- [ ] Enforce one active QF solo assignment per player in the database.
- [ ] Atomically write charge, ledger entry, assignment, and durable queue state.
- [ ] Derive copy availability and discounts from durable rows.
- [ ] Return explicit outcomes for no work, insufficient funds, duplicate command,
      and lost race.
- [ ] Add multi-connection claim tests with coordination disabled.
- [ ] Delete or demote queue mutation paths that can assign work independently.

Gate:

- [ ] Concurrent claim attempts produce one owner, one charge, and one active
      assignment.

## Phase C3 - Submission, voting, deadlines, and finalization

- [ ] Route prompt/copy submission through one conditional command per transition.
- [ ] Route vote submission through one command with transactional eligibility.
- [ ] Make timeout expiry compare expected status/version/deadline.
- [ ] Make refunds uniquely keyed and retry-safe.
- [ ] Make finalization stale-safe and the only prize-distribution path.
- [ ] Make payouts uniquely keyed and reconcile them with cached balances.
- [ ] Persist AI-fill intent before external work and reject stale AI results.
- [ ] Add duplicate, concurrent, late, stale, and restart tests for each command.

Gate:

- [ ] Repeated deadline and finalization commands cannot re-queue, refund, score, or
      pay twice.

## Phase C4 - Private protocol and reconnect

- [ ] Define explicit start, detail, dashboard, reconnect, vote, and result schemas.
- [ ] Replace canonical hidden lifecycle IDs with actor-scoped assignment tokens
      where required.
- [ ] Assert copy players cannot see the originating hidden prompt.
- [ ] Assert voters cannot identify the original entry before finalization.
- [ ] Assert authorship and contributor relationships remain hidden.
- [ ] Ensure reconnect restores the same assignment, submitted state, vote state,
      allowance, and deadline.
- [ ] Update the QF frontend to consume only the explicit projections.

Gate:

- [ ] Normal and reconnect flows expose no forbidden pre-finalization fields and do
      not reset active play.

## Phase C5 - Operations cleanup and smoke

- [ ] Convert `cleanup_orphaned_rounds.py` findings into regression tests.
- [ ] Convert `debug_copy_availability.py` findings into regression tests.
- [ ] Convert `fix_orphaned_captions.py` findings into regression tests.
- [ ] Move necessary repair tools to guarded `scripts/ops/` commands.
- [ ] Require backup, dry-run, bounded scope, and audit output for destructive
      repairs.
- [ ] Delete diagnostic scripts with no remaining operational purpose.
- [ ] Add a built-server solo smoke covering prompt, copy, vote, finalization, and
      balance reconciliation.
- [ ] Add restart and stale-command steps to the smoke or SQLite integration gate.

Gate:

- [ ] The built-server QF solo smoke and production-shaped SQLite lifecycle suite
      pass.

## Required verification

- [ ] Run QF pure-rule and lifecycle tests.
- [ ] Run multi-connection SQLite claim/finalization tests.
- [ ] Run disclosure and reconnect tests.
- [ ] Run ledger reconciliation tests.
- [ ] Build the QF frontend.
- [ ] Run the QF solo smoke.
- [ ] Obtain independent lifecycle, money, and disclosure reviews.

## Exit criteria

- [ ] Assignment and charging are one atomic operation.
- [ ] Queue loss and command retries do not alter ownership or money.
- [ ] Finalization is stale-safe and uniquely pays each logical movement.
- [ ] QF solo reconnect and response projections preserve state without disclosure.

## Non-goals

- Party Mode reliability work.
- Visual redesign of the QF client.
- Economy changes not required by the canonical game rules.
