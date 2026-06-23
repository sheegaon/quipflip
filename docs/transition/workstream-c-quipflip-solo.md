# Workstream C - QuipFlip Solo Hardening

> **Document type:** Implementation plan
> **Status:** Implemented baseline; remaining blueprint items tracked below
> **Audience:** Maintainers and agents
> **Last reviewed:** 2026-06-22

## Objective

Make QuipFlip solo assignment, submission, voting, deadlines, scoring, and money
movement transactional, private, retry-safe, and recoverable after restart.

## Implementation assessment (2026-06-23)

The merged workstream established the schema constraints, versioned aggregates,
stable vote choices, AI stale-result guards, and ledger idempotency foundation.
The completion pass removed synchronous locks from solo start/abandon paths,
bound every copy charge to its round, added role-scoped prize payout keys,
validated idempotent ledger replays, and fixed availability-cache invalidation.
The current lifecycle is documented in
[`qf-solo-state-machine.md`](../quipflip/qf-solo-state-machine.md).

Unchecked items below remain architectural targets, not claims about missing
basic gameplay. In particular, command receipts are not yet the public API
contract, queue-backed copy discovery has not been fully replaced by a
database-only claim query, and the built-server/browser smoke described here is
not part of the deterministic gate.

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

## Repository anchors and gotchas (verified 2026-06-22)

- **The repair scripts live at the repository root, not `scripts/`**:
  `cleanup_orphaned_rounds.py`, `debug_copy_availability.py`,
  `fix_orphaned_captions.py` (plus `run_cleanup.py`, `cleanup_test_players.py`).
  [`docs/CLEANUP_SCRIPTS.md`](../CLEANUP_SCRIPTS.md) already inventories them,
  documents the safe backup/dry-run procedure, and names `scripts/ops/` as the
  target — C5 should update that doc, not duplicate it.
- **Some C0/C5 regressions already exist**:
  `tests/test_copy_availability_regression.py` (copy availability) and
  `tests/test_stale_ai_service.py` (stale AI results). Build on these instead of
  starting from zero.
- **The locks to make transactional are concrete**:
  `backend/services/qf/round_service.py` lines 92, 375, 869, 1170 and
  `backend/services/qf/vote_service.py:428` use the synchronous `lock_client.lock(...)`.
  These are the "candidate selection outside the decisive transaction" sites C2/C3
  must replace with conditional database updates.
- **Idempotent prize collection already has a model**
  (`backend/models/qf/result_view.py`, `uq_player_phraseset_result`). Key refunds and
  payouts (C3) the same way, and reconcile them against `qf_transactions`, which
  currently has no idempotency key.

## Implementation blueprint

This section turns the phase checklist into a concrete implementation shape. It is
deliberately specific about ownership and database invariants, but it does not make
unapproved economy changes. If implementation uncovers a conflict with
[`QF_GAME_RULES.md`](../quipflip/QF_GAME_RULES.md), stop and resolve the rule before
changing behavior.

### Target module layout

Keep the existing routers as transport adapters and split the oversized solo
services along command, rule, query, and projection boundaries:

```text
backend/
  models/qf/
    round.py
    phraseset.py
    vote.py
    transaction.py
    command_receipt.py          # retriable public command identity
    ai_job.py                   # durable external-work intent
    second_copy_offer.py        # actor-scoped offer after first copy
    vote_choice.py              # actor-scoped vote choices
  schemas/qf/
    commands.py                 # request IDs and command inputs
    assignments.py              # prompt/copy/vote start and reconnect DTOs
    projections.py              # availability, dashboard, result DTOs
  services/qf/
    rules/
      assignment.py             # prompt/copy/vote eligibility
      pricing.py                # copy price and second-copy price
      voting.py                 # contributor exclusion and finalization decision
      scoring.py                # points, ties, payout allocation, wallet/vault split
    commands/
      assign_prompt.py
      assign_copy.py
      assign_vote.py
      submit_prompt.py
      submit_copy.py
      submit_vote.py
      expire_round.py
      abandon_round.py
      finalize_phraseset.py
      accept_ai_result.py
    queries/
      assignment_candidates.py
      availability.py
      reconnect.py
    projections/
      assignments.py
      dashboard.py
      phrasesets.py
```

