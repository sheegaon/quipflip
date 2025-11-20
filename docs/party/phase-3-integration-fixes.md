# Phase 3: Integration Fixes

> **Goal**: Fix PartyGame.tsx and round pages to call correct party-specific endpoints, ensuring rounds are properly linked to party sessions.

## Overview

This is the critical integration phase that connects the backend (Phase 1) with frontend hooks (Phase 2). Currently, PartyGame.tsx calls normal round endpoints (`POST /rounds/prompt/start`) instead of party-specific ones (`POST /party/{sessionId}/rounds/prompt`), which means rounds aren't linked to party sessions and progress isn't tracked.

## Prerequisites

- Phase 1 complete (party-aware backend)
- Phase 2 complete (frontend hooks created)
- Understanding of PartyGame orchestration flow
- Access to frontend API client

## Objectives

1. ✅ Add party-specific round start methods to API client
2. ✅ Fix PartyGame.tsx to use party endpoints
3. ✅ Verify round pages use submission endpoints correctly
4. ✅ Remove manual progress tracking attempts
5. ✅ Test end-to-end party mode flow

---

## Implementation Steps

### Step 1: Add Party Round Start Methods to API Client

**File**: `qf_frontend/src/api/client.ts`

**Check** if these methods exist. If not, **add**:

```typescript
class APIClient {
  // ... existing methods ...

  /**
   * Start a prompt round within a party session.
   *
   * @param sessionId - Party session ID
   * @returns Round data with party metadata
   */
  async startPartyPromptRound(sessionId: string): Promise<{
    round_id: string;
    party_round_id: string;
    round_type: 'prompt';
    prompt_text: string;
    expires_at: string;
    cost: number;
    status: string;
  }> {
    const response = await this.axiosInstance.post(
      `/party/${sessionId}/rounds/prompt`
    );
    return response.data;
  }

  /**
   * Start a copy round within a party session.
   *
   * @param sessionId - Party session ID
   * @returns Round data with party metadata
   */
  async startPartyCopyRound(sessionId: string): Promise<{
    round_id: string;
    party_round_id: string;
    round_type: 'copy';
    original_phrase: string;
    prompt_round_id: string;
    expires_at: string;
    cost: number;
    status: string;
  }> {
    const response = await this.axiosInstance.post(
      `/party/${sessionId}/rounds/copy`
    );
    return response.data;
  }

  /**
   * Start a vote round within a party session.
   *
   * @param sessionId - Party session ID
   * @returns Round data with party metadata
   */
  async startPartyVoteRound(sessionId: string): Promise<{
    round_id: string;
    party_round_id: string;
    round_type: 'vote';
    phraseset_id: string;
    prompt_text: string;
    phrases: string[];
    expires_at: string;
    cost: number;
    status: string;
  }> {
    const response = await this.axiosInstance.post(
      `/party/${sessionId}/rounds/vote`
    );
    return response.data;
  }
}

export default new APIClient();
```

**Why**: Provides type-safe methods for party round starting.

---

### Step 2: Fix PartyGame.tsx to Use Party Endpoints

**File**: `qf_frontend/src/pages/PartyGame.tsx`

**Current Issue** (Lines 53-74): Uses GameContext methods which call normal endpoints

**Remove** GameContext round starters from destructuring (Line 18):

```typescript
// OLD:
const { startPromptRound, startCopyRound, startVoteRound } = gameActions;

// NEW: (remove these, we won't use them in party mode)
// Don't import these at all
```

**Replace** round starting logic (Lines 53-74):

```typescript
// OLD:
if (step === 'copy') {
  if (gameState.activeRound?.round_type !== 'copy') {
    await startCopyRound();  // WRONG: Normal endpoint
  }
  navigate('/copy', { replace: true });
  return;
}

// NEW:
if (step === 'copy') {
  try {
    const roundData = await apiClient.startPartyCopyRound(sessionId);

    // Update GameContext with the new round data
    // This ensures activeRound state is in sync
    gameActions.updateActiveRound({
      round_type: 'copy',
      round_id: roundData.round_id,
      expires_at: roundData.expires_at,
      state: {
        round_id: roundData.round_id,
        original_phrase: roundData.original_phrase,
        prompt_round_id: roundData.prompt_round_id,
        expires_at: roundData.expires_at,
        cost: roundData.cost,
        status: roundData.status,
        discount_active: false, // or from roundData if backend provides it
      }
    });
  } catch (err) {
    const message = extractErrorMessage(err) || 'Failed to start copy round.';
    setError(message);
    return;
  }

  navigate('/copy', { replace: true });
  return;
}
```

