# Phase 2: Frontend Consolidation

> **Goal**: Extract duplicate round transition and navigation logic into reusable hooks, eliminating ~250+ lines of repeated code.

## Overview

Currently, PromptRound.tsx, CopyRound.tsx, and VoteRound.tsx each contain nearly identical code for:
- Transitioning to the next round in party mode
- Navigating home/exit based on party mode
- Error handling for round transitions
- Managing loading/error states

This phase consolidates all that logic into 2-3 reusable hooks.

## Prerequisites

- Phase 1 complete (party-aware backend)
- Understanding of React hooks and custom hooks
- Familiarity with existing round pages

## Objectives

1. ✅ Create `usePartyRoundCoordinator()` hook for round transitions
2. ✅ Create `usePartyNavigation()` hook for conditional navigation
3. ✅ Extend `usePartyMode()` with helper utilities
4. ✅ Update all 3 round pages to use new hooks
5. ✅ Remove ~250 lines of duplicate code

---

## Implementation Steps

### Step 1: Create usePartyRoundCoordinator Hook

**File**: `qf_frontend/src/hooks/usePartyRoundCoordinator.ts` (new file)

This hook centralizes ALL round transition logic for party mode.

```typescript
import { useCallback, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';
import apiClient, { extractErrorMessage } from '../api/client';

type RoundType = 'prompt' | 'copy' | 'vote';

interface TransitionState {
  isTransitioning: boolean;
  error: string | null;
}

/**
 * Coordinates round transitions in party mode.
 *
 * Handles:
 * - Starting the next round via party-specific endpoints
 * - Updating party mode step
 * - Navigation to next round page
 * - Error handling and retry logic
 *
 * Usage:
 *   const { transitionToNextRound, isTransitioning, error } = usePartyRoundCoordinator();
 *
 *   // After successful submission:
 *   useEffect(() => {
 *     if (successMessage && partyState.isPartyMode) {
 *       transitionToNextRound('prompt').catch(err => console.error(err));
 *     }
 *   }, [successMessage]);
 */
export function usePartyRoundCoordinator() {
  const { state: partyState, actions: partyActions } = usePartyMode();
  const navigate = useNavigate();
  const [state, setState] = useState<TransitionState>({
    isTransitioning: false,
    error: null,
  });
  const attemptedRef = useRef(false);

  /**
   * Transition from current round to the next round in party mode.
   *
   * @param currentRound - The round type that just completed
   * @returns Promise that resolves when transition complete
   * @throws Error if transition fails (after all retries)
   */
  const transitionToNextRound = useCallback(
    async (currentRound: RoundType): Promise<void> => {
      // Guard: Only in party mode
      if (!partyState.isPartyMode || !partyState.sessionId) {
        console.warn('transitionToNextRound called but not in party mode');
        return;
      }

      // Guard: Prevent duplicate attempts
      if (attemptedRef.current) {
        console.warn('Transition already in progress, skipping duplicate call');
        return;
      }

      setState({ isTransitioning: true, error: null });
      attemptedRef.current = true;

      // Define transition mappings
      const transitions: Record<
        RoundType,
        {
          next: 'copy' | 'vote' | 'results';
          endpoint?: (sessionId: string) => Promise<any>;
          path: string;
        }
      > = {
        prompt: {
          next: 'copy',
          endpoint: apiClient.startPartyCopyRound,
          path: '/copy',
        },
        copy: {
          next: 'vote',
          endpoint: apiClient.startPartyVoteRound,
          path: '/vote',
        },
        vote: {
          next: 'results',
          endpoint: undefined, // No endpoint, just navigate
          path: `/party/results/${partyState.sessionId}`,
        },
      };

      const transition = transitions[currentRound];

      try {
        // Special case: vote → results (no round to start, just navigate and end party mode)
        if (transition.next === 'results') {
          partyActions.endPartyMode();
          navigate(transition.path, { replace: true });
          setState({ isTransitioning: false, error: null });
          return;
        }

        // Start next round via party-specific endpoint
        if (!transition.endpoint) {
          throw new Error(`No endpoint defined for ${currentRound} → ${transition.next} transition`);
        }

        await transition.endpoint(partyState.sessionId);

        // Update party mode step
        partyActions.setCurrentStep(transition.next);

        // Navigate to next round page
        navigate(transition.path, { replace: true });

        setState({ isTransitioning: false, error: null });
        attemptedRef.current = false; // Reset for next transition
      } catch (err) {
        const message =
          extractErrorMessage(err) || `Unable to start the ${transition.next} round.`;

        setState({ isTransitioning: false, error: message });
        attemptedRef.current = false; // Allow retry

        throw new Error(message);
      }
    },
    [partyState.isPartyMode, partyState.sessionId, navigate, partyActions]
  );

  /**
   * Reset error state (useful for retry buttons)
   */
  const clearError = useCallback(() => {
    setState((prev) => ({ ...prev, error: null }));
    attemptedRef.current = false;
  }, []);

  return {
    transitionToNextRound,
    isTransitioning: state.isTransitioning,
    error: state.error,
    clearError,
  };
}
```