Do not mechanically move all of `round_service.py` and `vote_service.py` at once.
Introduce one command, route all callers to it, prove it, then delete the
superseded method. Party callers remain on the old paths until workstream D; new
solo commands must reject rows with `party_round_id IS NOT NULL`.

### State-machine inventory

The C0 deliverable is
`docs/quipflip/qf-solo-state-machine.md`. Its mutation table should include at
least the following command owners:

| Aggregate | From | Command | Decisive precondition | To | Money |
| --- | --- | --- | --- | --- | --- |
| player + round | no active solo round | `assign_prompt` | eligible unseen prompt, funds, outstanding cap | prompt `active` | keyed prompt entry |
| prompt round | `active` | `submit_prompt` | owner, version, deadline, valid phrase | `submitted` / `waiting_copies` | none |
| player + prompt | no active solo round | `assign_copy` | durable eligible slot, funds, cooldown | copy `active` | keyed copy entry |
| copy round | `active` | `submit_copy` | owner, version, deadline, valid distinct phrase | `submitted` | none; may create phraseset |
| player + phraseset | no active solo round | `assign_vote` | non-contributor, not voted, phraseset open | vote `active` | keyed vote entry |
| vote round + phraseset | `active` + open/closing | `submit_vote` | owner, version, deadline, valid choice, unique vote | vote `submitted` | keyed correct-vote payout |
| active round | `active` | `expire_round` | expected version and deadline passed | `expired` or `abandoned` | keyed refund |
| active round | `active` | `abandon_round` | owner and expected version | `abandoned` | keyed refund |
| phraseset | open/closing | `finalize_phraseset` | expected version and finalization rule true | `finalized` | three keyed contributor payouts |
| durable AI job | pending/running | `accept_ai_result` | expected target version and eligibility still true | applied/stale/failed | same human command path |

Inventory these current mutation callers and map each to the owner above:

- `backend/routers/qf/rounds.py`
- `backend/routers/qf/phrasesets.py`
- `backend/routers/qf/player.py` current-round timeout handling
- `backend/services/qf/round_service.py`
- `backend/services/qf/vote_service.py`
- `backend/services/qf/flagged_prompt_service.py`
- `backend/services/ai/qf_backup_orchestrator.py`
- `backend/services/ai/stale_ai_service.py`
- `backend/services/qf/cleanup_service.py`
- root repair scripts

The inventory must distinguish code behavior, canonical rule intent, and unresolved
questions. In particular, record that the current reconnect projection reshuffles
vote phrases and that current availability reads copy pricing from queue length.

Resolve these rule questions in C0 before the affected command lands:

- The canonical rules explicitly require timeout refunds for prompt and copy
  rounds, while current code also refunds expired vote rounds. Decide whether a
  vote timeout/abandon refunds, forfeits, or uses another rule.
- Decide whether an already-assigned vote remains submit-able if its phraseset
  otherwise becomes finalizable, or whether finalization cancels the assignment
  with a keyed refund. Do not silently strand a charged voter.
- Define the payout recipient policy for a contributor deleted before
  finalization. Current code skips the payout; the pool/accounting treatment needs
  an explicit rule.
- Confirm whether system AI actors pay entry costs and receive normal payouts in
  every backup/stale path.

### Database shape and migration order

Workstream B should first add the shared SQLite pragma hook and ledger idempotency
column. C then adds QF-specific lifecycle constraints in ordered migrations.

#### 1. Detect and repair existing invalid data

Before adding constraints, report:

- players with more than one active solo round;
- `qf_player_data.active_round_id` values that are missing, non-active, party, or
  owned by another player;
- active copy rounds beyond two live slots per prompt;
- duplicate submitted copies by one player outside the second-copy rule;
- phrasesets with missing or duplicate contributor rounds;
- duplicate votes;
- finalized phrasesets with missing or duplicate logical payouts;
- refunds without a resolved round and resolved rounds with duplicate refunds;
- wallet/vault values that do not reconcile with ledger history.

Repairs must be a separately reviewed, backup-required release operation. The
migration itself should abort with identifying counts rather than guess which
active assignment or payout is correct.

#### 2. Lifecycle columns and constraints

Add:

- `qf_rounds.version INTEGER NOT NULL DEFAULT 1`;
- `qf_rounds.assignment_token UUID NOT NULL`, unique and never reused;
- `qf_rounds.command_id UUID NULL` for the start command that created the round;
- `qf_rounds.copy_slot INTEGER NULL`, constrained to `1` or `2` for copy rounds;
- `qf_rounds.vote_order_seed` or persisted vote-choice rows so reconnect does not
  reshuffle;
