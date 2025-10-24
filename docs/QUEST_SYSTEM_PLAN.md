# 🎯 Quest/Bonus System Implementation Plan

## Overview
Comprehensive quest and achievement system with 16 achievement types, progress tracking, claim mechanism, and celebratory UI notifications.

**Implementation Status**: ✅ Backend Complete (100%), 🔄 Frontend UI In Progress (20%)

---

## ✅ Completed Phases (Summary)

### Phases 1-4: Backend Foundation & API ✅ COMPLETE
- **Database Models**: Quest and QuestTemplate tables with all 16 quest types configured
- **Quest Service**: 800+ lines of business logic for all quest types, tier progression, and reward distribution
- **Service Integration**: Quest checks integrated into vote_service, round_service, player_service, and prompt_feedback router
- **API Endpoints**: Full REST API at `/quests` with list, filter, detail, and claim endpoints
- **Frontend Types**: TypeScript interfaces and API client methods for quest data

**Key Files**:
- `backend/models/quest.py` - Quest & QuestTemplate models
- `backend/services/quest_service.py` - Complete business logic (800+ lines)
- `backend/routers/quests.py` - REST API endpoints
- `backend/schemas/quest.py` - Pydantic schemas
- `frontend/src/api/types.ts` (lines 375-410) - TypeScript types
- `frontend/src/api/client.ts` (lines 545-569) - API methods

---

## 🔄 Remaining Implementation

---

## Phase 5: Quest Context & State Management (Frontend State)

### Step 5.1: Create Quest Context
**File**: `frontend/src/contexts/QuestContext.tsx`

```typescript
interface QuestContextType {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  hasClaimableQuests: boolean;  // For treasure chest indicator
  loading: boolean;
  error: string | null;
  refreshQuests: () => Promise<void>;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
  clearError: () => void;
}
```

**Key Features**:
- `hasClaimableQuests` computed property for treasure chest state
- Auto-refresh after quest-eligible actions
- Error handling with user-friendly messages

### Step 5.2: Integrate with GameContext
**File**: `frontend/src/contexts/GameContext.tsx`

**Changes**:
- Import and wrap with QuestProvider
- Call `refreshQuests()` after:
  - Vote submission
  - Round completion (prompt/copy)
  - Daily bonus claim
  - Phraseset finalization
- Update `player` state to include daily_bonus_available flag

**New computed properties**:
```typescript
const hasTreasure = dailyBonusAvailable || hasClaimableQuests;
```

---

## Phase 6: Quest UI Components (Frontend Components)

### Step 6.1: Create Success Notification Component
**File**: `frontend/src/components/SuccessNotification.tsx`

Similar to ErrorNotification but with:
- Green/teal branded color scheme
- Celebration icon (🎉, ⭐, 🎯)
- Auto-dismiss after 5 seconds
- Support for "Quest completed!" messages
- Optional action button (e.g., "View Quests")

### Step 6.2: Create Quest Card Component
**File**: `frontend/src/components/QuestCard.tsx`

Props: `quest: Quest, onClaim?: (questId: string) => void`

**Features**:
- Display quest name, description, reward amount
- Progress bar (current / target)
- Status indicator (active, completed, claimed)
- Claim button for completed quests
- Category badge (streak, quality, activity, milestone)
- Locked/unlocked visual state
- Tier indicators (I, II, III) for progressive quests

**Layout**:
```
┌─────────────────────────────────────┐
│ 🔥 Hot Streak                  $10 │
│ Get 5 correct votes in a row       │
│ ████████░░░░ 3/5                   │
│                          [Active]  │
└─────────────────────────────────────┘
```

### Step 6.3: Create Quest Progress Bar Component
**File**: `frontend/src/components/QuestProgressBar.tsx`

- Animated progress bar with smooth transitions
- Show percentage or "X / Y" format
- Color coding by category:
  - Streak: Orange/red gradient
  - Quality: Purple gradient
  - Activity: Blue gradient
  - Milestone: Gold gradient
