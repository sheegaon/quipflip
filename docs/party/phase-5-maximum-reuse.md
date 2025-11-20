# Phase 5: Maximum Reuse (Advanced Patterns)

> **Goal**: Apply advanced refactoring patterns to achieve near-zero duplication between party and normal modes, maximizing code reuse and maintainability.

## Overview

This is an **optional but recommended** phase that goes beyond basic consolidation to create truly mode-agnostic round pages. After Phases 1-4, party mode works correctly but still has some conditional logic scattered across components. This phase eliminates that, making the codebase more elegant and easier to extend.

## Prerequisites

- Phases 1-4 complete
- Understanding of React composition patterns
- Familiarity with higher-order components or custom hooks
- Willingness to refactor for long-term maintainability

## Objectives

1. ✅ Create `usePartyRoundOverlay()` hook for unified round overlay logic
2. ✅ Consolidate success message handling into `useRoundSubmissionFlow()`
3. ✅ Extract common submission patterns
4. ✅ Make round pages truly mode-agnostic
5. ✅ Reduce party-specific code to <10 lines per page

---

## Implementation Steps

### Step 1: Create usePartyRoundOverlay Hook

**File**: `qf_frontend/src/hooks/usePartyRoundOverlay.tsx` (new)

This hook encapsulates BOTH showing the modal AND handling party transitions.

```typescript
import { useEffect } from 'react';
import { usePartyMode } from '../contexts/PartyModeContext';
import { usePartyRoundCoordinator } from './usePartyRoundCoordinator';
import PartyRoundModal from '../components/party/PartyRoundModal';
import { PartyStep } from '../contexts/PartyModeContext';

interface UsePartyRoundOverlayOptions {
  currentRound: 'prompt' | 'copy' | 'vote';
  successMessage: string | null;
  onError?: (error: string) => void;
}

/**
 * Unified hook for party mode overlay and transitions.
 *
 * Handles:
 * - Showing PartyRoundModal when in party mode
 * - Auto-transitioning to next round after successful submission
 * - Error handling for transitions
 *
 * Usage:
 *   const { overlay, isTransitioning, transitionError } = usePartyRoundOverlay({
 *     currentRound: 'prompt',
 *     successMessage,
 *     onError: setError
 *   });
 *
 *   return (
 *     <>
 *       {overlay}
 *       <div>Round content</div>
 *     </>
 *   );
 */
export function usePartyRoundOverlay(options: UsePartyRoundOverlayOptions) {
  const { currentRound, successMessage, onError } = options;
  const { state: partyState } = usePartyMode();
  const {
    transitionToNextRound,
    isTransitioning,
    error: transitionError,
  } = usePartyRoundCoordinator();

  // Auto-transition when submission succeeds in party mode
  useEffect(() => {
    if (successMessage && partyState.isPartyMode) {
      transitionToNextRound(currentRound).catch((err) => {
        console.error(`Failed to transition from ${currentRound}:`, err);
        if (onError) {
          onError(err.message);
        }
      });
    }
  }, [successMessage, partyState.isPartyMode, currentRound, transitionToNextRound, onError]);

  // Sync current step on mount
  useEffect(() => {
    if (partyState.isPartyMode) {
      const stepMap: Record<typeof currentRound, PartyStep> = {
        prompt: 'prompt',
        copy: 'copy',
        vote: 'vote',
      };
      partyActions.setCurrentStep(stepMap[currentRound]);
    }
  }, [partyState.isPartyMode, currentRound]);

  // Render overlay (null if not in party mode)
  const overlay = partyState.isPartyMode && partyState.sessionId ? (
    <PartyRoundModal
      sessionId={partyState.sessionId}
      currentStep={currentRound}
    />
  ) : null;

  return {
    overlay,
    isTransitioning,
    transitionError,
    isInPartyMode: partyState.isPartyMode,
  };
}
```

**Usage in PromptRound.tsx**:

**Before** (Lines 75-83, 133-137):
```typescript
// OLD: Manual overlay rendering
const partyOverlay = partyState.isPartyMode && partyState.sessionId ? (
  <PartyRoundModal sessionId={partyState.sessionId} currentStep="prompt" />
) : null;

// OLD: Manual step sync
useEffect(() => {
  if (partyState.isPartyMode) {
    setCurrentStep('prompt');
  }
}, [partyState.isPartyMode, setCurrentStep]);

// OLD: Manual transition trigger
useEffect(() => {
  if (successMessage && isInPartyMode) {
    transitionToNextRound('prompt').catch(err => console.error(err));
  }
}, [successMessage, isInPartyMode, transitionToNextRound]);

// OLD: Render overlay manually
return (
  <>
    {partyOverlay}
    <div>...</div>
  </>
);
```