- `qf_phrasesets.version INTEGER NOT NULL DEFAULT 1`;
- `qf_phrasesets.finalization_reason VARCHAR NULL`;
- `qf_phrasesets.payouts_completed_at DATETIME NULL`.

Backfill assignment tokens for every existing round. Backfill copy slots for live
and submitted copy rounds by creation order within each prompt; abort if more than
two rows require live slots or if the ordering is ambiguous.

Add partial unique indexes:

```sql
CREATE UNIQUE INDEX uq_qf_active_solo_round_per_player
ON qf_rounds(player_id)
WHERE status = 'active' AND party_round_id IS NULL;

CREATE UNIQUE INDEX uq_qf_live_copy_slot
ON qf_rounds(prompt_round_id, copy_slot)
WHERE round_type = 'copy'
  AND status IN ('active', 'submitted')
  AND party_round_id IS NULL;

CREATE UNIQUE INDEX uq_qf_solo_start_command
ON qf_rounds(player_id, command_id)
WHERE command_id IS NOT NULL AND party_round_id IS NULL;
```

Add check constraints tying round type to required fields where existing data
allows it. At minimum, reject invalid status values, invalid copy slots, negative
costs, negative pool counters, and `finalized` phrasesets without
`finalized_at`.

Keep `qf_player_data.active_round_id` during this workstream as a cached reconnect
pointer, but update it in the same transaction as the round. The partial unique
index is the ownership invariant. Add a reconciliation query that repairs only
unambiguous pointer drift.

#### 3. Command receipts

Create `qf_command_receipts` with:

- `player_id`;
- client-generated `command_id`;
- `command_type`;
- `aggregate_type` and `aggregate_id`;
- terminal `outcome`;
- `created_at`;
- unique `(player_id, command_id)`.

Public mutating requests accept a UUID `command_id`. A duplicate request returns
the existing typed outcome or current projection without repeating validation,
charging, refunding, or payout. Do not store secret or pre-finalization response
payloads in the receipt.

#### 4. Ledger idempotency

Add `idempotency_key` to every transaction table through workstream B's shared
model/migration and make it unique per game ledger. QF key formats are deterministic:

```text
qf:entry:<round-id>
qf:refund:<round-id>
qf:vote-payout:<vote-id>:wallet
qf:vote-payout:<vote-id>:vault
qf:prize:<phraseset-id>:<role>:wallet
qf:prize:<phraseset-id>:<role>:vault
qf:hint:<round-id>:<generation-id>
```

`TransactionService` must insert the ledger row and update the cached balance in
one caller-owned transaction. On duplicate key, load the existing row and verify
player, amount, type, reference, and wallet type match; a mismatch is an integrity
error, not an idempotent success.

#### 5. Actor-scoped choices and AI jobs

Create `qf_second_copy_offers` with player, source copy round, prompt round, opaque
offer token, expiry/consumption timestamps, and unique source copy round. Consuming
the offer must be conditional and actor-scoped.

Create `qf_vote_choices` keyed by `(round_id, position)` with an opaque
`choice_token`, displayed phrase, and internal role. The role never appears in a
pre-finalization response. Submit-vote accepts the assignment token and choice
token, not a phraseset ID plus phrase text.

Create `qf_ai_jobs` with job type, target aggregate, expected version, status,
attempt count, provider metadata, timestamps, and a unique active job per
`(job_type, target_id, expected_version)`. Persist the job before the network call.
The result command changes it to `applied`, `stale`, or `failed`.

### Pure rule APIs

Implement immutable input/output dataclasses or Pydantic-free typed records. The
functions must not import FastAPI, SQLAlchemy, services, settings singletons,
`datetime.now`, or module-level randomness.

```python
prompt_assignment_decision(player, outstanding_count, unseen_prompt_count, config, now)
copy_candidate_is_eligible(player_id, prompt, prior_copies, cooldowns, flagged, now)
copy_price(waiting_prompt_count, is_second_copy, config)
vote_candidate_is_eligible(player_id, contributor_ids, has_voted, phraseset_status)
vote_priority(phraseset, seeded_rank, config)
finalization_decision(phraseset_state, now, config)
score_votes(vote_roles, correct_points, incorrect_points)
allocate_prize_pool(pool, role_points)
split_wallet_vault(gross, entry_cost, vault_rate)
```

