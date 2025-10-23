# GameContext Migration Guide - Phase 2 Complete

**Date:** 2025-10-23
**Status:** Phase 2 Complete - Stable Actions Implemented

## What Changed

GameContext has been refactored to use stable action references, eliminating the infinite loop bug and simplifying dependency management.

---

## New API Structure

### Before (Old API)
```typescript
const {
  player,
  activeRound,
  pendingResults,
  refreshDashboard,
  logout,
  // ... all mixed together
} = useGame();
```

### After (New API)
```typescript
const { state, actions } = useGame();

// State (read-only)
const { player, activeRound, pendingResults } = state;

// Actions (stable references)
actions.refreshDashboard();
actions.logout();
```

---

## Key Benefits

### 1. Stable References
Actions no longer change reference, so they can be safely used in `useEffect` dependencies:

```typescript
// ❌ Before - causes infinite loops
useEffect(() => {
  refreshDashboard();
}, [refreshDashboard]); // refreshDashboard changes → effect re-runs → loop

// ✅ After - stable reference
useEffect(() => {
  actions.refreshDashboard();
}, [actions]); // actions never changes → effect runs once
```

### 2. Clear Separation
State and actions are clearly separated, making it obvious what's data and what's behavior.

### 3. No More Refs Needed
Components no longer need to create refs to work around dependency issues:

```typescript
// ❌ Before - hacky workaround
const refreshDashboardRef = useRef(refreshDashboard);
useEffect(() => {
  refreshDashboardRef.current = refreshDashboard;
}, [refreshDashboard]);

useEffect(() => {
  refreshDashboardRef.current(); // Use ref to avoid dependency
}, []);

// ✅ After - just use actions directly
useEffect(() => {
  actions.refreshDashboard();
}, [actions]);
```

---

## Migration Steps

### Step 1: Update Component Imports
```typescript
// Before
const {
  player,
  refreshDashboard,
  logout,
} = useGame();

// After
const { state, actions } = useGame();
const { player } = state;
```

### Step 2: Update Action Calls
```typescript
// Before
onClick={() => refreshDashboard()}
onClick={() => logout()}

// After
onClick={() => actions.refreshDashboard()}
onClick={() => actions.logout()}
```

### Step 3: Remove Ref Workarounds
```typescript
// Before
const refreshDashboardRef = useRef(refreshDashboard);
useEffect(() => {
  refreshDashboardRef.current = refreshDashboard;
}, [refreshDashboard]);

// Remove all this code!

// After
// Just use actions directly - no refs needed
```

---

## Legacy Compatibility

For backwards compatibility, we've added `useLegacyGame()`:

```typescript
// This still works (for now)
const { player, refreshDashboard, logout } = useLegacyGame();

// But migrate to new API when possible
const { state, actions } = useGame();
```

**Note:** `useLegacyGame()` will be removed in a future version.

---

## Common Migration Patterns

### Pattern 1: Dashboard Refresh
```typescript
// ❌ Before
const Dashboard = () => {
  const { refreshDashboard } = useGame();

  const refreshDashboardRef = useRef(refreshDashboard);
  useEffect(() => {
    refreshDashboardRef.current = refreshDashboard;
  }, [refreshDashboard]);

  useEffect(() => {
    refreshDashboardRef.current();
  }, []);

  return <div>...</div>;
};

// ✅ After
const Dashboard = () => {
  const { state, actions } = useGame();

  // GameContext auto-refreshes on mount, so you usually don't need this
  // But if you do:
  useEffect(() => {
    actions.refreshDashboard();
  }, [actions]);

  return <div>...</div>;
};
```

### Pattern 2: Conditional Actions
```typescript
// ❌ Before
const Component = () => {
  const { player, refreshBalance } = useGame();

  useEffect(() => {
    if (player?.balance < 100) {
      refreshBalance();
    }
  }, [player, refreshBalance]); // refreshBalance changes → effect re-runs

  return <div>...</div>;
};

// ✅ After
const Component = () => {
  const { state, actions } = useGame();
  const { player } = state;

  useEffect(() => {
    if (player?.balance < 100) {
      actions.refreshBalance();
    }
  }, [player, actions]); // actions is stable → effect only runs when player changes

  return <div>...</div>;
};
```

### Pattern 3: Navigation After Action
```typescript
// ❌ Before
const handleSubmit = async () => {
  await submitPhrase(roundId, phrase);
  setTimeout(() => navigate('/dashboard'), 1500);
};

// ✅ After
const handleSubmit = async () => {
  await submitPhrase(roundId, phrase);
  actions.navigateAfterDelay('/dashboard', 1500);
};
```

---

## Components Migrated

- ✅ **GameContext.tsx** - Fully refactored
- ✅ **Dashboard.tsx** - Migrated to new API
- ⏳ **PromptRound.tsx** - TODO
- ⏳ **CopyRound.tsx** - TODO
- ⏳ **VoteRound.tsx** - TODO

---

## Testing Checklist

After migrating a component, verify:

- [ ] No console errors about missing dependencies
- [ ] No infinite loops (check Network tab for repeated calls)
- [ ] Actions work as expected
- [ ] Navigation works correctly
- [ ] No memory leaks (check with React DevTools Profiler)

---

## Troubleshooting

### Issue: "actions is not defined"
**Solution:** Make sure you're destructuring correctly:
```typescript
// ❌ Wrong
const { actions } = useGame();
const { player } = actions; // Error! player is in state, not actions

// ✅ Correct
const { state, actions } = useGame();
const { player } = state;
```

### Issue: "useEffect dependency warning"
**Solution:** Add `actions` to dependency array:
```typescript
useEffect(() => {
  actions.refreshDashboard();
}, [actions]); // Include actions
```

### Issue: "Component re-renders too often"
**Solution:** Check if you're accidentally creating new objects:
```typescript
// ❌ Creates new object on every render
const data = { ...state };

// ✅ Use state directly
const { player } = state;
```

---

## Next Steps (Phase 3)

1. Migrate round pages to new API
2. Remove local state from round pages
3. Remove hasInitialized refs
4. Centralize round initialization in GameContext
5. Remove useLegacyGame compatibility layer

See [FRONTEND_STATE_MANAGEMENT_REVIEW.md](./FRONTEND_STATE_MANAGEMENT_REVIEW.md) for full roadmap.

---

## Questions?

If you encounter issues or have questions about the migration, refer to:
- [FRONTEND_STATE_MANAGEMENT_REVIEW.md](./FRONTEND_STATE_MANAGEMENT_REVIEW.md) - Full architecture review
- GameContext.tsx - Reference implementation
- Dashboard.tsx - Migrated example