**Why This Works**:
- **Single place** to update transition logic
- **Consistent error handling** across all rounds
- **Prevents duplicate calls** via ref
- **Clean API** for round pages to use

---

### Step 2: Create usePartyNavigation Hook

**File**: `qf_frontend/src/hooks/usePartyNavigation.ts` (new file)

This hook handles conditional navigation based on party mode state.

```typescript
import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../contexts/PartyModeContext';

/**
 * Provides party-aware navigation helpers.
 *
 * Handles conditional navigation based on whether user is in party mode.
 *
 * Usage:
 *   const { navigateHome, navigateToResults } = usePartyNavigation();
 *
 *   <button onClick={navigateHome}>Back</button>
 */
export function usePartyNavigation() {
  const { state: partyState, actions: partyActions } = usePartyMode();
  const navigate = useNavigate();

  /**
   * Navigate to home/dashboard.
   * - Party mode: Exit party mode and go to /party
   * - Normal mode: Go to /dashboard
   */
  const navigateHome = useCallback(() => {
    if (partyState.isPartyMode) {
      partyActions.endPartyMode();
      navigate('/party');
    } else {
      navigate('/dashboard');
    }
  }, [partyState.isPartyMode, partyActions, navigate]);

  /**
   * Navigate to results page.
   * - Party mode: Go to /party/results/{sessionId}
   * - Normal mode: Go to /dashboard
   */
  const navigateToResults = useCallback(() => {
    if (partyState.isPartyMode && partyState.sessionId) {
      partyActions.endPartyMode();
      navigate(`/party/results/${partyState.sessionId}`);
    } else {
      navigate('/dashboard');
    }
  }, [partyState.isPartyMode, partyState.sessionId, partyActions, navigate]);

  /**
   * Get the appropriate results path without navigating.
   */
  const getResultsPath = useCallback((): string => {
    if (partyState.isPartyMode && partyState.sessionId) {
      return `/party/results/${partyState.sessionId}`;
    }
    return '/dashboard';
  }, [partyState.isPartyMode, partyState.sessionId]);

  /**
   * Check if currently in party mode (convenience helper).
   */
  const isInPartyMode = partyState.isPartyMode;

  return {
    navigateHome,
    navigateToResults,
    getResultsPath,
    isInPartyMode,
  };
}
```

---

### Step 3: Extend usePartyMode with Helpers

**File**: `qf_frontend/src/contexts/PartyModeContext.tsx`

**Add** helper functions to the context (no state changes, just derived values):

```typescript
// ... existing code ...

export const usePartyMode = (): PartyModeContextValue => {
  const context = useContext(PartyModeContext);
  if (!context) {
    throw new Error('usePartyMode must be used within a PartyModeProvider');
  }
  return context;
};

// ADD THESE NEW HELPER HOOKS:

/**
 * Check if currently in party mode (convenience hook).
 */
export const useIsInPartyMode = (): boolean => {
  const { state } = usePartyMode();
  return state.isPartyMode;
};

/**
 * Get current party session ID (or null if not in party mode).
 */
export const usePartySessionId = (): string | null => {
  const { state } = usePartyMode();
  return state.sessionId;
};

/**
 * Get current party step (or null if not in party mode).
 */
export const usePartyStep = (): PartyStep | null => {
  const { state } = usePartyMode();
  return state.currentStep;
};
```

**Why**: Makes conditional checks cleaner in components.

---

### Step 4: Update PromptRound.tsx to Use New Hooks

**File**: `qf_frontend/src/pages/PromptRound.tsx`

**Remove** (Lines 53-73):
```typescript
// DELETE THIS ENTIRE FUNCTION:
const beginPartyCopyRound = useCallback(async () => {
  if (!partyState.isPartyMode || nextRoundAttemptedRef.current) {
    return;
  }
  // ... ~20 lines of transition logic ...
}, [navigate, partyState.isPartyMode, setCurrentStep, startCopyRound]);
```

**Remove** (Lines 185-192):
```typescript
// DELETE THIS ENTIRE FUNCTION:
const handleHomeNavigation = () => {
  if (partyState.isPartyMode) {
    endPartyMode();
    navigate('/party');
  } else {
    navigate('/dashboard');
  }
};
```

**Add** (at top of component, after existing hooks):
```typescript
import { usePartyRoundCoordinator } from '../hooks/usePartyRoundCoordinator';
import { usePartyNavigation } from '../hooks/usePartyNavigation';

export const PromptRound: React.FC = () => {
  // ... existing hooks ...

  // ADD THESE:
  const { transitionToNextRound, isTransitioning: isStartingNextRound, error: nextRoundError } = usePartyRoundCoordinator();
  const { navigateHome, isInPartyMode } = usePartyNavigation();

  // REMOVE: nextRoundAttemptedRef, isStartingNextRound state, nextRoundError state
  // They're now handled by the hook
```