Rules return explicit reason codes. Preserve these intended details:

- copy discount activates only when the durable waiting count is greater than
  `copy_discount_threshold`;
- second copies cost `2 * copy_cost_normal` and never receive the discount;
- contributors cannot vote;
- zero total points split the pool evenly;
- proportional payouts floor division and leave the remainder in the phraseset;
- seeded ranking is deterministic for tests but does not expose the original role.

Add table-driven boundary cases for threshold minus one/equal/plus one, exact
deadline/grace cutoff, insufficient funds, one player owning both copy roles, zero
votes, ties, flooring remainder, and deleted contributors.

### Command contracts and transaction algorithms

Commands return typed outcomes such as `Applied`, `Duplicate`, `NoWork`,
`InsufficientFunds`, `LostRace`, `Expired`, `Stale`, and `Forbidden`. Routers map
these outcomes to stable HTTP statuses and error codes. Expected business outcomes
must not become generic 500 responses.

#### Prompt assignment

`assign_prompt(player_id, command_id, now, rng)`:

1. Begin a short write transaction.
2. Insert/read the command receipt.
3. Re-read moderation lock, wallet, active solo assignment, and outstanding prompt
   count.
4. Select unseen enabled prompts in deterministic order, then choose with the
   injected RNG.
5. Insert the active prompt round with assignment token, version, deadline, and
   command ID. The active-round partial index chooses the winner.
6. Conditionally decrement wallet and insert `qf:entry:<round-id>`.
7. Update the cached active pointer and prompt usage.
8. Commit, then invalidate caches and publish notifications.

Concurrent calls for the same player produce one round and one charge. A retry with
the same command ID returns the same assignment. A different command ID while a
round is active returns `AlreadyActive` with the reconnect projection.

#### Copy assignment

`assign_copy(player_id, command_id, now, rng, second_copy_offer_token=None)` uses
`BEGIN IMMEDIATE` because candidate selection depends on aggregate counts that are
not representable by one row CAS.

Inside the transaction:

1. Validate player state and command identity.
2. Count durable waiting prompts and calculate the price.
3. For a normal copy, select FIFO candidates that are submitted, unflagged, have
   no phraseset, have fewer than two live copy slots, are not owned by the actor,
   were not copied by the actor, and are outside the actor's cooldown.
4. Assign the lowest free `copy_slot` and insert the round. The live-slot and
   active-player indexes reject races.
5. For a second copy, consume an actor-scoped offer created by the first submission,
   verify the same player owns slot 1, and claim slot 2 at the fixed price.
6. Write entry charge, system contribution, active pointer, and receipt atomically.

Do not pop or remove queue entries in this command. Queue notifications may be
published after commit, but availability and price are derived from rows.

#### Vote assignment

`assign_vote(player_id, command_id, now, rng)`:

1. In one write transaction, validate funds, guest lockout, no active round, no
   prior vote, non-contributor status, and phraseset state.
2. Rank eligible phrasesets by closing priority, minimum-window priority, then a
   seeded random rank.
3. Insert the vote round and three persisted `qf_vote_choices`.
4. Charge the vote entry, set the active pointer, and commit.

The start and reconnect projections return the same choice order. They expose no
phraseset ID, contributor IDs, source round IDs, or original-role marker.

#### Prompt and copy submission

Phrase validation may require slow external work, so use a two-stage pattern:

1. Read the actor-owned assignment projection and validate syntax/similarity
   outside the write transaction.
2. Begin a short transaction and CAS:

```sql
UPDATE qf_rounds
SET status = 'submitted', version = version + 1, ...
WHERE round_id = :id
  AND player_id = :player_id
  AND status = 'active'
  AND version = :expected_version
  AND expires_at + :grace >= :now;
```

3. Re-check any database-dependent phrase conflicts inside the transaction.
4. Clear the active pointer and write activity.
5. For prompt submission, durable row state alone makes it copy-claimable.
6. For copy submission, update the claimed slot and create the phraseset with a
   unique `prompt_round_id` constraint when both slots are submitted.
7. Commit, then run quest/cache/notification work.

If external validation completed after the round changed, return `Stale`; never
apply the result to a newer state.

#### Vote submission

`submit_vote(player_id, assignment_token, choice_token, command_id, expected_version, now)`:

- CAS the active vote round before the grace cutoff;
- join the persisted choice to determine the internal role;
- revalidate phraseset status and contributor exclusion;
- insert the unique `(player_id, phraseset_id)` vote;
- atomically increment phraseset counters and timeline/version;
- write an idempotent correct-vote payout when applicable;
- clear the active pointer;
- call the same finalization command after commit if the updated state may be due.

If finalization wins between assignment and submission, the vote is stale and must
not be charged again or added to the pool. Resolve the charged assignment according
to the C0 vote-cancellation decision, with a uniquely keyed refund if cancellation
is the approved behavior.

#### Expiry, abandonment, and flagging

Use one `resolve_round` core transaction with reasons `timeout`, `abandon`, and
`flagged`. It must:

- CAS `active` plus expected version;
- require `deadline + grace < now` for timeout;
- calculate refund from the stored round cost;
- insert `qf:refund:<round-id>`;
- clear the active pointer;
- add copy cooldown with its existing unique key;
- make an abandoned copy slot claimable from durable state;
- update prompt flag state atomically for flagging.

Repeated calls return the existing resolution. Queue pushes are removed. The
reconnect/dashboard orchestration may discover an overdue assignment and invoke
this command before building the projection, but projection code must not implement
timeout mutation itself.

#### Finalization

`finalize_phraseset(phraseset_id, expected_version, now, reason)`:

1. Begin a short `BEGIN IMMEDIATE` transaction and re-read vote count, pool
   counters, contributors, costs, status, version, and finalization deadlines.
2. Recalculate the finalization decision and payouts from those transaction-local
   facts.
3. Insert each wallet/vault payout with deterministic role keys.
4. CAS open/closing plus expected version to `finalized`, set
   reason/timestamp/payout completion, update the prompt projection, and write one
   finalization activity.
5. Commit before quests, leaderboards, notifications, or WebSocket publication.

Only this command distributes the contributor pool. Availability reads,
result-screen reads, repair scripts, and AI services may request finalization but
may not pay contributors. A stale or repeated command observes the finalized state
and verifies the expected ledger rows without writing new ones.

### Read models and private protocol

Replace the current broad round DTOs with six explicit solo projections:

- `QFSoloAvailabilityResponse`;
- `QFPromptAssignmentResponse`;
- `QFCopyAssignmentResponse`;
- `QFVoteAssignmentResponse`;
- `QFSoloReconnectResponse`;
- finalized-only result/detail responses.

Start and reconnect should use the same assignment projection builder. Public
commands reference `assignment_token`, `choice_token`, and `command_id`; internal
round, prompt-round, phraseset, player, and contributor IDs stay server-side before
finalization.

Pre-finalization payload rules:

- prompt assignment: assignment token, prompt text, cost, deadline, version;
- copy assignment: assignment token, original quip phrase, cost, discount flag,
  deadline, version; no originating prompt or prompt-round ID;
- vote assignment: assignment token, prompt text, ordered choice tokens/text, cost,
  deadline, version; no original marker or phraseset ID;
- dashboard: availability, active assignment projection, balances, and aggregate
  counts only;
- reconnect: exactly the same assignment, choice ordering, submitted state,
  allowance, and deadline;
- notifications/WebSockets: opaque assignment/result references only.

The copy player may reveal the originating prompt only after their copy submission,
through a dedicated post-submission projection. Do not use the current general
`GET /rounds/{round_id}` authorization exception for this reveal.

The frontend changes are protocol migration, not a redesign:

- update `frontend/crowdcraft/src/api/types.ts` and `BaseApiClient.ts`;
- make `GameContext.tsx` hydrate from the reconnect projection;
- update `Dashboard.tsx`, `PromptRound.tsx`, `CopyRound.tsx`, and `VoteRound.tsx`
  to send command IDs and opaque tokens;
- remove client-side vote reshuffling and internal-ID routing;
- keep countdowns display-only and refresh the authoritative projection at expiry.

### AI and background work

Change backup and stale AI from direct ORM mutation to durable jobs:

1. A discovery cycle inserts a pending job with target ID and expected version.
2. A worker claims the job, commits, then calls the provider outside a transaction.
3. The result is submitted to `accept_ai_result`.
4. The command validates the job, target version, slot/vote eligibility, phrase,
   and current lifecycle state, then invokes the same submit command used by a
   human/system actor.
