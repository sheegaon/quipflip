# Phase 1: Backend Foundation

> **Goal**: Make submission endpoints party-aware so they automatically detect and handle party context without requiring separate endpoints.

## Overview

This phase fixes the most critical issue: normal round endpoints don't know about party mode, so submissions don't track progress or trigger phase advancement. We'll make the backend transparently handle both normal and party modes.

## Prerequisites

- Understanding of existing `RoundService` and `PartyCoordinationService`
- Access to modify backend models and routes
- Ability to run backend tests

## Objectives

1. ✅ Make `POST /rounds/{id}/submit` party-aware
2. ✅ Return party progress in submission responses
3. ✅ Ensure party-specific round start endpoints exist
4. ✅ Add database link from Round to PartyRound for fast lookups
5. ✅ Test both normal and party mode submissions

## Current Implementation Snapshot

- `Round.party_round_id` is present for fast party lookups (`backend/models/qf/round.py`).
- `POST /qf/rounds/{round_id}/submit` routes party rounds through `PartyCoordinationService`, returning `party_session_id` and `party_round_id` when a party link exists (`backend/routers/qf/rounds.py`).
- Party start endpoints for prompt/copy/vote live under `/qf/party/{session_id}/rounds/*` and include session progress fields to keep the UI in sync (`backend/routers/qf/party.py`).

---

## Implementation Steps

### Step 1: Enhance Round Model with Party Link

**File**: `backend/models/qf/round.py`

**Current State**: Round table has no reference to party mode

**Add** (after existing fields):

```python
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from backend.models.base import get_uuid_column

class Round(Base):
    __tablename__ = "qf_rounds"

    # ... existing fields ...

    # ADD THIS:
    party_round_id = get_uuid_column(nullable=True, index=True)
    # Note: Not a FK constraint to avoid circular dependencies
    # Instead, use application-level join via PartyRound.round_id
```

**Create Migration**:

```bash
cd backend
alembic revision -m "add party_round_id to rounds table"
```

**Migration File** (generated file in `alembic/versions/`):

```python
def upgrade():
    op.add_column('qf_rounds', sa.Column('party_round_id', sa.String(36), nullable=True))
    op.create_index('ix_qf_rounds_party_round_id', 'qf_rounds', ['party_round_id'])

def downgrade():
    op.drop_index('ix_qf_rounds_party_round_id', table_name='qf_rounds')
    op.drop_column('qf_rounds', 'party_round_id')
```

**Run Migration**:

```bash
alembic upgrade head
```

**Testing**:
```python
# Test that column exists
from backend.models.qf.round import Round
assert hasattr(Round, 'party_round_id')
```

---

### Step 2: Update PartySessionService to Set party_round_id

**File**: `backend/services/qf/party_session_service.py`

**Method**: `link_round_to_party()` (Line 1035-1080)

**Change**:

```python
async def link_round_to_party(
    self,
    session_id: UUID,
    player_id: UUID,
    round_id: UUID,
    round_type: str,
    phase: str,
) -> PartyRound:
    """Link a round to party session without incrementing progress counters."""

    participant = await self.get_participant(session_id, player_id)
    if not participant:
        raise PartyModeError(f"Player {player_id} not in session {session_id}")

    # Create party round link
    party_round = PartyRound(
        party_round_id=uuid.uuid4(),
        session_id=session_id,
        round_id=round_id,
        participant_id=participant.participant_id,
        round_type=round_type,
        phase=phase,
        created_at=datetime.now(UTC),
    )
    self.db.add(party_round)

    # NEW: Update the round record to reference party_round_id for fast lookup
    round_result = await self.db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()
    if round_obj:
        round_obj.party_round_id = party_round.party_round_id

    participant.last_activity_at = datetime.now(UTC)

    await self.db.commit()
    await self.db.refresh(party_round)

    logger.info(f"Linked {round_type} round {round_id} to party session {session_id}")
    return party_round
```

**Why**: When round is created, immediately stamp it with party_round_id for O(1) lookup later.

---

### Step 3: Make Submission Endpoints Party-Aware

**File**: `backend/routes/qf/rounds.py`

**Current State**: `POST /rounds/{round_id}/submit` calls normal RoundService

**Replace** the submit endpoint with party-aware version:

```python
from backend.services.qf.party_coordination_service import PartyCoordinationService
from backend.models.qf.party_round import PartyRound
from backend.models.qf.round import Round
from sqlalchemy import select

@router.post("/{round_id}/submit")
async def submit_phrase(
    round_id: UUID,
    request: SubmitPhraseRequest,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a phrase for a round.

    Automatically detects if this is a party round and routes accordingly.
    Works for both normal and party modes transparently.
    """

    # Get round to determine type
    round_result = await db.execute(
        select(Round).where(Round.round_id == round_id)
    )
    round_obj = round_result.scalar_one_or_none()
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")

    # Check if this is a party round
    is_party_round = round_obj.party_round_id is not None

    if is_party_round:
        # PARTY MODE: Use coordination service
        logger.info(f"Submitting party round {round_id} (party_round_id: {round_obj.party_round_id})")

        # Get party_round to find session_id
        party_round_result = await db.execute(
            select(PartyRound).where(PartyRound.party_round_id == round_obj.party_round_id)
        )
        party_round = party_round_result.scalar_one_or_none()
        if not party_round:
            raise HTTPException(status_code=500, detail="Party round metadata not found")

        # Route to party coordination service based on round type
        coordination_service = PartyCoordinationService(db)

        if round_obj.round_type == 'prompt':
            result = await coordination_service.submit_party_prompt(
                session_id=party_round.session_id,
                player=player,
                round_id=round_id,
                phrase=request.phrase
            )
        elif round_obj.round_type == 'copy':
            result = await coordination_service.submit_party_copy(
                session_id=party_round.session_id,
                player=player,
                round_id=round_id,
                phrase=request.phrase
            )
        else:
            raise HTTPException(status_code=400, detail=f"Invalid round type for submission: {round_obj.round_type}")

        # Enrich response with party metadata
        return {
            **result,
            "party_session_id": str(party_round.session_id),
            "party_round_id": str(party_round.party_round_id),
        }

    else:
        # NORMAL MODE: Use regular service
        logger.info(f"Submitting normal round {round_id}")
        round_service = RoundService(db)

        if round_obj.round_type == 'prompt':
            result = await round_service.submit_prompt_phrase(round_id, request.phrase, player)
        elif round_obj.round_type == 'copy':
            result = await round_service.submit_copy_phrase(round_id, request.phrase, player)
        else:
            raise HTTPException(status_code=400, detail=f"Invalid round type for submission: {round_obj.round_type}")

        return result
```

**Why**: Single endpoint handles both modes. Frontend doesn't need to know which mode it's in.

---

### Step 4: Make Vote Endpoint Party-Aware

**File**: `backend/routes/qf/votes.py`

**Current State**: `POST /phrasesets/{phraseset_id}/vote` calls VoteService

**Replace** with party-aware version:

```python
from backend.services.qf.party_coordination_service import PartyCoordinationService
from backend.models.qf.party_phraseset import PartyPhraseset

@router.post("/{phraseset_id}/vote")
async def submit_vote(
    phraseset_id: UUID,
    request: SubmitVoteRequest,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """
    Submit a vote for a phraseset.

    Automatically detects if this is a party phraseset and routes accordingly.
    """

    # Check if this phraseset is part of a party session
    party_phraseset_result = await db.execute(
        select(PartyPhraseset).where(PartyPhraseset.phraseset_id == phraseset_id)
    )
    party_phraseset = party_phraseset_result.scalar_one_or_none()

    if party_phraseset:
        # PARTY MODE: Find the player's vote round
        logger.info(f"Submitting party vote for phraseset {phraseset_id}")

        # Get the player's active vote round for this phraseset
        vote_round_result = await db.execute(
            select(Round)
            .where(Round.player_id == player.player_id)
            .where(Round.round_type == 'vote')
            .where(Round.phraseset_id == phraseset_id)
            .where(Round.status == 'active')
        )
        vote_round = vote_round_result.scalar_one_or_none()
        if not vote_round:
            raise HTTPException(status_code=404, detail="No active vote round found for this phraseset")

        # Use party coordination service
        coordination_service = PartyCoordinationService(db)
        result = await coordination_service.submit_party_vote(
            session_id=party_phraseset.session_id,
            player=player,
            round_id=vote_round.round_id,
            phraseset_id=phraseset_id,
            phrase=request.phrase
        )

        return {
            **result,
            "party_session_id": str(party_phraseset.session_id),
        }

    else:
        # NORMAL MODE: Use regular service
        logger.info(f"Submitting normal vote for phraseset {phraseset_id}")
        vote_service = VoteService(db)
        result = await vote_service.submit_vote(
            player=player,
            phraseset_id=phraseset_id,
            chosen_phrase=request.phrase
        )
        return result
```