- Pulse animation when 80%+ complete

### Step 6.4: Create Quest Category Filter
**File**: `frontend/src/components/QuestCategoryFilter.tsx`

- Tabs for: All, Streaks, Quality, Activity, Milestones
- Show count badge per category
- Filter quest list by category
- Responsive mobile design (horizontal scroll or dropdown)

---

## Phase 7: Quests Page (Frontend Page)

### Step 7.1: Create Quests Page
**File**: `frontend/src/pages/Quests.tsx`

**Layout**:
```
Header with balance
┌─────────────────────────────────────┐
│ 🎁 Quests & Achievements            │
│                                     │
│ ┌─ Daily Bonus ─────────────────┐  │
│ │ $100 Daily Bonus Available!   │  │
│ │ [Claim Daily Bonus] ←────────── │  │
│ └───────────────────────────────┘  │
│                                     │
│ Claimable Rewards: 3 🎉            │
│ Total Rewards Earned: $XXX         │
└─────────────────────────────────────┘

[Category Filter: All | Streaks | Quality | Activity | Milestones]

┌── Claimable Quests ───────────────┐
│ [QuestCard ✅] [QuestCard ✅]     │
└─────────────────────────────────────┘

┌── Active Quests ──────────────────┐
│ [QuestCard] [QuestCard] [QuestCard] │
│ [QuestCard] [QuestCard]             │
└─────────────────────────────────────┘

┌── Claimed Quests ─────────────────┐
│ [QuestCard ✓] [QuestCard ✓]       │
└─────────────────────────────────────┘
```

**Features**:
- **Daily Bonus Section**: Prominent card at top with claim button (moved from Header)
- Real-time progress updates
- Click quest card to expand details
- Claim button for completed quests (updates balance immediately)
- Filter by category
- Sort by: progress, reward amount, completion date
- Empty states with encouraging messages
- Summary stats (total earned, current streak, etc.)

### Step 7.2: Add Route
**File**: `frontend/src/App.tsx`

Add route:
```typescript
<Route path="/quests" element={<Quests />} />
```

---

## Phase 8: Treasure Chest Integration (MODIFIED)

### Changes from Original Plan:
1. **Treasure chest now leads to Quests page** (not just daily bonus)
2. **Treasure chest state indicates available rewards**:
   - **Gold/Available**: When `dailyBonusAvailable || hasClaimableQuests`
   - **Gray/Empty**: When no daily bonus and no claimable quests
3. **Daily bonus claim moved to Quests page** (removed from Header dropdown)

### Step 8.1: Update Treasure Chest Icon Component
**File**: `frontend/src/components/TreasureChestIcon.tsx`

**Current Implementation** (check existing):
- Likely has `isAvailable` prop that controls visual state
- Update to show gold when available, gray when not

**Expected Props**:
```typescript
interface TreasureChestIconProps {
  isAvailable: boolean;  // Gold when true, gray when false
  className?: string;
}
```

**Visual States**:
- **Available (Gold)**: Shiny, animated, inviting
- **Unavailable (Gray)**: Muted, static, clearly empty

### Step 8.2: Update Header Component
**File**: `frontend/src/components/Header.tsx`

**Current State** (from earlier in conversation):
- Treasure chest button exists (lines 123-134)
- Currently shows when `player.daily_bonus_available`
- Clicking calls `handleClaimBonus()` directly

