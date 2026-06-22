# Workstream D - QuipFlip Party Mode

> **Document type:** Implementation plan
> **Status:** Active
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Make Party Mode a server-authoritative, deadline-driven, reconnect-safe
multi-client lifecycle with stale-command rejection and deterministic tests.

## Starting point

Party Mode has a separate backend and frontend surface. Current phase advancement
contains incompatible async/synchronous lock usage and lacks direct regression
coverage. In-flight branch intent exists in `party-refactor` and
`refactor-round-names`, but those branches are evidence to reconcile, not changes
to merge blindly.

## Dependencies and boundaries

- Requires workstream A's deterministic/fake-clock and built-server smoke support.
- Uses workstream B's lifecycle versions, conditional commands, and explicit
  projections.
- QF solo behavior belongs in workstream C.
- Preserve intended behavior from the
  [Party documentation](../quipflip/party/party_overview.md), resolving conflicts
  against running code and tests explicitly.

## Repository anchors and gotchas (verified 2026-06-22)

- **The branches are on the `gh-quipflip` remote, not `origin`.** This checkout's
  only remote is `gh-quipflip` (`https://github.com/sheegaon/quipflip.git`). Inspect
  with `git log --stat gh-quipflip/party-refactor` and
  `git log --stat gh-quipflip/refactor-round-names` (D0); there is no
  `origin/party-refactor`.
- **The broken-lock site is exact: `backend/services/qf/party_session_service.py:959`**
  uses `async with lock_client.lock(...)` against a synchronous `@contextmanager`
  (`backend/utils/lock_client.py`), which raises `AttributeError` whenever that path
  runs — which is why it has no working test today (roadmap finding 6). This is D1's
  "replace broken synchronous lock usage."
- **Party state and services are already substantial.** Models:
  `backend/models/qf/{party_session,party_participant,party_round,party_phraseset}.py`
  (`party_phraseset` already has `uq_party_phrasesets_session_phraseset`). Services:
  `backend/services/qf/{party_session_service,party_coordination_service,party_scoring_service,party_websocket_manager}.py`
  — these are the oversized boundaries D2 splits along command/projection/rule lines.
  Docs: `docs/quipflip/party/{architecture-overview,party_api,party_services,party_data_models_and_schemas,party_overview}.md`.
- **A leftover `backend/migrations/cleanup_party_tables.sql` exists** — confirm its
  status and whether it is still referenced during D0.
- **Existing coverage**: `tests/test_party_session_service.py` and `tests/party/`;
  reconcile rather than replace.
- Implements [ADR 0001](../decisions/0001-server-authoritative-lifecycle.md) and
  [ADR 0002](../decisions/0002-private-response-projection.md).

## Phase D0 - Reconcile intent and current ownership

- [ ] Inspect `party-refactor` without merging it.
- [ ] Inspect `refactor-round-names` without merging it.
- [ ] Record reusable intent, obsolete assumptions, and conflicts with current
      code.
- [ ] Complete the Party state/phase diagram with commands, actors, deadlines, and
      reconnect projections.
- [ ] Inventory REST, WebSocket, scheduler, AI-fill, admin, and startup mutation
      callers.
- [ ] Identify duplicated phase-advance logic and oversized service boundaries.
- [ ] Define participant identity and reconnection rules.

Gate:

- [ ] Every Party mutation maps to one intended command and every remote-branch
      idea has an explicit keep, adapt, or reject decision.

## Phase D1 - Phase/version and deadline model

- [ ] Add an authoritative phase and monotonic lifecycle version.
- [ ] Persist an authoritative deadline for every timed phase.
- [ ] Define valid command/phase/version combinations.
- [ ] Implement conditional phase advancement with one winner.
- [ ] Make duplicate and stale advancement explicit no-ops or typed conflicts.
- [ ] Replace broken synchronous lock usage in async paths.
- [ ] Ensure socket presence never advances or rewinds lifecycle state.
- [ ] Add database constraints for session membership and per-round assignment
      uniqueness.

Gate:

- [ ] Concurrent or repeated phase commands cannot skip, repeat, or rewind a phase.

## Phase D2 - Command ownership and durable orchestration

- [ ] Implement one command each for join, ready, start, submit, vote, advance,
      timeout, AI-fill acceptance, and finalization.
- [ ] Route REST endpoints through those commands.
- [ ] Route WebSocket messages through those commands or read-only projections.
- [ ] Route deadline discovery through those commands.
- [ ] Persist AI-fill intent and reject results for stale phases.
- [ ] Keep network/AI work outside write transactions.
- [ ] Publish notifications only after commit.
- [ ] Split services along command, projection, and pure-rule boundaries while
      migrating covered behavior.

Gate:

- [ ] No router, socket handler, or scheduler performs an independent Party state
      mutation.

## Phase D3 - Reconnect and private projections

- [ ] Define explicit host, participant, spectator, and reconnect projections.
- [ ] Restore the same participant identity after reconnect.
- [ ] Restore assignment, submission, counters, vote state, allowances, phase, and
      deadline.
- [ ] Keep disconnect/reconnect presence separate from lifecycle eligibility.
- [ ] Prevent duplicate joins and duplicate commands after reconnect.
- [ ] Assert hidden prompts, authorship, and original-entry identity remain private.
- [ ] Reject stale client phase/status updates.
- [ ] Update the Party frontend to render server deadlines and projections.

Gate:

- [ ] Disconnecting and reconnecting during every phase preserves authoritative
      state and does not disclose hidden information.

## Phase D4 - Deterministic lifecycle tests

- [ ] Add fake-clock tests for join and ready.
- [ ] Add fake-clock tests for host start and phase deadlines.
- [ ] Add tests for prompt/caption submission and voting.
- [ ] Add tests for disconnect and reconnect in every phase.
- [ ] Add tests for duplicate REST and WebSocket commands.
- [ ] Add tests for stale phase/version commands.
- [ ] Add tests for timeout, AI fills, stale AI results, and finalization.
- [ ] Add multi-client tests for simultaneous commands.
- [ ] Add restart recovery tests with socket state absent.

Gate:

- [ ] The full Party lifecycle passes without wall-clock sleeps or external AI.

## Phase D5 - Built-server and browser verification

- [ ] Add a multi-client built-server Party smoke through results.
- [ ] Include a mid-phase disconnect/reconnect.
- [ ] Include a stale phase command and verify rejection.
- [ ] Include a duplicate command and verify idempotent behavior.
- [ ] Verify host and participant views in an actual browser.
- [ ] Verify responsive interaction and socket recovery.
- [ ] Record bounded diagnostics without tokens or private player data.

Gate:

- [ ] A multi-client Party smoke completes through results with reconnect and stale
      command coverage.

## Required verification

- [ ] Run Party pure-rule and fake-clock tests.
- [ ] Run production-shaped SQLite concurrency tests.
- [ ] Build the QF frontend.
- [ ] Run the Party built-server smoke.
- [ ] Perform browser verification.
- [ ] Obtain independent lifecycle/WebSocket and disclosure reviews.

## Exit criteria

- [ ] Phase/version/deadline state is durable and server-authoritative.
- [ ] Reconnect restores rather than resets.
- [ ] One command owns each transition across REST, WebSocket, jobs, and AI.
- [ ] Multi-client smoke proves completion, reconnect, duplicate, and stale paths.

## Non-goals

- Blindly merging historical Party branches.
- Replacing Party Mode with a new room framework.
- A mechanical service rewrite without behavior-preserving tests.
