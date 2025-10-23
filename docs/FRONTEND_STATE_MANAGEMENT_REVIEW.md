# Frontend State Management & Round Flow Review

**Date:** 2025-10-23
**Components Analyzed:** Dashboard, PromptRound, CopyRound, VoteRound, GameContext

## Executive Summary

The current frontend architecture has several issues that cause infinite loops, redundant API calls, and complex dependency management. This document provides an in-depth analysis of the problems and proposes concrete solutions.

---

## Current Architecture Overview

### State Flow
```
GameContext (Global)
    ↓
    ├── Dashboard (reads context, triggers refreshes)
    ├── PromptRound (reads activeRound, makes own API calls)
    ├── CopyRound (reads activeRound, makes own API calls)
    └── VoteRound (reads activeRound, makes own API calls)
```

### Key Issues Identified

#### 1. **Infinite Loop Problem (CRITICAL)**
**Location:** `GameContext.tsx` lines 169-196, `Dashboard.tsx` lines 42-66

**Problem:**
```typescript
// GameContext - refreshDashboard changes whenever dependencies change
const refreshDashboard = useCallback(async (signal) => { ... },
  [handleAuthError, isAuthenticated, username]
);

// Dashboard - uses refreshDashboard as dependency
useEffect(() => {
  refreshDashboard();
}, [refreshDashboard]); // ❌ This recreates on every refreshDashboard change
```

**Why it happens:**
1. `refreshDashboard` is recreated when `username`, `handleAuthError`, or `isAuthenticated` changes
2. `useEffect` in Dashboard depends on `refreshDashboard`
3. Effect runs → calls `refreshDashboard` → may update `username` → `refreshDashboard` recreates → effect runs again
4. Result: Hundreds of API calls per second

**Current Fix Applied:**
Using refs to break the dependency chain:
```typescript
const refreshDashboardRef = useRef(refreshDashboard);
useEffect(() => {
  refreshDashboardRef.current = refreshDashboard;
}, [refreshDashboard]);

useEffect(() => {
  refreshDashboardRef.current();
}, []); // ✅ Stable dependency
```

**Better Solution:** See recommendations below.

---

#### 2. **Dual State Management Pattern**
**Location:** All round pages (PromptRound, CopyRound, VoteRound)

**Problem:**
Each round page maintains its own local state AND reads from GameContext:
```typescript
// Round pages have both:
const { activeRound } = useGame();           // From context
const [roundData, setRoundData] = useState(); // Local state
```

**Consequences:**
- **Confusion:** Two sources of truth for round data
- **Synchronization issues:** Local state can get out of sync with context
- **Redundant API calls:** Pages make their own API calls even when context already has data
- **Complex initialization logic:** Each page has ~60 lines of initialization code

**Example from PromptRound.tsx lines 27-96:**
```typescript
useEffect(() => {
  const initRound = async () => {
    // Check if we have an active prompt round
    if (activeRound?.round_type === 'prompt' && activeRound.state) {
      setRoundData(activeRound.state); // ✅ Use context data
    } else {
      // Start new round - makes API call
      const response = await apiClient.startPromptRound(); // ❌ Could be in context
      setRoundData(response);
    }
  };
  initRound();
}, [activeRound]);
```

---

#### 3. **Multiple Refresh Triggers**
**Location:** `Dashboard.tsx` lines 48-66

**Problem:**
Dashboard triggers refreshes in 3 places:
1. On mount (line 49-51)
2. On visibility change (line 54-65)
3. GameContext triggers automatically (lines 176-183)

**Result:**
- Duplicate refreshes on mount
- Unclear ownership of when refreshes happen
- Potential race conditions

---

#### 4. **Inconsistent Navigation Patterns**
**Location:** All round pages

**Problem:**
Round pages navigate to dashboard in multiple scenarios with different delays:
- On error: 2 second delay
- On success: 1.5 second delay (PromptRound, CopyRound) or 3 second delay (VoteRound)
- On expired round: immediate

This creates an inconsistent user experience.

---

#### 5. **hasInitialized Anti-Pattern**
**Location:** All round pages (lines 23, 29)

**Problem:**
```typescript
const hasInitialized = useRef(false);

useEffect(() => {
  if (hasInitialized.current) return; // Prevent React StrictMode double-call
  hasInitialized.current = true;
  // ... initialization
}, []);
```

