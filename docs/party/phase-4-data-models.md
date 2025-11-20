# Phase 4: Data Model Enhancements

> **Goal**: Enhance API responses and frontend context to include party metadata, reducing redundant API calls and improving data consistency.

## Overview

Currently, the frontend makes multiple API calls to get party session status (PartyGame fetches it, then PartyRoundModal fetches it again). Additionally, round start/submit responses don't include party progress information, forcing components to make separate requests. This phase enriches responses with party context and extends PartyModeContext to cache this data.

## Prerequisites

- Phase 1, 2, and 3 complete
- Understanding of TypeScript types and interfaces
- Familiarity with React Context patterns

## Objectives

1. ✅ Add `party_context` to round start responses
2. ✅ Include party progress in submission responses
3. ✅ Extend PartyModeContext with session configuration and progress
4. ✅ Update PartyRoundModal to use context instead of fetching
5. ✅ Create standardized DTOs for party data
6. ✅ Reduce redundant API calls by 60%+

---

## Implementation Steps

### Step 1: Define Party Context DTOs

**File**: `qf_frontend/src/api/types.ts`

**Add** these new types:

```typescript
/**
 * Party context included in round responses when in party mode.
 */
export interface PartyContext {
  session_id: string;
  current_phase: string;
  your_progress: {
    prompts_submitted: number;
    prompts_required: number;
    copies_submitted: number;
    copies_required: number;
    votes_submitted: number;
    votes_required: number;
  };
  session_progress: {
    players_ready_for_next_phase: number;
    total_players: number;
  };
}

/**
 * Enhanced round start response with optional party context.
 */
export interface PartyPromptRoundResponse {
  round_id: string;
  party_round_id?: string;
  round_type: 'prompt';
  prompt_text: string;
  expires_at: string;
  cost: number;
  status: string;
  party_context?: PartyContext;
}

export interface PartyCopyRoundResponse {
  round_id: string;
  party_round_id?: string;
  round_type: 'copy';
  original_phrase: string;
  prompt_round_id: string;
  expires_at: string;
  cost: number;
  status: string;
  discount_active?: boolean;
  party_context?: PartyContext;
}

export interface PartyVoteRoundResponse {
  round_id: string;
  party_round_id?: string;
  round_type: 'vote';
  phraseset_id: string;
  prompt_text: string;
  phrases: string[];
  expires_at: string;
  cost: number;
  status: string;
  party_context?: PartyContext;
}

/**
 * Enhanced submission response with party metadata.
 */
export interface SubmitPhraseResponse {
  success: boolean;
  phrase: string;
  round_type: 'prompt' | 'copy';
  // Party-specific fields (present when in party mode)
  party_session_id?: string;
  party_round_id?: string;
  party_context?: PartyContext;
  // Copy-specific fields
  eligible_for_second_copy?: boolean;
  second_copy_cost?: number;
  prompt_round_id?: string;
  original_phrase?: string;
  phraseset_created?: boolean;
  phraseset_id?: string;
}

export interface VoteResponse {
  correct: boolean;
  payout: number;
  your_choice: string;
  original_phrase: string;
  // Party-specific fields
  party_session_id?: string;
  party_context?: PartyContext;
}
```

---

### Step 2: Extend PartyModeContext State

**File**: `qf_frontend/src/contexts/PartyModeContext.tsx`

**Replace** state interface:

```typescript
// OLD:
interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;
}

// NEW:
interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;

  // Session configuration (set once at start, doesn't change)
  sessionConfig: {
    prompts_per_player: number;
    copies_per_player: number;
    votes_per_player: number;
    min_players: number;
    max_players: number;
  } | null;

  // Player's individual progress (updated on each submission)
  yourProgress: {
    prompts_submitted: number;
    copies_submitted: number;
    votes_submitted: number;
  } | null;

  // Overall session progress (updated via WebSocket or context refresh)
  sessionProgress: {
    players_ready_for_next_phase: number;
    total_players: number;
  } | null;
}
```