**Replace** (Lines 133-137):
```typescript
// OLD:
useEffect(() => {
  if (successMessage && partyState.isPartyMode) {
    void beginPartyCopyRound();
  }
}, [beginPartyCopyRound, partyState.isPartyMode, successMessage]);

// NEW:
useEffect(() => {
  if (successMessage && isInPartyMode) {
    transitionToNextRound('prompt').catch(err => {
      console.error('Failed to transition to copy round:', err);
      // Error state is already set by the hook
    });
  }
}, [successMessage, isInPartyMode, transitionToNextRound]);
```

**Replace** (Line 386):
```typescript
// OLD:
<button onClick={handleHomeNavigation}>

// NEW:
<button onClick={navigateHome}>
```

**Replace** (Line 267):
```typescript
// OLD:
{partyState.isPartyMode ? 'Starting the impostor round...' : 'Returning to dashboard...'}

// NEW:
{isInPartyMode ? 'Starting the impostor round...' : 'Returning to dashboard...'}
```

**Replace** error retry button (Lines 275-280):
```typescript
// OLD:
<button onClick={() => {
  nextRoundAttemptedRef.current = false;
  void beginPartyCopyRound();
}}>
  Retry
</button>

// NEW:
<button onClick={() => transitionToNextRound('prompt')}>
  Retry
</button>
```

---

### Step 5: Update CopyRound.tsx to Use New Hooks

**File**: `qf_frontend/src/pages/CopyRound.tsx`

**Same pattern as PromptRound**:

1. **Remove** `beginPartyVoteRound()` function (Lines 271-291)
2. **Remove** `handleHomeNavigation()` function (Lines 297-304)
3. **Add** hooks at top:
   ```typescript
   const { transitionToNextRound, isTransitioning: isStartingNextRound, error: nextRoundError } = usePartyRoundCoordinator();
   const { navigateHome, isInPartyMode } = usePartyNavigation();
   ```
4. **Replace** transition effect (Lines 390-394):
   ```typescript
   useEffect(() => {
     if (isInPartyMode && successMessage && !awaitingSecondCopyDecision && !secondCopyEligibility) {
       transitionToNextRound('copy').catch(err => console.error(err));
     }
   }, [awaitingSecondCopyDecision, isInPartyMode, secondCopyEligibility, successMessage, transitionToNextRound]);
   ```
5. **Replace** all `handleHomeNavigation` calls with `navigateHome`
6. **Replace** all `partyState.isPartyMode` checks with `isInPartyMode`

---

### Step 6: Update VoteRound.tsx to Use New Hooks

**File**: `qf_frontend/src/pages/VoteRound.tsx`

**Remove** (Lines 84-91):
```typescript
// DELETE:
const navigateAfterVote = useCallback(() => {
  if (partyState.isPartyMode) {
    partyActions.endPartyMode();
    navigate(partyResultsPath);
  } else {
    navigate('/dashboard');
  }
}, [navigate, partyActions, partyResultsPath, partyState.isPartyMode]);
```

**Add** hooks:
```typescript
const { navigateToResults, isInPartyMode } = usePartyNavigation();
```

**Replace** (Line 163):
```typescript
// OLD:
const handleDismiss = () => {
  voteRoundLogger.debug('Dismissing vote results');
  navigateAfterVote();
};

// NEW:
const handleDismiss = () => {
  voteRoundLogger.debug('Dismissing vote results');
  navigateToResults();
};
```

**Replace** all `partyState.isPartyMode` with `isInPartyMode`

**Note**: VoteRound doesn't need `transitionToNextRound` since it just navigates to results.

---

## Code Reduction Summary

### Before (Duplicate Code)

**PromptRound.tsx**:
- `beginPartyCopyRound()`: ~20 lines
- `handleHomeNavigation()`: ~8 lines
- State management: ~3 lines
- **Total: ~31 lines**

**CopyRound.tsx**:
- `beginPartyVoteRound()`: ~20 lines
- `handleHomeNavigation()`: ~8 lines
- State management: ~3 lines
- **Total: ~31 lines**

**VoteRound.tsx**:
- `navigateAfterVote()`: ~8 lines
- Conditional navigation: ~5 lines
- **Total: ~13 lines**

**Grand Total: ~75 lines** (repeated code per page) × 3 pages = **~225 lines**

### After (Consolidated)

**New Hooks**:
- `usePartyRoundCoordinator.ts`: ~120 lines (but reusable!)
- `usePartyNavigation.ts`: ~60 lines (but reusable!)
- PartyModeContext helpers: ~20 lines