**After**:
```typescript
// NEW: Single hook handles everything
import { usePartyRoundOverlay } from '../hooks/usePartyRoundOverlay';

export const PromptRound: React.FC = () => {
  // ... existing state ...
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // REPLACES: partyOverlay, step sync useEffect, transition useEffect
  const { overlay, isTransitioning, transitionError, isInPartyMode } = usePartyRoundOverlay({
    currentRound: 'prompt',
    successMessage,
    onError: setError,
  });

  // ... rest of component ...

  return (
    <>
      {overlay}
      <div>Round content</div>
    </>
  );
};
```

**Code Saved**: ~30 lines per round page × 3 pages = **~90 lines**

---

### Step 2: Create useRoundSubmissionFlow Hook

**File**: `qf_frontend/src/hooks/useRoundSubmissionFlow.ts` (new)

Consolidates the pattern: "submit → show success → navigate after delay".

```typescript
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyNavigation } from './usePartyNavigation';
import { getRandomMessage } from '../utils/brandedMessages';

type RoundType = 'prompt' | 'copy' | 'vote';

interface SubmissionFlowOptions {
  roundType: RoundType;
  onSubmit: () => Promise<void>;
  shouldAutoNavigate?: (isPartyMode: boolean) => boolean;
  navigationDelay?: number; // ms, default 2000
}

/**
 * Manages submission flow for round pages.
 *
 * Handles:
 * - Submission state (loading, error)
 * - Success message display
 * - Auto-navigation after delay (if not in party mode)
 *
 * Usage:
 *   const { handleSubmit, isSubmitting, successMessage, feedbackMessage, error } = useRoundSubmissionFlow({
 *     roundType: 'prompt',
 *     onSubmit: async () => {
 *       await apiClient.submitPhrase(roundId, phrase);
 *     },
 *   });
 *
 *   <form onSubmit={handleSubmit}>...</form>
 */
export function useRoundSubmissionFlow(options: SubmissionFlowOptions) {
  const { roundType, onSubmit, shouldAutoNavigate, navigationDelay = 2000 } = options;
  const navigate = useNavigate();
  const { isInPartyMode } = usePartyNavigation();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  // Determine if should auto-navigate
  const shouldNav = shouldAutoNavigate
    ? shouldAutoNavigate(isInPartyMode)
    : !isInPartyMode; // Default: navigate in normal mode, not in party mode

  // Auto-navigate after success message appears
  useEffect(() => {
    if (successMessage && shouldNav) {
      const timer = setTimeout(() => {
        navigate('/dashboard');
      }, navigationDelay);
      return () => clearTimeout(timer);
    }
  }, [successMessage, shouldNav, navigate, navigationDelay]);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting) return;

      setIsSubmitting(true);
      setError(null);

      try {
        await onSubmit();

        // Show success messages
        const messageKey = `${roundType}Submitted` as const;
        const feedbackKey = `${roundType}SubmittedFeedback` as const;
        const heading = getRandomMessage(messageKey);
        const feedback = getRandomMessage(feedbackKey);

        setSuccessMessage(heading);
        setFeedbackMessage(feedback);
      } catch (err) {
        const message =
          err instanceof Error ? err.message : `Failed to submit ${roundType}.`;
        setError(message);
      } finally {
        setIsSubmitting(false);
      }
    },
    [isSubmitting, onSubmit, roundType]
  );

  return {
    handleSubmit,
    isSubmitting,
    error,
    setError,
    successMessage,
    feedbackMessage,
  };
}
```

**Usage in PromptRound.tsx**:

**Before** (Lines 194-250):
```typescript
const [isSubmitting, setIsSubmitting] = useState(false);
const [error, setError] = useState<string | null>(null);
const [successMessage, setSuccessMessage] = useState<string | null>(null);
const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

const handleSubmit = async (e: React.FormEvent) => {
  e.preventDefault();

  if (!roundData || isSubmitting || !isPhraseValid) return;
  if (roundData.status === 'submitted') return;

  setIsSubmitting(true);
  setError(null);

  try {
    await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

    const heading = getRandomMessage('promptSubmitted');
    const feedback = getRandomMessage('promptSubmittedFeedback');
    setSuccessMessage(heading);
    setFeedbackMessage(feedback);

    // ... party context update ...

    await refreshDashboard();

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

**After**:
```typescript
const { handleSubmit, isSubmitting, error, setError, successMessage, feedbackMessage } = useRoundSubmissionFlow({
  roundType: 'prompt',
  onSubmit: async () => {
    if (!roundData || !isPhraseValid) return;
    if (roundData.status === 'submitted') return;

    const response = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

    // Update party context if present
    if (response.party_context) {
      partyActions.updateFromPartyContext(response.party_context);
    }

    await refreshDashboard();
  },
});
```

**Code Saved**: ~40 lines per round page × 3 pages = **~120 lines**

---

### Step 3: Extract Common Submission Validation

**File**: `qf_frontend/src/hooks/useRoundSubmission.ts` (new)

Handles validation checks that are identical across all rounds.

```typescript
import { useMemo } from 'react';

interface RoundData {
  round_id: string;
  status: string;
  expires_at: string;
}

/**
 * Common submission validation logic.
 *
 * Returns whether submission is allowed based on:
 * - Round exists
 * - Round not already submitted
 * - Round not expired
 * - Phrase valid (if applicable)
 */
export function useRoundSubmission(
  roundData: RoundData | null,
  isPhraseValid: boolean,
  isExpired: boolean
) {
  const canSubmit = useMemo(() => {
    if (!roundData) return false;
    if (roundData.status === 'submitted') return false;
    if (isExpired) return false;
    if (!isPhraseValid) return false;
    return true;
  }, [roundData, isPhraseValid, isExpired]);

  const disabledReason = useMemo(() => {
    if (!roundData) return 'Loading...';
    if (roundData.status === 'submitted') return 'Already submitted';
    if (isExpired) return "Time's up";
    if (!isPhraseValid) return 'Invalid phrase';
    return null;
  }, [roundData, isPhraseValid, isExpired]);

  return { canSubmit, disabledReason };
}
```

**Usage**:
```typescript
const { canSubmit, disabledReason } = useRoundSubmission(roundData, isPhraseValid, isExpired);

<button type="submit" disabled={!canSubmit} title={disabledReason || undefined}>
  {disabledReason || 'Submit Phrase'}
</button>
```

---

### Step 4: Refactor Round Pages to Be Mode-Agnostic

**Goal**: Make round pages work identically regardless of mode, with ALL party-specific logic in hooks.

**PromptRound.tsx** (after all refactoring):

```typescript
import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { usePartyMode } from '../contexts/PartyModeContext';
import { usePartyRoundOverlay } from '../hooks/usePartyRoundOverlay';
import { usePartyNavigation } from '../hooks/usePartyNavigation';
import { useRoundSubmissionFlow } from '../hooks/useRoundSubmissionFlow';
import { useRoundSubmission } from '../hooks/useRoundSubmission';
import { usePhraseValidation } from '../hooks/usePhraseValidation';
import { useTimer } from '../hooks/useTimer';
import apiClient from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { TrackingIcon } from '../components/icons/NavigationIcons';
import { loadingMessages } from '../utils/brandedMessages';
import type { PromptState } from '../api/types';