---

### Step 5: Verify Party Round Start Endpoints Exist

**File**: `backend/routes/qf/party.py`

**Check** that these endpoints exist (they should from original implementation):

```python
@router.post("/{session_id}/rounds/prompt")
async def start_party_prompt_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """Start a prompt round within party session."""
    coordination_service = PartyCoordinationService(db)
    transaction_service = TransactionService(db)

    round_obj, party_round_id = await coordination_service.start_party_prompt_round(
        session_id=session_id,
        player=player,
        transaction_service=transaction_service
    )

    return {
        "round_id": str(round_obj.round_id),
        "party_round_id": str(party_round_id),
        "round_type": "prompt",
        "prompt_text": round_obj.prompt_text,
        "expires_at": round_obj.expires_at.isoformat(),
        "cost": round_obj.cost,
        "status": round_obj.status,
    }

@router.post("/{session_id}/rounds/copy")
async def start_party_copy_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """Start a copy round within party session."""
    # Similar implementation...

@router.post("/{session_id}/rounds/vote")
async def start_party_vote_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """Start a vote round within party session."""
    # Similar implementation...
```

**If missing**: Add these endpoints. They should delegate to `PartyCoordinationService`.

---

## Testing

### Unit Tests

**File**: `backend/tests/party/test_party_aware_submissions.py` (new file)

```python
import pytest
from uuid import uuid4
from backend.models.qf.round import Round
from backend.models.qf.party_round import PartyRound
from backend.services.qf.party_coordination_service import PartyCoordinationService

@pytest.mark.asyncio
async def test_normal_submission_without_party_context(db, player, round_service):
    """Verify normal submissions still work when not in party mode."""
    # Create normal round
    round_obj = await round_service.start_prompt_round(player, transaction_service)
    assert round_obj.party_round_id is None

    # Submit phrase
    result = await round_service.submit_prompt_phrase(round_obj.round_id, "test phrase", player)
    assert result['success'] is True

    # Verify no party metadata in response
    assert 'party_session_id' not in result

@pytest.mark.asyncio
async def test_party_submission_increments_progress(db, party_session, player):
    """Verify party submissions increment participant progress."""
    coordination_service = PartyCoordinationService(db)

    # Start party prompt round
    round_obj, party_round_id = await coordination_service.start_party_prompt_round(
        session_id=party_session.session_id,
        player=player,
        transaction_service=transaction_service
    )

    # Verify party_round_id is set
    assert round_obj.party_round_id == party_round_id

    # Submit phrase
    result = await coordination_service.submit_party_prompt(
        session_id=party_session.session_id,
        player=player,
        round_id=round_obj.round_id,
        phrase="test phrase"
    )

    # Verify progress incremented
    participant = await party_session_service.get_participant(party_session.session_id, player.player_id)
    assert participant.prompts_submitted == 1

@pytest.mark.asyncio
async def test_party_phase_advancement_automatic(db, party_session, players):
    """Verify phase advances when all players submit."""
    # All players submit prompts
    for player in players:
        # Start and submit prompt round
        round_obj, _ = await coordination_service.start_party_prompt_round(...)
        await coordination_service.submit_party_prompt(...)

    # Verify phase advanced to COPY
    session = await party_session_service.get_session_by_id(party_session.session_id)
    assert session.current_phase == 'COPY'
```

### Integration Tests

**Test Scenario 1: Normal Mode Still Works**

```bash
# Create normal player
POST /auth/register { username: "normal_user", ... }

# Start normal prompt round
POST /rounds/prompt/start
→ { round_id: "abc123", ... }

# Submit phrase (no party metadata)
POST /rounds/abc123/submit { phrase: "test" }
→ { success: true }

# Verify no party fields in response
assert response.party_session_id is None
```