**Updated Round Pages**:
- Each page: ~3-5 lines of hook usage

**Net Result**:
- **Removed**: ~225 lines of duplicate code
- **Added**: ~200 lines of reusable hooks
- **Net Savings**: ~25 lines + massively improved maintainability

---

## Testing

### Manual Testing Checklist

**Test Party Mode Round Transitions**:

1. Create party session
2. Join with 2 players
3. Host starts session
4. **Prompt Round**:
   - Submit prompt
   - Verify "Starting the impostor round..." message
   - Verify auto-navigation to /copy
5. **Copy Round**:
   - Submit copy
   - Verify "Starting the vote round..." message
   - Verify auto-navigation to /vote
6. **Vote Round**:
   - Submit vote
   - Verify "View Party Summary" button
   - Click button → navigate to party results
7. Verify no errors in console

**Test Normal Mode (Regression)**:

1. Play normal prompt round
2. Submit prompt
3. Verify "Returning to dashboard..." message
4. Verify navigation to /dashboard
5. Repeat for copy and vote rounds

**Test Error Handling**:

1. Start party session
2. Disable backend (simulate network error)
3. Submit prompt
4. Verify error message appears
5. Click "Retry" button
6. Verify transition attempted again

**Test Home Navigation**:

1. In party mode, click "Exit Party Mode"
2. Verify navigation to /party
3. In normal mode, click "Back to Dashboard"
4. Verify navigation to /dashboard

### Unit Tests

**File**: `qf_frontend/src/hooks/__tests__/usePartyRoundCoordinator.test.ts` (new)

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePartyRoundCoordinator } from '../usePartyRoundCoordinator';
import { PartyModeProvider } from '../../contexts/PartyModeContext';
import apiClient from '../../api/client';

jest.mock('../../api/client');
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}));

describe('usePartyRoundCoordinator', () => {
  it('should transition from prompt to copy round', async () => {
    const mockStartCopy = jest.fn().mockResolvedValue({ round_id: 'copy123' });
    (apiClient.startPartyCopyRound as jest.Mock) = mockStartCopy;

    const wrapper = ({ children }: any) => (
      <PartyModeProvider>{children}</PartyModeProvider>
    );

    const { result } = renderHook(() => usePartyRoundCoordinator(), { wrapper });

    // Simulate party mode
    act(() => {
      // Setup party mode state
    });

    await act(async () => {
      await result.current.transitionToNextRound('prompt');
    });

    expect(mockStartCopy).toHaveBeenCalledWith(expect.any(String));
    expect(result.current.isTransitioning).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should handle transition errors', async () => {
    const mockStartCopy = jest.fn().mockRejectedValue(new Error('Network error'));
    (apiClient.startPartyCopyRound as jest.Mock) = mockStartCopy;

    const { result } = renderHook(() => usePartyRoundCoordinator(), { wrapper });

    await act(async () => {
      try {
        await result.current.transitionToNextRound('prompt');
      } catch (err) {
        // Expected
      }
    });

    expect(result.current.error).toContain('Network error');
    expect(result.current.isTransitioning).toBe(false);
  });
});
```

---

## Rollback Plan

If issues arise:

### Quick Rollback

1. **Keep old functions** temporarily (comment out instead of deleting)
2. **Add feature flag** in component:
   ```typescript
   const USE_NEW_HOOKS = false; // Set to false to use old code

   if (USE_NEW_HOOKS) {
     const { transitionToNextRound } = usePartyRoundCoordinator();
   } else {
     // Old beginPartyCopyRound code
   }
   ```
3. **Revert imports** if hooks cause issues

### Full Rollback

```bash
git revert <commit-hash>  # Revert hook creation
git revert <commit-hash>  # Revert round page updates
```

---

## Success Criteria

- [ ] `usePartyRoundCoordinator` hook created and tested
- [ ] `usePartyNavigation` hook created and tested
- [ ] All 3 round pages updated to use new hooks
- [ ] Duplicate code removed (~225 lines)
- [ ] Party mode transitions work end-to-end
- [ ] Normal mode still works (regression test)
- [ ] Error handling works correctly
- [ ] All tests pass

---

## Next Steps

After completing Phase 2:

1. ✅ Test manually with party session
2. ✅ Run frontend tests: `npm test`
3. ✅ Check bundle size (should be smaller)
4. ➡️ Proceed to [Phase 3: Integration Fixes](./phase-3-integration-fixes.md)

---

## Estimated Time

- **Create coordinator hook**: 1 hour
- **Create navigation hook**: 30 minutes
- **Update PromptRound**: 30 minutes
- **Update CopyRound**: 30 minutes
- **Update VoteRound**: 20 minutes
- **Write tests**: 1 hour
- **Testing and debugging**: 30 minutes
- **Total**: **3-4 hours**