export const PromptRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability } = state;
  const { refreshDashboard } = actions;
  const { actions: partyActions } = usePartyMode();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');

  const roundData = activeRound?.round_type === 'prompt' ? activeRound.state as PromptState : null;
  const abandonedPenalty = roundAvailability?.abandoned_penalty || 5;

  // Hooks for party mode
  const { overlay, isTransitioning, transitionError, isInPartyMode } = usePartyRoundOverlay({
    currentRound: 'prompt',
    successMessage: submissionState.successMessage,
    onError: submissionState.setError,
  });
  const { navigateHome } = usePartyNavigation();

  // Hooks for submission
  const { isPhraseValid, trimmedPhrase } = usePhraseValidation(phrase);
  const { isExpired } = useTimer(roundData?.expires_at || null);
  const { canSubmit, disabledReason } = useRoundSubmission(roundData, isPhraseValid, isExpired);

  const submissionState = useRoundSubmissionFlow({
    roundType: 'prompt',
    onSubmit: async () => {
      if (!roundData || !canSubmit) return;

      const response = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

      // Update party context if present
      if (response.party_context) {
        partyActions.updateFromPartyContext(response.party_context);
      }

      await refreshDashboard();
    },
  });

  const { handleSubmit, isSubmitting, error, successMessage, feedbackMessage } = submissionState;

  // Redirect if no active round (unless showing success)
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'prompt') {
      if (successMessage) return; // Don't navigate during success display

      const timeoutId = setTimeout(() => {
        if (isInPartyMode) {
          navigate(`/party/game/${partyState.sessionId}`);
        } else {
          navigate('/dashboard');
        }
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, successMessage, isInPartyMode, navigate]);

  // Success state
  if (successMessage) {
    return (
      <>
        {overlay}
        <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
          <div className="tile-card max-w-md w-full p-8 text-center flip-enter space-y-2">
            <div className="flex justify-center mb-4">
              <TrackingIcon className="w-24 h-24" />
            </div>
            <h2 className="text-2xl font-display font-bold text-quip-turquoise mb-2">
              {successMessage}
            </h2>
            <p className="text-lg text-quip-teal mb-4">{feedbackMessage}</p>
            <p className="text-sm text-quip-teal">
              {isInPartyMode ? 'Starting the impostor round...' : 'Returning to dashboard...'}
            </p>
            {isTransitioning && isInPartyMode && (
              <p className="text-xs text-quip-teal">Loading the next round now...</p>
            )}
            {transitionError && (
              <div className="mt-2 text-sm text-red-600">
                {transitionError}
                {/* Error is automatically retryable via hook */}
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  // Loading state
  if (!roundData) {
    return (
      <>
        {overlay}
        <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
          <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
        </div>
      </>
    );
  }

  // Main round UI
  return (
    <>
      {overlay}
      <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
          {/* ... Timer, Instructions, Prompt display ... */}

          {error && <div className="mb-4 p-4 bg-red-100">{error}</div>}

          <form onSubmit={handleSubmit} className="space-y-4">
            <input
              type="text"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              placeholder="Enter your phrase"
              disabled={isExpired || isSubmitting}
              maxLength={100}
            />

            <button type="submit" disabled={!canSubmit}>
              {disabledReason || 'Submit Phrase'}
            </button>
          </form>

          <button onClick={navigateHome} disabled={isSubmitting}>
            {isInPartyMode ? 'Exit Party Mode' : 'Back to Dashboard'}
          </button>
        </div>
      </div>
    </>
  );
};
```

**Party-Specific Code**: <15 lines (all in hook usage)

---

## Code Reduction Summary

### Total Lines Removed

| Refactoring | Lines Saved Per Page | Pages | Total Saved |
|-------------|---------------------|-------|-------------|
| usePartyRoundOverlay | ~30 | 3 | ~90 |
| useRoundSubmissionFlow | ~40 | 3 | ~120 |
| useRoundSubmission | ~15 | 3 | ~45 |
| Simplified logic | ~10 | 3 | ~30 |
| **Total** | | | **~285 lines** |

### New Hook Code

| Hook | Lines | Reusable? |
|------|-------|-----------|
| usePartyRoundOverlay | ~60 | ✅ All pages |
| useRoundSubmissionFlow | ~80 | ✅ All pages |
| useRoundSubmission | ~30 | ✅ All pages |
| **Total** | ~170 | |

**Net Savings**: 285 - 170 = **115 lines** + massive maintainability improvement

---

## Success Criteria

- [ ] All 3 round pages use `usePartyRoundOverlay`
- [ ] All 3 round pages use `useRoundSubmissionFlow`
- [ ] Party-specific code reduced to <15 lines per page
- [ ] No duplicate success message handling
- [ ] No duplicate overlay rendering
- [ ] All tests pass
- [ ] Party and normal modes work identically

---

## Next Steps

After completing Phase 5:

1. ✅ Review each round page: should be very similar structure
2. ✅ Check for any remaining duplication
3. ✅ Document the hook patterns for future features
4. ➡️ Proceed to [Phase 6: Testing](./phase-6-testing.md)

---

## Estimated Time

- **Create usePartyRoundOverlay**: 1.5 hours
- **Create useRoundSubmissionFlow**: 1.5 hours
- **Create useRoundSubmission**: 30 minutes
- **Refactor 3 round pages**: 1.5 hours
- **Testing**: 1 hour
- **Total**: **4-5 hours**

---

## Notes

This phase is **optional** but provides significant long-term benefits:
- Easier to add new round types or game modes
- Clear patterns for new developers
- Minimal surface area for bugs (logic in one place)
- Future-proof architecture

If time is limited, Phases 1-4 provide the critical functionality. Phase 5 is the "polish" that makes the codebase exemplary.