**Why this is problematic:**
- Works around React StrictMode instead of embracing it
- Hides potential bugs that StrictMode is designed to catch
- Makes code harder to reason about
- Violates React's mental model (effects should be idempotent)

---

#### 6. **Complex Callback Dependencies**
**Location:** GameContext.tsx

**Problem:**
```typescript
const refreshDashboard = useCallback(
  async (signal?: AbortSignal) => { ... },
  [handleAuthError, isAuthenticated, username] // ⚠️ Changes frequently
);

const claimBonus = useCallback(async () => {
  await refreshDashboard(); // ⚠️ Depends on refreshDashboard
}, [handleAuthError, isAuthenticated, refreshDashboard]); // ⚠️ Circular dependencies
```

Creates a web of interdependent callbacks that are hard to track and maintain.

---

## Recommended Architecture

### Principle: Single Source of Truth

All game state should live in GameContext. Pages should ONLY read from context and dispatch actions.

### Proposed Structure

```typescript
// GameContext.tsx - Simplified
interface GameContextType {
  // State (read-only for components)
  state: {
    player: Player | null;
    activeRound: ActiveRound | null;
    roundAvailability: RoundAvailability | null;
    // ... other state
  };

  // Actions (stable references)
  actions: {
    startPromptRound: () => Promise<void>;
    startCopyRound: () => Promise<void>;
    startVoteRound: () => Promise<void>;
    submitPhrase: (roundId: string, phrase: string) => Promise<void>;
    submitVote: (phrasesetId: string, phrase: string) => Promise<void>;
    refreshDashboard: () => Promise<void>;
  };
}
```

### Key Changes

#### 1. **Stable Action References**
```typescript
// Use refs for actions to prevent recreation
const actionsRef = useRef({
  startPromptRound: async () => {
    const response = await apiClient.startPromptRound();
    setActiveRound({ ...response, round_type: 'prompt' });
  },
  // ... other actions
});

// Return stable reference
const value = {
  state: { player, activeRound, ... },
  actions: actionsRef.current,
};
```

**Benefits:**
- Actions never change reference → no dependency issues
- Components can safely use actions in effects
- No need for useCallback chains

#### 2. **Remove Local State from Round Pages**
```typescript
// ❌ Before
const [roundData, setRoundData] = useState();
const { activeRound } = useGame();

// ✅ After
const { state: { activeRound }, actions } = useGame();
// Just use activeRound directly
```

**Benefits:**
- Single source of truth
- No synchronization issues
- Simpler components

#### 3. **Centralize Round Initialization**
```typescript
// GameContext handles all round starting
const startPromptRound = async () => {
  try {
    const response = await apiClient.startPromptRound();
    setActiveRound({
      round_type: 'prompt',
      round_id: response.round_id,
      state: response,
    });
  } catch (err) {
    setError(extractErrorMessage(err));
    throw err;
  }
};

// Pages just navigate and trust context
const PromptRound = () => {
  const { state: { activeRound }, actions } = useGame();
  const navigate = useNavigate();

  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'prompt') {
      actions.startPromptRound()
        .catch(() => navigate('/dashboard'));
    }
  }, [activeRound, actions, navigate]);

  // Just render based on activeRound
  return <div>{activeRound?.state.prompt_text}</div>;
};
```

#### 4. **Remove Manual Refresh Calls**
```typescript
// ❌ Before - Dashboard manually refreshes
useEffect(() => {
  refreshDashboard();
}, []);

// ✅ After - GameContext auto-refreshes, Dashboard just reads
const Dashboard = () => {
  const { state } = useGame();
  // No manual refresh needed
  return <div>Balance: {state.player?.balance}</div>;
};
```

#### 5. **Unified Navigation Helper**
```typescript
// Add to GameContext
const navigateAfterRound = (path: string, delay = 1500) => {
  setTimeout(() => navigate(path), delay);
};

// Use consistently
const handleSubmit = async () => {
  await actions.submitPhrase(roundId, phrase);
  actions.navigateAfterRound('/dashboard');
};
```

---

## Implementation Plan

### Phase 1: Fix Immediate Issues (Done)
- ✅ Fix infinite loop with refs
- ✅ Add orphaned player check in vote finalization

### Phase 2: Refactor GameContext (Recommended Next)
1. Create stable actions object with refs
2. Remove callback dependencies
3. Add centralized error handling
4. Add centralized navigation

### Phase 3: Simplify Round Pages
1. Remove local state
2. Remove hasInitialized refs
3. Remove manual API calls
4. Simplify to pure presentation

