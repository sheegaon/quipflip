# MemeMint state machine

> Current implementation notes for the MM workstream, reviewed 2026-06-23.

## Aggregates

| Aggregate | States | Owning command |
| --- | --- | --- |
| Vote round | `active`, `voted`, `captioned`, `closed`, `abandoned` | `start_vote_round`, `submit_vote`, `submit_caption`, `abandon_round` |
| Caption | `active`, `retired`, `removed` | `submit_caption`, `retire_caption` |

## Vote round lifecycle

| State | Actor / public command | Owning backend command | Preconditions | Status / version predicate | Deadline / late behavior | Rows written | Ledger movement keys | Returned projection | Forbidden fields | Duplicate / concurrent / stale outcome | Reconnect projection |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | Player starts a vote round | `start_vote_round` | Player has balance and no other active round | One active round per player; selected round row remains open until vote or abandon | No authoritative vote-round deadline is exposed; the UI timer is display-only | `mm_vote_rounds`, `mm_transactions` | `mm_round_entry` (existing MM ledger path) | Vote round response returns image, captions, and cost; authorship is hidden until reveal | `author_username`, circle membership, riff ancestry, internal ids not needed before vote | Duplicate start is blocked by the active-round uniqueness constraint; concurrent start races collapse to one row | Reconnect restores the same active round and caption list |
| `voted` | Player submits a vote | `submit_vote` | Round belongs to player; chosen caption is in the round; round not already voted | `chosen_caption_id` set; `result_finalized_at` set | Vote is one-way; late duplicate submissions are rejected | `mm_vote_rounds`, `mm_captions`, `mm_caption_seen`, `mm_transactions` | `mm_caption_payout_wallet`, `mm_caption_payout_vault`, `mm_first_vote_bonus`, `mm_local_crowd_favorite_bonus`, `mm_round_entry_refund` (system-only rounds) | Vote response now returns payout split, bonus flags, and revealed captions | Pre-vote authorship, kind, parent links, and circle membership are hidden from the ballot | Duplicate vote is rejected; first-voter bonus is DB-arbitrated; circle bonus suppression is evaluated at vote time | Reconnect after vote restores the revealed captions and chosen caption |
| `captioned` | Player submits a caption after voting | `MMCaptionService.submit_caption` | Round belongs to the player, vote exists, and the round has no caption claim | `mm_caption_submissions.round_id` is unique; the submission row is claimed before quota or fee movement | Caption submission only happens after successful vote | `mm_caption_submissions`, `mm_captions`, `mm_player_daily_states`, `mm_transactions` | Paid submissions use `mm_caption_submission_fee`, keyed by player/round/type; the daily free slot is claimed by conditional update | Caption response returns caption id, cost, free-slot usage, and new wallet balance | Authorship of other captions and pre-vote reveal data stay hidden | Duplicate/concurrent submission loses the unique round claim before consuming another free slot or fee | Round details restore `captioned` state plus the submitted caption id/text |
| `closed` | Round is finalized after vote or after a caption submission flow completes | `submit_vote`, `abandon_round`, cleanup/finalize commands | A voted round may close immediately; a caption round closes after its own completion | `result_finalized_at` or equivalent close marker | Late submissions are rejected | `mm_vote_rounds`, `mm_transactions` | None beyond the payout/fee ledger above | Closed round details may reveal authorship and rationale after vote | No internal ids are needed in closed projections beyond the round id | Stale close/finalize is no-op by idempotency and state checks | Reconnect restores the closed round state |
| `abandoned` | Legacy terminal state for already-started rounds | `abandon_round` | Player chooses to quit an active round | Current code now completes and scores the round instead of refunding a penalty | No historical 95-coin refund is granted; the round is scored at current state | `mm_vote_rounds`, `mm_transactions` | Same as `closed` | Abandon response is a simple completion acknowledgement | None beyond the round state itself | Duplicate abandon is rejected once the round is no longer active | Reconnect restores the completed state |

## Mutation callers

- `backend/routers/mm/rounds.py`: command
- `backend/services/mm/game_service.py`: command owner / discovery
- `backend/services/mm/vote_service.py`: command owner
- `backend/services/mm/caption_service.py`: command owner
- `backend/services/mm/circle_service.py`: command owner for circle membership
- `backend/services/mm/scoring_service.py`: command owner for payouts
- `backend/scripts/mm/*`: import / seed / admin tooling
- `frontend/mm/src/contexts/GameContext.tsx` and `frontend/mm/src/pages/*`: projections only

## Constraint evidence

- `f2a3b4c5d6e7_add_ir_assignments_mm_round_claim.py` adds the nullable historical
  `round_id` foreign key and unique round constraint. New accepted submissions
  always carry a round id; legacy/import rows may remain unscoped.
- `tests/test_mm_caption_round_claim.py` proves one accepted submission and one
  free-slot consumption when the same round is submitted twice.