**Required Changes**:
1. **Always show treasure chest** (don't conditionally hide)
2. **Update `isAvailable` prop logic**:
   ```typescript
   const hasTreasure = player.daily_bonus_available || hasClaimableQuests;
   ```
3. **Navigate to `/quests` on click** (remove direct claim logic):
   ```typescript
   onClick={() => navigate('/quests')}
   ```
4. **Remove `handleClaimBonus` function** (moved to Quests page)
5. **Update tooltip**:
   - Available: "View available rewards"
   - Unavailable: "No rewards available"

**Modified Header Code**:
```typescript
{/* Treasure Chest - Always visible */}
<button
  onClick={() => navigate('/quests')}
  className="relative group"
  title={hasTreasure ? "View available rewards" : "No rewards available"}
>
  <TreasureChestIcon
    className="w-7 h-7 md:w-10 md:h-10 transition-transform group-hover:scale-110"
    isAvailable={hasTreasure}
  />
</button>
```

### Step 8.3: Remove Daily Bonus Claim from Header
**File**: `frontend/src/components/Header.tsx`

- Remove `handleClaimBonus` async function
- Remove `isClaiming` state
- Remove `claimBonus` from useGame destructure (if no longer needed in Header)
- Keep treasure chest button always visible

### Step 8.4: Update GameContext
**File**: `frontend/src/contexts/GameContext.tsx`

**Add to context interface**:
```typescript
interface GameContextType {
  // ... existing properties
  hasClaimableQuests: boolean;  // From QuestContext
  claimDailyBonus: () => Promise<void>;  // For Quests page to call
}
```

**Integration**:
- Access QuestContext's `hasClaimableQuests`
- Expose `claimBonus` as `claimDailyBonus` for Quests page
- Ensure `refreshQuests()` is called after daily bonus claim

### Step 8.5: Quest Completion Notifications
**File**: `frontend/src/contexts/GameContext.tsx` or `QuestContext.tsx`

**When quest completes** (status changes active → completed):
- Show SuccessNotification:
  ```
  🎉 Quest Completed!
  [Quest Name] - Earned $[reward]
  [View Quests]
  ```
- Optional: Subtle celebration animation on treasure chest

**Trigger Points**:
- After vote submission (check for completed hot_streak)
- After round completion (check for completed round_completion quests)
- After phraseset finalization (check for quality bonuses)
- After daily login
- Polling/refresh (periodic check for new completions)

---

## Phase 9: Testing & Refinement

### Step 9.1: Frontend Component Tests
**Files**: `frontend/src/components/__tests__/`

Test cases:
- QuestCard rendering for all states (active, completed, claimed)
- QuestProgressBar animation and percentage display
- TreasureChestIcon visual states (gold vs gray)
- SuccessNotification auto-dismiss and actions
- Quest filtering and sorting

### Step 9.2: Integration Testing
- Navigate to Quests page via treasure chest
- Claim daily bonus from Quests page (verify balance update)
- Claim quest rewards (verify balance update and transaction)
- Complete quest and verify notification appears
- Verify treasure chest state changes based on available rewards
- Test with multiple claimable quests

### Step 9.3: Mobile Responsiveness
- Treasure chest icon size on mobile
- Quest cards stack properly
- Category filter works on small screens
- Daily bonus claim button accessible on mobile

### Step 9.4: Edge Cases
- No quests available (empty state)
- All quests claimed (encouraging message)
- Multiple quests complete simultaneously
- Daily bonus + quest rewards both available
- Network errors during claim

---

## Phase 10: Documentation & Polish

### Step 10.1: Update Documentation
**Files**:
- `README.md` - Add quest system overview (player-facing)
- `docs/API.md` - Quest endpoints already documented
- `docs/ARCHITECTURE.md` - Explain treasure chest + quest integration

### Step 10.2: Visual Polish
- Smooth transitions and animations
- Consistent color scheme for quest categories
- Celebration effects for quest completion
- Loading states during claim actions
- Error states with retry options

---

## Implementation Summary

### My Understanding of Changes:

**Original Phase 8**:
- Treasure chest was for daily bonus only
- Clicking opened a modal or claimed directly in header
- Separate navigation link to Quests page

**Modified Phase 8**:
1. **Treasure chest = Gateway to all rewards**
   - Daily bonus + quest rewards both accessed via treasure chest
   - Clicking navigates to `/quests` page

2. **Treasure chest visual state = Reward indicator**
   - Gold/shiny when `dailyBonusAvailable || hasClaimableQuests`
   - Gray/muted when no rewards available
   - Always visible (not conditionally rendered)

3. **Quests page = Unified reward center**
   - Daily bonus claim moved here (prominent card at top)
   - Quest list below daily bonus
   - Single place for all reward claiming

4. **Benefits of this approach**:
   - Cleaner header UI (one button, no claim modal)
   - Clear visual indicator of available rewards
   - Centralized reward experience
   - Encourages quest discovery (players see quests when claiming daily bonus)

### Files to Modify:
1. `frontend/src/components/Header.tsx` - Update treasure chest behavior
2. `frontend/src/components/TreasureChestIcon.tsx` - Ensure gold/gray states work
3. `frontend/src/contexts/GameContext.tsx` - Expose hasClaimableQuests
4. `frontend/src/contexts/QuestContext.tsx` - NEW: Create quest state management
5. `frontend/src/pages/Quests.tsx` - NEW: Create quests page with daily bonus section
6. `frontend/src/components/QuestCard.tsx` - NEW: Quest display component
7. `frontend/src/components/QuestProgressBar.tsx` - NEW: Progress visualization
8. `frontend/src/components/SuccessNotification.tsx` - NEW: Celebration notifications

### Quest Definitions Reference

| Quest Type | Name | Target | Reward | Category | Resets |
|------------|------|--------|--------|----------|---------|
| hot_streak_5 | Hot Streak | 5 correct votes | $10 | Streak | On wrong vote |
| hot_streak_10 | Blazing Streak | 10 correct votes | $25 | Streak | On wrong vote |
| hot_streak_20 | Inferno Streak | 20 correct votes | $75 | Streak | On wrong vote |
| deceptive_copy | Master Deceiver | 75%+ votes to copy | $20 | Quality | Per phraseset |
| obvious_original | Clear Original | 85%+ votes to original | $15 | Quality | Per phraseset |
| round_completion_5 | Quick Player | 5 rounds in 24h | $25 | Activity | 24h window |
| round_completion_10 | Active Player | 10 rounds in 24h | $75 | Activity | 24h window |
| round_completion_20 | Power Player | 20 rounds in 24h | $200 | Activity | 24h window |
| balanced_player | Balanced Player | 1p/2c/10v in 24h | $20 | Activity | 24h window |
| login_streak_7 | Week Warrior | 7 consecutive days | $200 | Streak | On missed day |
| feedback_contributor_10 | Feedback Novice | 10 feedback submissions | $5 | Milestone | Never (one-time) |
| feedback_contributor_50 | Feedback Expert | 50 feedback submissions | $25 | Milestone | Never (one-time) |
| milestone_votes_100 | Century Voter | 100 total votes | $50 | Milestone | Never (one-time) |
| milestone_prompts_50 | Prompt Master | 50 total prompts | $100 | Milestone | Never (one-time) |
| milestone_copies_100 | Copy Champion | 100 total copies | $75 | Milestone | Never (one-time) |
| milestone_phraseset_20votes | Popular Set | First set with 20 votes | $25 | Milestone | Never (one-time) |

---

## Next Steps

**Priority 1**: Phase 8 - Treasure Chest Integration
- Update Header to navigate to /quests
- Update treasure chest state logic
- Ensure always visible with correct gold/gray state

**Priority 2**: Phase 5 - Quest Context
- Create QuestContext with state management
- Integrate with GameContext

**Priority 3**: Phase 7 - Quests Page
- Create page with daily bonus section at top
- Implement claim functionality
- Add quest list display

**Priority 4**: Phase 6 - Quest Components
- Build QuestCard, QuestProgressBar, SuccessNotification
- Implement category filtering

**Priority 5**: Phase 9 & 10 - Testing & Polish
- Integration testing
- Mobile responsiveness
- Visual polish and animations