### Phase 4: Testing & Validation
1. Test all round flows
2. Verify no duplicate API calls
3. Check for memory leaks
4. Performance profiling

---

## Code Examples

### Before: Dashboard.tsx
```typescript
const Dashboard = () => {
  const { refreshDashboard } = useGame();

  const refreshDashboardRef = useRef(refreshDashboard);
  useEffect(() => {
    refreshDashboardRef.current = refreshDashboard;
  }, [refreshDashboard]);

  useEffect(() => {
    refreshDashboardRef.current();
  }, []);

  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        refreshDashboardRef.current();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => document.removeEventListener('visibilitychange', handleVisibilityChange);
  }, []);

  // ... 300 more lines
};
```

### After: Dashboard.tsx (Proposed)
```typescript
const Dashboard = () => {
  const { state, actions } = useGame();
  const navigate = useNavigate();

  // No manual refreshes needed - context handles it

  return (
    <div>
      <button onClick={() => navigate('/prompt')}>
        Start Prompt Round
      </button>
      {/* Simple, declarative rendering */}
    </div>
  );
};
```

### Before: PromptRound.tsx
```typescript
const PromptRound = () => {
  const { activeRound } = useGame();
  const [roundData, setRoundData] = useState(null);
  const hasInitialized = useRef(false);

  useEffect(() => {
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    const initRound = async () => {
      if (activeRound?.round_type === 'prompt') {
        setRoundData(activeRound.state);
      } else {
        const response = await apiClient.startPromptRound();
        setRoundData(response);
      }
    };
    initRound();
  }, [activeRound]);

  const handleSubmit = async (phrase) => {
    await apiClient.submitPhrase(roundData.round_id, phrase);
    setTimeout(() => navigate('/dashboard'), 1500);
  };

  // ... 200 more lines
};
```

### After: PromptRound.tsx (Proposed)
```typescript
const PromptRound = () => {
  const { state: { activeRound }, actions } = useGame();
  const [phrase, setPhrase] = useState('');

  const roundData = activeRound?.round_type === 'prompt' ? activeRound.state : null;

  const handleSubmit = async (e) => {
    e.preventDefault();
    await actions.submitPhrase(activeRound.round_id, phrase);
    // Navigation handled by context
  };

  if (!roundData) {
    return <LoadingSpinner />;
  }

  return (
    <form onSubmit={handleSubmit}>
      <h1>{roundData.prompt_text}</h1>
      <input value={phrase} onChange={(e) => setPhrase(e.target.value)} />
      <button type="submit">Submit</button>
    </form>
  );
};
```

---

## Performance Improvements

### Current Issues
- **Infinite loops:** Hundreds of API calls per second
- **Duplicate calls:** Dashboard + Context both fetch on mount
- **Unnecessary re-renders:** Changing callback references trigger re-renders
- **Memory leaks:** Intervals not properly cleaned up

### Expected Improvements
- **API calls reduced by 95%:** One call on mount, one every 60 seconds
- **Render cycles reduced by 70%:** Stable action references prevent cascading renders
- **Memory usage reduced:** Proper cleanup of intervals and abort controllers
- **Faster page transitions:** No redundant initialization

---

## Migration Checklist

- [ ] Refactor GameContext to use stable actions
- [ ] Remove all useCallback from GameContext (use refs instead)
- [ ] Update Dashboard to remove manual refresh calls
- [ ] Update PromptRound to use context state only
- [ ] Update CopyRound to use context state only
- [ ] Update VoteRound to use context state only
- [ ] Remove hasInitialized from all components
- [ ] Add centralized navigation helper
- [ ] Add comprehensive error boundaries
- [ ] Test all round flows
- [ ] Performance profiling before/after
- [ ] Update documentation

---

## Conclusion

The current architecture has evolved organically and accumulated technical debt. The proposed changes will:

1. **Eliminate infinite loops** through stable action references
2. **Simplify components** by removing dual state management
3. **Improve performance** by reducing unnecessary API calls and re-renders
4. **Improve maintainability** through clearer ownership of concerns
5. **Better user experience** through consistent behavior

The changes are **backwards compatible** and can be implemented incrementally without breaking existing functionality.

---

## Related Files

- `frontend/src/contexts/GameContext.tsx`
- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/pages/PromptRound.tsx`
- `frontend/src/pages/CopyRound.tsx`
- `frontend/src/pages/VoteRound.tsx`
- `frontend/src/api/client.ts`