**Complete Rewrite** of `beginPartyFlow()` function (Lines 29-81):

```typescript
const beginPartyFlow = async () => {
  setIsStarting(true);
  setError(null);

  try {
    const status = await apiClient.getPartySessionStatus(sessionId);
    const phase = status.current_phase.toLowerCase();

    // Check if already completed
    if (phase === 'results' || status.status === 'COMPLETED') {
      endPartyMode();
      navigate(`/party/results/${sessionId}`);
      return;
    }

    // Map server phase to client step
    const phaseToStepMap: Record<string, 'prompt' | 'copy' | 'vote'> = {
      prompt: 'prompt',
      copy: 'copy',
      vote: 'vote',
    };
    const step = phaseToStepMap[phase] ?? 'prompt';

    // Initialize party mode
    startPartyMode(sessionId, step);
    setCurrentStep(step);

    // Start the appropriate round using PARTY-SPECIFIC endpoints
    if (step === 'prompt') {
      const roundData = await apiClient.startPartyPromptRound(sessionId);
      gameActions.updateActiveRound({
        round_type: 'prompt',
        round_id: roundData.round_id,
        expires_at: roundData.expires_at,
        state: {
          round_id: roundData.round_id,
          prompt_text: roundData.prompt_text,
          expires_at: roundData.expires_at,
          cost: roundData.cost,
          status: roundData.status,
        }
      });
      navigate('/prompt', { replace: true });
    } else if (step === 'copy') {
      const roundData = await apiClient.startPartyCopyRound(sessionId);
      gameActions.updateActiveRound({
        round_type: 'copy',
        round_id: roundData.round_id,
        expires_at: roundData.expires_at,
        state: {
          round_id: roundData.round_id,
          original_phrase: roundData.original_phrase,
          prompt_round_id: roundData.prompt_round_id,
          expires_at: roundData.expires_at,
          cost: roundData.cost,
          status: roundData.status,
          discount_active: false,
        }
      });
      navigate('/copy', { replace: true });
    } else if (step === 'vote') {
      const roundData = await apiClient.startPartyVoteRound(sessionId);
      gameActions.updateActiveRound({
        round_type: 'vote',
        round_id: roundData.round_id,
        expires_at: roundData.expires_at,
        state: {
          round_id: roundData.round_id,
          phraseset_id: roundData.phraseset_id,
          prompt_text: roundData.prompt_text,
          phrases: roundData.phrases,
          expires_at: roundData.expires_at,
          cost: roundData.cost,
          status: roundData.status,
        }
      });
      navigate('/vote', { replace: true });
    }
  } catch (err) {
    const message = extractErrorMessage(err) || 'Failed to start party round.';
    setError(message);
  } finally {
    setIsStarting(false);
  }
};
```

**Why This Fix Works**:
1. Calls correct party endpoints: `/party/{sessionId}/rounds/{type}`
2. Rounds are created with party_round_id set (from Phase 1 backend)
3. Progress tracking will work automatically when player submits
4. GameContext state stays in sync with backend

**Add** `updateActiveRound` method to GameContext if missing:

**File**: `qf_frontend/src/contexts/GameContext.tsx`

```typescript
// In GameContextProvider component, add action:

const updateActiveRound = useCallback((roundData: ActiveRound) => {
  setState(prev => ({
    ...prev,
    activeRound: roundData
  }));
}, []);

// Add to actions object:
const actions = useMemo(() => ({
  // ... existing actions
  updateActiveRound,
}), [/* dependencies */, updateActiveRound]);
```

---

### Step 3: Verify Round Pages Use Submission Endpoints Correctly

**Files**:
- `qf_frontend/src/pages/PromptRound.tsx`
- `qf_frontend/src/pages/CopyRound.tsx`
- `qf_frontend/src/pages/VoteRound.tsx`

**Check** submission logic in each page:

**PromptRound.tsx** (Line 213):
```typescript
await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);
```

**CopyRound.tsx** (Line 408):
```typescript
await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);
```

**VoteRound.tsx** (Line 121):
```typescript
const result = await apiClient.submitVote(roundData.phraseset_id, phrase);
```

**Verification**: These are **correct**! They use normal endpoints, which are now party-aware (from Phase 1). No changes needed here.

**Why**: Backend automatically detects party context and routes to party services.

---

### Step 4: Remove Manual Progress Tracking Attempts

