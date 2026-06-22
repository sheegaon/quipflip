# Workstream E - MemeMint, Initial Reaction, and ThinkLink

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Apply the verified lifecycle, database, money, privacy, and smoke-test guarantees
to Initial Reaction, MemeMint, and ThinkLink, then verify shared cross-game client
and session behavior.

## Starting point

MemeMint is the next most mature game after QuipFlip and carries caption/vote and
money-integrity risk. ThinkLink has a narrower core loop with scoring, matching,
and finalization risk. Initial Reaction is the smallest surface but currently has
the strongest build/model drift signal and thinnest regression coverage.

## Dependencies and boundaries

- Requires workstream A's backend, frontend, SQLite, and smoke gates.
- Uses workstream B's inventory format, command boundary, constraints, ledger
  idempotency, and private projections.
- Work proceeds in risk order: IR stabilization, MM integrity, TL finalization,
  then cross-game behavior.
- Canonical rules under `docs/<game>/` define intended gameplay and economy.

## Repository anchors and gotchas (verified 2026-06-22)

- **Concrete IR drift signals.** The shared client's prefix-strip regex at
  `frontend/crowdcraft/src/api/client.ts:76` is `replace(/\/(qf|mm|tl)(\/)?$/, '')` —
  it **omits `ir`**, so IR's root-API base resolution differs from the other three
  games. CI also has **no IR frontend lint/build job** while QF/MM/TL do
  (`.github/workflows/testing.yml`). Fix both in E1, paired with A5/A6.
- **Each game already has model scaffolding to extend.** IR/MM/TL each have a
  `transaction.py` plus uniqueness/result models — e.g.
  `uq_ir_result_view_player_set`, `uq_ir_entry_player_set`, `uq_ir_vote_player_set`;
  MM has `caption.py` and `vote_round.py`. E2/E3 add lifecycle versions and ledger
  idempotency keys on top, following workstream B.
- **Per-game tests are namespaced** `test_ir_*`, `test_mm_*`, `test_tl_*` and are
  already invoked individually in CI (`.github/workflows/testing.yml:69-71`). E0's
  per-game commands should formalize this split with markers.
- Implements [ADR 0001](../decisions/0001-server-authoritative-lifecycle.md),
  [0002](../decisions/0002-private-response-projection.md), and
  [0003](../decisions/0003-database-source-of-truth.md).

## Phase E0 - Common readiness

- [ ] Complete state-machine pages for IR, MM, and TL.
- [ ] Inventory each game's mutation callers and reconnect/read projections.
- [ ] Define forbidden pre-finalization fields per game.
- [ ] Map each game to pure-rule, deterministic lifecycle, SQLite concurrency,
      projection, and smoke coverage.
- [ ] Identify shared code changes and name all game consumers before editing the
      shared library.
- [ ] Establish per-game focused commands so one game's failures do not hide
      another's results.

Gate:

- [ ] Each game has a reviewed task breakdown with unresolved rule questions
      separated from implementation defects.

## Phase E1 - Initial Reaction stabilization

- [ ] Fix frontend TypeScript/model drift and add a regression for the mismatch.
- [ ] Reconcile API schemas, frontend types, ORM models, and canonical IR rules.
- [ ] Extract IR scoring/selection/eligibility rules into pure functions.
- [ ] Add database constraints for active rounds, submissions, and result
      collection.
- [ ] Route start, submit, timeout, and finalization through single commands.
- [ ] Add duplicate, concurrent, stale, and restart lifecycle tests.
- [ ] Add explicit response and reconnect schemas with forbidden-field assertions.
- [ ] Add a built-server IR smoke from start through results.

Gate:

- [ ] IR builds and passes pure-rule, SQLite lifecycle, privacy, reconnect, and
      built-server smoke gates.

## Phase E2 - MemeMint integrity

- [ ] Reconcile caption authorship, image/prompt ownership, vote eligibility, and
      economy rules with MM documentation.
- [ ] Extract caption eligibility, vote validity, scoring, pricing, and payout
      allocation into pure functions.
- [ ] Make caption claim/creation and any charge one atomic command.
- [ ] Make vote submission and eligibility one atomic command.
- [ ] Add uniqueness for active assignments, one vote per eligible relation, and
      ledger movement keys.
- [ ] Make timeout, refund, finalization, and payout commands stale-safe.
- [ ] Add negative disclosure assertions for caption authorship and original/source
      relationships.
- [ ] Verify circles and admin paths cannot bypass lifecycle ownership.
- [ ] Add duplicate, concurrent, stale, restart, and reconciliation tests.
- [ ] Add a built-server MM smoke through caption, vote, result, and balance update.

Gate:

- [ ] MM caption/vote ownership and every money movement remain correct under
      concurrent and repeated commands.

## Phase E3 - ThinkLink finalization

- [ ] Reconcile matching, scoring, tie, and finalization behavior with TL rules.
- [ ] Extract matching, scoring, eligibility, and payout rules into pure functions.
- [ ] Define one command for round assignment and response submission.
- [ ] Define one command for matching/result collection.
- [ ] Define one stale-safe finalization and payout command.
- [ ] Add constraints for active rounds, unique responses/matches, and result
      collection.
- [ ] Add duplicate, concurrent, late, stale, and restart tests.
- [ ] Add explicit play, history, result, admin, and reconnect projections.
- [ ] Assert no answer/match/authorship relationship leaks before finalization.
- [ ] Add a built-server TL smoke from assignment through finalized results.

Gate:

- [ ] TL matching, scoring, and finalization are deterministic, retry-safe, and
      database-enforced.

## Phase E4 - Cross-game auth and shared client

- [ ] Verify host/game scope is derived from validated server context.
- [ ] Verify one game's host cannot call another game's API prefix.
- [ ] Verify host-only cookies and logout/session behavior for all four hosts.
- [ ] Verify shared API errors do not expose internal models or cross-game data.
- [ ] Verify shared reconnect logic restores each game's durable state.
- [ ] Add contract tests for shared API and WebSocket clients.
- [ ] Build all four apps after every shared-library protocol change.
- [ ] Run one smoke loop per game against the same built backend.

Gate:

- [ ] Shared client and session behavior is consistent without allowing cross-game
      scope or data leakage.

## Required verification

- [ ] Run pure-rule tests for IR, MM, and TL.
- [ ] Run deterministic lifecycle and reconnect tests for each game.
- [ ] Run production-shaped SQLite concurrency/constraint tests for each game.
- [ ] Run money reconciliation tests for games with flipcoin movements.
- [ ] Build IR, MM, TL, and all consumers of changed shared code.
- [ ] Run one built-server smoke loop per game.
- [ ] Obtain independent lifecycle, money, disclosure, and shared-auth reviews as
      applicable.

## Exit criteria

- [ ] IR, MM, and TL each pass rules, lifecycle, privacy, reconnect, and smoke
      gates.
- [ ] MM and TL finalization cannot duplicate payouts or results.
- [ ] Shared code changes are verified across all four frontends.
- [ ] Cross-game host/session isolation has automated coverage.

## Non-goals

- Combining the three games into one lifecycle abstraction.
- Visual redesigns unrelated to reliability.
- Changing game rules to force implementation consistency.