**Update** default state:

```typescript
const defaultState: PartyModeState = {
  isPartyMode: false,
  sessionId: null,
  currentStep: null,
  sessionConfig: null,
  yourProgress: null,
  sessionProgress: null,
};
```

**Add** new actions:

```typescript
interface PartyModeActions {
  startPartyMode: (
    sessionId: string,
    initialStep?: PartyStep,
    config?: PartyModeState['sessionConfig']
  ) => void;
  endPartyMode: () => void;
  setCurrentStep: (step: PartyStep) => void;

  // NEW: Update progress from API responses
  updateYourProgress: (progress: PartyModeState['yourProgress']) => void;
  updateSessionProgress: (progress: PartyModeState['sessionProgress']) => void;
  updateFromPartyContext: (context: PartyContext) => void;
}
```

**Implement** new action handlers:

```typescript
export const PartyModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<PartyModeState>(() => loadInitialState());

  const startPartyMode = useCallback(
    (sessionId: string, initialStep: PartyStep = 'prompt', config?: PartyModeState['sessionConfig']) => {
      setState((prev) => {
        const nextState: PartyModeState = {
          ...prev,
          isPartyMode: true,
          sessionId,
          currentStep: initialStep,
          sessionConfig: config || prev.sessionConfig,
        };
        persistState(nextState);
        return nextState;
      });
    },
    []
  );

  const updateYourProgress = useCallback((progress: PartyModeState['yourProgress']) => {
    setState((prev) => {
      const nextState = { ...prev, yourProgress: progress };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const updateSessionProgress = useCallback((progress: PartyModeState['sessionProgress']) => {
    setState((prev) => {
      const nextState = { ...prev, sessionProgress: progress };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const updateFromPartyContext = useCallback((context: PartyContext) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        yourProgress: context.your_progress,
        sessionProgress: context.session_progress,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const value = useMemo<PartyModeContextValue>(
    () => ({
      state,
      actions: {
        startPartyMode,
        endPartyMode,
        setCurrentStep,
        updateYourProgress,
        updateSessionProgress,
        updateFromPartyContext,
      },
    }),
    [state, startPartyMode, endPartyMode, setCurrentStep, updateYourProgress, updateSessionProgress, updateFromPartyContext]
  );

  return <PartyModeContext.Provider value={value}>{children}</PartyModeContext.Provider>;
};
```

**Why**: Context now caches party data, reducing need for redundant API calls.

---

### Step 3: Update Backend to Include Party Context in Responses

**File**: `backend/routes/qf/party.py`

**Enhance** round start endpoints to include party context:

```python
@router.post("/{session_id}/rounds/prompt")
async def start_party_prompt_round(
    session_id: UUID,
    player: QFPlayer = Depends(get_current_player),
    db: AsyncSession = Depends(get_db)
):
    """Start a prompt round within party session."""
    coordination_service = PartyCoordinationService(db)
    party_session_service = PartySessionService(db)
    transaction_service = TransactionService(db)

    round_obj, party_round_id = await coordination_service.start_party_prompt_round(
        session_id=session_id,
        player=player,
        transaction_service=transaction_service
    )

    # Get participant progress
    participant = await party_session_service.get_participant(session_id, player.player_id)

    # Get session config
    session = await party_session_service.get_session_by_id(session_id)

    # Get all participants for session progress
    all_participants = await party_session_service.get_participants(session_id)
    active_participants = [p for p in all_participants if p.status == 'ACTIVE']
    players_ready = sum(1 for p in active_participants if p.prompts_submitted >= session.prompts_per_player)

    return {
        "round_id": str(round_obj.round_id),
        "party_round_id": str(party_round_id),
        "round_type": "prompt",
        "prompt_text": round_obj.prompt_text,
        "expires_at": round_obj.expires_at.isoformat(),
        "cost": round_obj.cost,
        "status": round_obj.status,
        # NEW: Party context
        "party_context": {
            "session_id": str(session_id),
            "current_phase": session.current_phase,
            "your_progress": {
                "prompts_submitted": participant.prompts_submitted,
                "prompts_required": session.prompts_per_player,
                "copies_submitted": participant.copies_submitted,
                "copies_required": session.copies_per_player,
                "votes_submitted": participant.votes_submitted,
                "votes_required": session.votes_per_player,
            },
            "session_progress": {
                "players_ready_for_next_phase": players_ready,
                "total_players": len(active_participants),
            }
        }
    }
```