**Test Scenario 2: Party Mode Progress Tracking**

```bash
# Create party session
POST /party/create
→ { session_id: "party123", party_code: "ABC1234" }

# Join party
POST /party/join { party_code: "ABC1234" }

# Start session
POST /party/party123/start

# Start party prompt round
POST /party/party123/rounds/prompt
→ { round_id: "round456", party_round_id: "pr789", ... }

# Submit phrase (should auto-detect party context)
POST /rounds/round456/submit { phrase: "test" }
→ { success: true, party_session_id: "party123", ... }

# Verify progress incremented
GET /party/party123/status
→ { participants: [{ prompts_submitted: 1, prompts_required: 1 }] }
```

**Test Scenario 3: Phase Advancement**

```bash
# Setup: Party session with 2 players, each needs 1 prompt

# Player 1 submits
POST /rounds/{round1}/submit { phrase: "p1" }

# Check phase (should still be PROMPT)
GET /party/{session}/status
→ { current_phase: "PROMPT" }

# Player 2 submits (last player)
POST /rounds/{round2}/submit { phrase: "p2" }

# Check phase (should now be COPY)
GET /party/{session}/status
→ { current_phase: "COPY" }

# Verify WebSocket broadcast was sent
assert ws_events contains { type: "phase_transition", new_phase: "COPY" }
```

---

## Rollback Plan

If issues arise:

### Quick Rollback (Disable Feature)

Add feature flag:

```python
# backend/config.py
PARTY_AWARE_SUBMISSIONS = os.getenv('PARTY_AWARE_SUBMISSIONS', 'false').lower() == 'true'

# In rounds.py
if PARTY_AWARE_SUBMISSIONS and is_party_round:
    # Use party service
else:
    # Use normal service (always)
```

Set `PARTY_AWARE_SUBMISSIONS=false` in environment to disable.

### Database Rollback

```bash
alembic downgrade -1  # Removes party_round_id column
```

### Code Rollback

Revert commits:
```bash
git revert <commit-hash>  # Revert submission endpoint changes
```

---

## Troubleshooting

### Issue: Submissions fail with "Party round metadata not found"

**Cause**: Round has `party_round_id` set but PartyRound record doesn't exist

**Fix**:
```python
# Check for orphaned records
SELECT r.round_id, r.party_round_id
FROM qf_rounds r
LEFT JOIN party_rounds pr ON r.party_round_id = pr.party_round_id
WHERE r.party_round_id IS NOT NULL AND pr.party_round_id IS NULL;

# Clean up orphaned records
UPDATE qf_rounds SET party_round_id = NULL WHERE party_round_id IN (...);
```

### Issue: Phase doesn't advance after all submissions

**Cause**: `can_advance_phase()` logic incorrect or WebSocket not broadcasting

**Debug**:
```python
# Add logging
logger.info(f"Checking phase advancement: {participants}")
logger.info(f"Required: {session.prompts_per_player}, Submitted: {[p.prompts_submitted for p in participants]}")
```

**Common causes**:
- AI players stuck in lobby
- Disconnected players counted as active
- Progress counter not incrementing

### Issue: Normal mode submissions broken

**Cause**: Missing check for `party_round_id` being None

**Fix**: Ensure condition is `round_obj.party_round_id is not None` not just truthy check

---

## Success Criteria

- [ ] Normal mode submissions work identically to before
- [ ] Party mode submissions increment progress counters
- [ ] Phase advancement happens automatically when all players done
- [ ] WebSocket broadcasts sent on submission and phase change
- [ ] All tests pass (normal + party modes)
- [ ] Migration runs cleanly on production database
- [ ] No performance regression (submission time <200ms)

---

## Next Steps

After completing Phase 1:

1. ✅ Verify all tests pass
2. ✅ Test manually with party session
3. ✅ Monitor logs for errors
4. ➡️ Proceed to [Phase 2: Frontend Consolidation](./phase-2-frontend-consolidation.md)

---

## Estimated Time

- **Database migration**: 30 minutes
- **Update link_round_to_party()**: 15 minutes
- **Refactor submission endpoints**: 2 hours
- **Write tests**: 1.5 hours
- **Testing and debugging**: 1 hour
- **Total**: **4-6 hours**