**Search** for any code that tries to manually track party progress (there shouldn't be any, but double-check):

```bash
# Search for manual progress updates
grep -r "prompts_submitted" qf_frontend/src/pages/
grep -r "copies_submitted" qf_frontend/src/pages/
grep -r "votes_submitted" qf_frontend/src/pages/
```

**If found**: Remove them. Progress tracking is now automatic via backend.

**Example of code to remove** (if exists):
```typescript
// DELETE THIS if found:
const updatePartyProgress = async () => {
  await apiClient.updateProgress(sessionId, { prompts_submitted: 1 });
};
```

---

### Step 5: Update GameContext Types

**File**: `qf_frontend/src/contexts/GameContext.tsx`

**Ensure** `updateActiveRound` is in the types:

```typescript
interface GameActions {
  startPromptRound: () => Promise<void>;
  startCopyRound: () => Promise<void>;
  startVoteRound: () => Promise<void>;
  flagCopyRound: (roundId: string) => Promise<FlagCopyRoundResponse>;
  refreshDashboard: () => Promise<void>;
  fetchCopyHints: (roundId: string) => Promise<void>;
  // ADD THIS:
  updateActiveRound: (roundData: ActiveRound) => void;
}
```

---

## Testing

### End-to-End Party Mode Test

**Scenario**: Full party game from start to results

```bash
# 1. Setup
- Create party session (Player A)
- Join party (Player B)
- Both players ready
- Host starts session

# 2. Verify PROMPT phase
GET /party/{session_id}/status
→ { current_phase: 'PROMPT', ... }

# Navigate to /party/game/{session_id}
- Should call POST /party/{session_id}/rounds/prompt
- Should navigate to /prompt
- Check browser DevTools Network tab:
  ✓ POST /party/{session_id}/rounds/prompt (200 OK)
  ✓ Response includes { round_id, party_round_id, ... }

# Submit prompts (both players)
POST /rounds/{round_id}/submit { phrase: "..." }
- Check console logs for party awareness
- Should see progress increment in backend logs

# 3. Verify AUTO phase advancement to COPY
GET /party/{session_id}/status
→ { current_phase: 'COPY', ... }

# WebSocket should broadcast phase_transition event
- Frontend receives event
- PartyRoundModal updates UI

# 4. Navigate to /party/game/{session_id} again
- Should call POST /party/{session_id}/rounds/copy
- Should navigate to /copy
- Check Network tab:
  ✓ POST /party/{session_id}/rounds/copy (200 OK)

# Submit copies (both players)
POST /rounds/{round_id}/submit { phrase: "..." }
- Progress increments automatically

# 5. Verify AUTO phase advancement to VOTE
GET /party/{session_id}/status
→ { current_phase: 'VOTE', ... }

# 6. Navigate to /party/game/{session_id} again
- Should call POST /party/{session_id}/rounds/vote
- Should navigate to /vote

# Submit votes (both players)
POST /phrasesets/{phraseset_id}/vote { phrase: "..." }

# 7. Verify AUTO phase advancement to RESULTS
GET /party/{session_id}/status
→ { current_phase: 'RESULTS', ... }

# 8. Navigate to /party/results/{session_id}
GET /party/{session_id}/results
→ { rankings: [...], awards: {...}, ... }

# Verify results page displays correctly
✓ Player rankings shown
✓ Awards displayed
✓ Phraseset summaries listed
```

### Integration Tests

**Test 1: Round Linking**

```typescript
// After starting party prompt round
const round = await db.get(Round, round_id);
expect(round.party_round_id).not.toBeNull();

const partyRound = await db.get(PartyRound, round.party_round_id);
expect(partyRound.session_id).toBe(party_session.session_id);
```

**Test 2: Progress Tracking**

```typescript
// Before submission
const participant = await getParticipant(session_id, player_id);
expect(participant.prompts_submitted).toBe(0);

// Submit via normal endpoint
await apiClient.submitPhrase(round_id, 'test phrase');

// After submission
const updated = await getParticipant(session_id, player_id);
expect(updated.prompts_submitted).toBe(1);
```

**Test 3: Phase Advancement**

```typescript
// Setup: 2 players, each needs 1 prompt
const session = await createPartySession({ prompts_per_player: 1 });

// Player 1 submits
await submitPrompt(player1, session_id);
let status = await getSessionStatus(session_id);
expect(status.current_phase).toBe('PROMPT'); // Still in PROMPT

// Player 2 submits (last player)
await submitPrompt(player2, session_id);
status = await getSessionStatus(session_id);
expect(status.current_phase).toBe('COPY'); // Advanced to COPY
```

**Test 4: GameContext Sync**

```typescript
// In PartyGame.tsx test
render(<PartyGame />);

await waitFor(() => {
  expect(mockNavigate).toHaveBeenCalledWith('/prompt', { replace: true });
});

// Verify GameContext state
const { result } = renderHook(() => useGame());
expect(result.current.state.activeRound?.round_type).toBe('prompt');
expect(result.current.state.activeRound?.round_id).toBeTruthy();
```

---

## Debugging Tips

### Issue: Rounds not linked to party

**Symptom**: Progress doesn't track, phase doesn't advance

**Check**:
```sql
-- Check if round has party_round_id
SELECT round_id, party_round_id FROM qf_rounds WHERE round_id = '<round_id>';

-- Should return:
-- round_id | party_round_id
-- abc123   | pr789  ← Should have value, not NULL
```

**Fix**: Verify Step 2 in Phase 1 was completed (link_round_to_party sets party_round_id)

### Issue: PartyGame navigates but round page shows loading forever

**Symptom**: Navigation works but round page stuck on LoadingSpinner

**Check**:
1. DevTools Network tab: Did `/party/{sessionId}/rounds/{type}` call succeed?
2. Console errors: Any 404 or 500 errors?
3. GameContext state: Is `activeRound` populated?

**Debug**:
```typescript
// Add logging in PartyGame.tsx
console.log('Round data received:', roundData);
console.log('Active round after update:', gameState.activeRound);
```

**Common causes**:
- `updateActiveRound` not implemented in GameContext
- Round data shape mismatch between API and frontend types
- Navigation happens before state update completes

### Issue: Phase doesn't advance after all players submit

**Symptom**: All players done but still in same phase

**Check backend logs**:
```
# Look for these logs
"Checking phase advancement: session_id=..."
"All participants done with PROMPT phase"
"Advanced session <id> to phase COPY"
```

**If missing**: Phase 1 submission endpoints not routing to party service

**Fix**:
```python
# In rounds.py, add debug logging
logger.info(f"Round {round_id} has party_round_id: {round_obj.party_round_id}")

# Verify this is TRUE for party rounds
```

---

## Rollback Plan

### Quick Rollback

**Revert PartyGame.tsx changes**:
```typescript
// Change back to:
const { startPromptRound, startCopyRound, startVoteRound } = gameActions;

if (step === 'copy') {
  if (gameState.activeRound?.round_type !== 'copy') {
    await startCopyRound(); // Back to normal endpoint
  }
  navigate('/copy', { replace: true });
}
```

**Why this works**: Frontend calls normal endpoints, which still work for non-party rounds

### Full Rollback

```bash
git revert <phase-3-commit>  # Revert PartyGame changes
git revert <api-client-commit>  # Revert API client additions
```

**Note**: Phase 1 and 2 changes are non-breaking, so they can stay

---

## Success Criteria

- [ ] API client has party round start methods
- [ ] PartyGame.tsx calls party-specific endpoints
- [ ] Rounds created have non-null `party_round_id`
- [ ] Submissions increment party progress
- [ ] Phase advancement happens automatically
- [ ] GameContext state syncs with backend
- [ ] WebSocket events broadcast correctly
- [ ] End-to-end party game completes successfully
- [ ] Normal mode still works (regression test)

---

## Common Pitfalls

1. **Forgetting to call `updateActiveRound`**: Round starts but state not synced → page shows loading
2. **Wrong endpoint path**: Typo in `/party/{sessionId}/rounds/...` → 404 errors
3. **Type mismatches**: Backend response shape doesn't match frontend types → runtime errors
4. **Missing party_round_id**: Phase 1 not complete → progress tracking fails
5. **Race conditions**: Navigation happens before state update → stale data displayed

---

## Next Steps

After completing Phase 3:

1. ✅ Test full party game end-to-end
2. ✅ Verify WebSocket events in browser DevTools
3. ✅ Check database for correct party_round linkage
4. ✅ Monitor backend logs for errors
5. ➡️ Proceed to [Phase 4: Data Model Enhancements](./phase-4-data-models.md)

---

## Estimated Time

- **Add API client methods**: 30 minutes
- **Fix PartyGame.tsx**: 1.5 hours
- **Add updateActiveRound to GameContext**: 20 minutes
- **Verification and testing**: 1 hour
- **Debugging**: 30 minutes (buffer)
- **Total**: **2-3 hours**