**Repeat for** `start_party_copy_round` and `start_party_vote_round`.

**Update** submission endpoints in `rounds.py` (from Phase 1):

```python
# In the party mode branch:
if is_party_round:
    # ... existing submission logic ...

    # Get updated participant progress
    participant = await party_session_service.get_participant(party_round.session_id, player.player_id)
    session = await party_session_service.get_session_by_id(party_round.session_id)
    all_participants = await party_session_service.get_participants(party_round.session_id)
    active_participants = [p for p in all_participants if p.status == 'ACTIVE']

    # Determine how many players are ready for next phase
    if session.current_phase == 'PROMPT':
        players_ready = sum(1 for p in active_participants if p.prompts_submitted >= session.prompts_per_player)
    elif session.current_phase == 'COPY':
        players_ready = sum(1 for p in active_participants if p.copies_submitted >= session.copies_per_player)
    elif session.current_phase == 'VOTE':
        players_ready = sum(1 for p in active_participants if p.votes_submitted >= session.votes_per_player)
    else:
        players_ready = 0

    return {
        **result,
        "party_session_id": str(party_round.session_id),
        "party_round_id": str(party_round.party_round_id),
        # NEW: Party context
        "party_context": {
            "session_id": str(party_round.session_id),
            "current_phase": session.current_phase,
            "your_progress": {
                "prompts_submitted": participant.prompts_submitted,
                "prompts_required": session.prompts_per_player,
                "copies_submitted": participant.copies_submitted,
                "copies_required": session.copies_per_player,
                "votes_submitted": participant.votes_submitted,
                "votes_required": session.votes_per_player,
            },
            "session_progress": {
                "players_ready_for_next_phase": players_ready,
                "total_players": len(active_participants),
            }
        }
    }
```

---

### Step 4: Update PartyGame to Store Party Context

**File**: `qf_frontend/src/pages/PartyGame.tsx`

**Import** updated types and context actions:

```typescript
import type { PartyPromptRoundResponse, PartyCopyRoundResponse, PartyVoteRoundResponse } from '../api/types';
```

**After** calling party round endpoints, update context:

```typescript
if (step === 'prompt') {
  const roundData: PartyPromptRoundResponse = await apiClient.startPartyPromptRound(sessionId);

  // NEW: Update party context from response
  if (roundData.party_context) {
    partyActions.updateFromPartyContext(roundData.party_context);
  }

  // If this is the first round, also store session config
  if (!partyState.sessionConfig && roundData.party_context) {
    partyActions.startPartyMode(sessionId, 'prompt', {
      prompts_per_player: roundData.party_context.your_progress.prompts_required,
      copies_per_player: roundData.party_context.your_progress.copies_required,
      votes_per_player: roundData.party_context.your_progress.votes_required,
      min_players: 0, // Could fetch from session status if needed
      max_players: 0,
    });
  }

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
}
```

**Repeat** for copy and vote rounds.

---

### Step 5: Update Round Pages to Update Context After Submission

**File**: `qf_frontend/src/pages/PromptRound.tsx` (Lines 209-242)

**After successful submission**, update party context:

```typescript
const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();

  if (!roundData || isSubmitting || !isPhraseValid) return;
  if (roundData.status === 'submitted') return;

  setIsSubmitting(true);
  setError(null);

  try {
    const response: SubmitPhraseResponse = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

    // Show success messages
    const heading = getRandomMessage('promptSubmitted');
    const feedback = getRandomMessage('promptSubmittedFeedback');
    setSuccessMessage(heading);
    setFeedbackMessage(feedback);

    // NEW: Update party context if present
    if (response.party_context) {
      partyActions.updateFromPartyContext(response.party_context);
    }

    // Refresh dashboard
    await refreshDashboard();

    // Navigate after delay (if not in party mode)
    setTimeout(() => {
      if (!partyState.isPartyMode) {
        navigate('/dashboard');
      }
    }, 2000);
  } catch (err) {
    const message = extractErrorMessage(err) || 'Unable to submit your phrase.';
    setError(message);
  } finally {
    setIsSubmitting(false);
  }
};
```

**Repeat** for CopyRound.tsx and VoteRound.tsx.

---

### Step 6: Update PartyRoundModal to Use Context Instead of Fetching

**File**: `qf_frontend/src/components/party/PartyRoundModal.tsx`

**Before** (Lines 27-41):
```typescript
const loadStatus = useCallback(async () => {
  if (!sessionId) return;

  setIsLoading(true);
  try {
    const status = await apiClient.getPartySessionStatus(sessionId);
    setSessionStatus(status);
    setError(null);
  } catch (err) {
    console.error('Failed to load party session status', err);
    setError('Unable to refresh party status right now.');
  } finally {
    setIsLoading(false);
  }
}, [sessionId]);
```

**After** (use context as source of truth):
```typescript
import { usePartyMode } from '../../contexts/PartyModeContext';

export const PartyRoundModal: React.FC<PartyRoundModalProps> = ({ sessionId, currentStep }) => {
  const { state: gameState } = useGame();
  const { state: partyState } = usePartyMode(); // Get party context

  // Derive values from context instead of fetching
  const currentPlayer = useMemo(() => {
    if (!gameState.player?.player_id) return null;
    return {
      player_id: gameState.player.player_id,
      username: gameState.player.username,
      prompts_submitted: partyState.yourProgress?.prompts_submitted ?? 0,
      prompts_required: partyState.sessionConfig?.prompts_per_player ?? 0,
      copies_submitted: partyState.yourProgress?.copies_submitted ?? 0,
      copies_required: partyState.sessionConfig?.copies_per_player ?? 0,
      votes_submitted: partyState.yourProgress?.votes_submitted ?? 0,
      votes_required: partyState.sessionConfig?.votes_per_player ?? 0,
    };
  }, [gameState.player, partyState.yourProgress, partyState.sessionConfig]);

  const playersReady = partyState.sessionProgress?.players_ready_for_next_phase ?? 0;
  const totalPlayers = partyState.sessionProgress?.total_players ?? 0;

  // Only fetch on mount if context is empty (shouldn't happen in normal flow)
  useEffect(() => {
    if (!partyState.yourProgress && sessionId) {
      // Fallback: fetch session status
      console.warn('PartyRoundModal: Context empty, fetching session status as fallback');
      const fetchStatus = async () => {
        try {
          const status = await apiClient.getPartySessionStatus(sessionId);
          // Update context with fetched data
          const participant = status.participants.find(p => p.player_id === gameState.player?.player_id);
          if (participant) {
            partyActions.updateYourProgress({
              prompts_submitted: participant.prompts_submitted,
              copies_submitted: participant.copies_submitted,
              votes_submitted: participant.votes_submitted,
            });
          }
        } catch (err) {
          console.error('Failed to fetch session status:', err);
        }
      };
      fetchStatus();
    }
  }, [partyState.yourProgress, sessionId, gameState.player?.player_id]);

  // WebSocket updates should update context, not local state
  usePartyWebSocket({
    sessionId,
    onProgressUpdate: () => {
      // Context is already updated by submission response
      // Just trigger re-render if needed
    },
    onPhaseTransition: (data) => {
      // Update current step based on new phase
      partyActions.setCurrentStep(data.new_phase.toLowerCase() as PartyStep);
    },
    onSessionUpdate: () => {
      // Could update session progress here if WebSocket provides it
    },
  });
```