5. A late result becomes `stale`; it is recorded but does not create a copy, vote,
   phraseset, charge, payout, or queue mutation.

Remove direct `create_phraseset_if_ready` and direct vote mutation calls from
`qf_backup_orchestrator.py` and `stale_ai_service.py`. Due-row discovery and
finalization scans call command functions and tolerate `Stale`/`AlreadyApplied`.

### Test implementation

Add focused files rather than extending the current broad service tests indefinitely:

```text
tests/qf/rules/
  test_assignment_rules.py
  test_pricing_rules.py
  test_vote_rules.py
  test_scoring_rules.py
  test_payout_rules.py
tests/qf/commands/
  test_assign_prompt.py
  test_assign_copy.py
  test_assign_vote.py
  test_submit_prompt.py
  test_submit_copy.py
  test_submit_vote.py
  test_resolve_round.py
  test_finalize_phraseset.py
  test_ai_result.py
tests/qf/sqlite/
  test_concurrent_assignments.py
  test_concurrent_votes.py
  test_retry_idempotency.py
  test_restart_recovery.py
  test_ledger_reconciliation.py
tests/qf/protocol/
  test_assignment_disclosure.py
  test_dashboard_disclosure.py
  test_reconnect.py
  test_results_disclosure.py
```

The production-shaped SQLite tests use a temporary file, WAL,
`foreign_keys=ON`, `busy_timeout=5000`, `synchronous=FULL`, separate sessions, a
barrier to coordinate contenders, a fake clock, and coordination/queue clients
disabled. Required assertions include:

- two prompt starts: one active round and one entry charge;
- two copy claims for one remaining slot: one owner and one charge;
- second-copy claim racing a normal claim: one slot-2 owner;
- two vote starts for one player: one active round and one charge;
- duplicate/concurrent vote submit: one vote, one pool increment, one payout;
- active-pointer loss and queue/cache loss followed by restart: reconnect and
  availability remain correct;
- duplicate prompt/copy submission: one state transition and one phraseset;
- expiry racing submission: exactly one terminal outcome and at most one refund;
- repeated expiry/abandon/flag: one refund and one cooldown record;
- finalization racing a vote and another finalizer: one final state and one payout
  set;
- deleted contributor and zero-point cases follow the approved rule;
- stale AI result cannot fill a replaced slot or vote on a finalized set;
- every cached wallet/vault equals the configured opening balance plus ledger sums.

Protocol tests must use negative assertions for `round_id`, `prompt_round_id`,
`phraseset_id`, contributor IDs, authorship, original-role markers, and the hidden
originating prompt.

### Delivery sequence

Land this work as reviewable slices:

1. **C0 inventory and regression fixtures** — state machine, mutator/projection
   inventory, fake clock and concurrency fixture dependencies from A/B.
2. **C1 rules extraction** — no behavior change; route existing services through
   pure rules where safe.
3. **C2a schema and cleanup rehearsal** — versions, assignment tokens, copy slots,
   active partial indexes, command receipts, ledger keys.
4. **C2b prompt assignment** — command, router, reconnect projection, concurrent
   tests.
5. **C2c copy assignment** — durable FIFO/discount/slots, second-copy offer,
   queue-authority removal.
6. **C2d vote assignment** — durable priority and persisted private choice order.
7. **C3a submissions and resolution** — CAS submission, timeout, abandonment,
   flagging, keyed refunds.
8. **C3b voting and finalization** — transactional vote, keyed payouts, stale-safe
   finalizer, reconciliation.
9. **C3c AI jobs** — persisted intent and stale-result rejection.
10. **C4 protocol/frontend cutover** — opaque tokens, reconnect, disclosure tests,
    QF build and browser verification.
11. **C5 operations and smoke** — guarded repair tools, restart/stale steps,
    built-server lifecycle smoke.

Do not carry both old and new solo mutation paths after a slice lands. Temporary
compatibility is acceptable only at the router/protocol edge, with a named current
frontend consumer and a removal slice.

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
- [x] Enforce one active QF solo assignment per player in the database.
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
- [x] Make refunds uniquely keyed and retry-safe.
- [ ] Make finalization stale-safe and the only prize-distribution path.
- [x] Make payouts uniquely keyed and reconcile them with cached balances.
- [x] Persist AI-fill intent before external work and reject stale AI results.
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