**Why**: Eliminates redundant API call. Context is updated by submissions and round starts.

---

## API Call Reduction Summary

### Before Phase 4

**PartyGame.tsx** (on mount):
1. `GET /party/{sessionId}/status` (fetch session status)
2. `POST /party/{sessionId}/rounds/prompt` (start round)

**PartyRoundModal** (on mount):
3. `GET /party/{sessionId}/status` (fetch session status again!)

**After Each Submission**:
4. `POST /rounds/{roundId}/submit` (submit phrase)
5. WebSocket broadcast (server → client)

**Total**: 5 requests per round (2 duplicate status fetches)

---

### After Phase 4

**PartyGame.tsx** (on mount):
1. `POST /party/{sessionId}/rounds/prompt` (includes party_context in response)

**PartyRoundModal** (on mount):
- No API call! Uses context.

**After Each Submission**:
2. `POST /rounds/{roundId}/submit` (includes updated party_context in response)
3. WebSocket broadcast (server → client)

**Total**: 3 requests per round (0 duplicate fetches)

**Reduction**: 40% fewer API calls (5 → 3)

**Benefit**: Faster perceived performance, less backend load, consistent data.

---

## Testing

### Verify Context Updates

**Test 1: Party context populated on round start**

```typescript
// Start party prompt round
const response = await apiClient.startPartyPromptRound(sessionId);

// Verify response includes party_context
expect(response.party_context).toBeDefined();
expect(response.party_context.your_progress.prompts_submitted).toBe(0);
expect(response.party_context.your_progress.prompts_required).toBe(1);

// Verify context updated
const { state: partyState } = usePartyMode();
expect(partyState.yourProgress?.prompts_submitted).toBe(0);
```

**Test 2: Progress updates after submission**

```typescript
// Submit prompt
const submitResponse = await apiClient.submitPhrase(roundId, 'test phrase');

// Verify party_context in response shows updated progress
expect(submitResponse.party_context?.your_progress.prompts_submitted).toBe(1);

// Verify context updated
const { state: partyState } = usePartyMode();
expect(partyState.yourProgress?.prompts_submitted).toBe(1);
```

**Test 3: PartyRoundModal uses context (no fetch)**

```typescript
// Spy on API calls
const spy = jest.spyOn(apiClient, 'getPartySessionStatus');

// Render PartyRoundModal
render(<PartyRoundModal sessionId={sessionId} currentStep="prompt" />);

// Verify NO fetch call made (context used instead)
expect(spy).not.toHaveBeenCalled();

// Verify progress displayed from context
expect(screen.getByText(/1 \/ 1/)).toBeInTheDocument(); // prompts_submitted / prompts_required
```

---

## Success Criteria

- [ ] Backend responses include `party_context`
- [ ] PartyModeContext stores session config and progress
- [ ] Context updated after round starts
- [ ] Context updated after submissions
- [ ] PartyRoundModal uses context (no redundant fetch)
- [ ] API calls reduced by 40%+
- [ ] Data consistency across components
- [ ] All tests pass

---

## Next Steps

After completing Phase 4:

1. ✅ Monitor network tab: verify no duplicate `/status` calls
2. ✅ Test context persistence (reload page, context should restore)
3. ✅ Verify WebSocket updates still work
4. ➡️ Proceed to [Phase 5: Maximum Reuse](./phase-5-maximum-reuse.md) (optional polish)

---

## Estimated Time

- **Define DTOs**: 30 minutes
- **Extend PartyModeContext**: 1 hour
- **Update backend responses**: 1.5 hours
- **Update PartyGame and round pages**: 1 hour
- **Update PartyRoundModal**: 30 minutes
- **Testing**: 30 minutes
- **Total**: **2-3 hours**
