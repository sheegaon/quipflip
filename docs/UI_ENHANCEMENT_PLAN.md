# UI Enhancement Plan

## Overview
This document outlines planned UI/UX improvements for the Quipflip application, focusing on mobile responsiveness, visual polish, navigation improvements, and consistent branding.

---

## 1. Mobile Header Optimization

### Goal
Improve header bar appearance on mobile devices by reducing vertical spacing and scaling down elements.

### Requirements
- **Desktop behavior**: Keep existing header sizing unchanged
- **Mobile behavior**: Apply tighter spacing only on mobile viewports

### Implementation Details

#### Files to Modify
- `frontend/src/components/Header.tsx`

#### Changes
1. **Reduce vertical padding on mobile**
   - Desktop: Keep current `py-3` (0.75rem)
   - Mobile: Change to `py-2` or `py-1.5` using responsive classes (e.g., `py-1.5 md:py-3`)

2. **Scale down elements on mobile**
   - **Logo**:
     - Desktop: `h-12` (current)
     - Mobile: `h-8` or `h-10` (e.g., `h-8 md:h-12`)

   - **Flipcoin icon**:
     - Desktop: `w-10 h-10` (current)
     - Mobile: `w-6 h-6` or `w-8 h-8` (e.g., `w-6 h-6 md:w-10 md:h-10`)

   - **Balance number**:
     - Desktop: `text-3xl` (current)
     - Mobile: `text-xl` or `text-2xl` (e.g., `text-xl md:text-3xl`)

   - **Username button**:
     - Desktop: `text-lg` (current)
     - Mobile: `text-sm` (already responsive: `text-sm md:text-lg`)

   - **Treasure chest icon**:
     - Desktop: `w-10 h-10` (current)
     - Mobile: `w-6 h-6` or `w-8 h-8`

   - **Logout icon**:
     - Desktop: `h-6 w-6` (current)
     - Mobile: `h-5 w-5` (e.g., `h-5 w-5 md:h-6 md:w-6`)

3. **Reduce gap between elements on mobile**
   - Desktop: `gap-4` (current)
   - Mobile: `gap-2` or `gap-3` (e.g., `gap-2 md:gap-4`)

#### Testing Checklist
- [ ] Test on iOS Safari (iPhone)
- [ ] Test on Android Chrome
- [ ] Test on various viewport widths (320px, 375px, 414px, 768px, 1024px)
- [ ] Verify desktop layout remains unchanged
- [ ] Ensure all elements remain visible and clickable
- [ ] Check treasure chest sparkles animation still works

---

## 2. Balance Visual Enhancement

### Goal
Add a subtle box/border around the balance display to make it more prominent and visually contained.

### Requirements
- Box should not overlap with the flipcoin icon
- Should be subtle and theme-consistent
- Should work on both mobile and desktop

### Implementation Details

#### Files to Modify
- `frontend/src/components/Header.tsx`

#### Changes
1. **Wrap balance in a bordered container**
   ```tsx
   // Current structure:
   <div className="flex items-center gap-2 tutorial-balance">
     <img src="/flipcoin.png" />
     <BalanceFlipper value={player.balance} />
   </div>

   // New structure:
   <div className="flex items-center gap-2">
     <img src="/flipcoin.png" />
     <div className="border-2 border-quip-turquoise rounded-tile px-3 py-1">
       <BalanceFlipper value={player.balance} />
     </div>
   </div>
   ```

2. **Design considerations**
   - Border color: `border-quip-turquoise` or `border-quip-teal`
   - Border width: `border-2`
   - Corner style: `rounded-tile` (matches existing tile design)
   - Padding: `px-3 py-1` or adjust for mobile
   - Optional: Add subtle background `bg-quip-turquoise bg-opacity-5`

3. **Keep tutorial-balance class**
   - Move `tutorial-balance` class to outer container to maintain tutorial compatibility

---

## 3. Nomenclature Refactoring: PhrasesetTracking → Tracking

### Goal
Rename "PhrasesetTracking" to "Tracking" throughout the entire codebase for consistency and simplicity.

### Scope
- Page component name
- Route path
- UI labels
- Code comments
- File names
- Import/export statements

### Implementation Details

#### Files to Rename
- `frontend/src/pages/PhrasesetTracking.tsx` → `frontend/src/pages/Tracking.tsx`

#### Files to Modify

**Frontend Files:**
1. `frontend/src/App.tsx` or routing configuration
   - Route path: Consider `/phrasesets` → `/tracking` (check if this breaks existing links)
   - Component import: `import PhrasesetTracking from './pages/PhrasesetTracking'` → `import Tracking from './pages/Tracking'`

2. `frontend/src/pages/Tracking.tsx` (renamed file)
   - Component name: `export const PhrasesetTracking` → `export const Tracking`
   - Page title: Update `<h1>` from "Past Round Tracking" to "Tracking"
   - Update any internal references

3. `frontend/src/pages/Dashboard.tsx`
   - Button text/label: Update any references to phraseset tracking
   - Navigation: Update `navigate('/phrasesets')` → `navigate('/tracking')` (if route changes)

4. `frontend/src/components/` (search for any components that reference this page)
   - Update any links, breadcrumbs, or navigation items

**Backend Files:**
5. Search backend for any endpoint documentation or comments referencing "phraseset tracking"
   - API endpoint paths can remain `/phrasesets` for backward compatibility
   - Update code comments and docstrings

#### Migration Considerations
- **Breaking change**: If route path changes from `/phrasesets` to `/tracking`, existing bookmarks will break
- **Option 1**: Keep route as `/phrasesets` but rename everything else
- **Option 2**: Change route to `/tracking` and add redirect from `/phrasesets` for backward compatibility
- **Recommendation**: Keep route as `/phrasesets` for stability, but rename all UI text and component names

#### Search Pattern
Use grep/search to find all references:
```bash
# Frontend
grep -r "PhrasesetTracking" frontend/src/
grep -r "phraseset" frontend/src/ --ignore-case
grep -r "Past Round Tracking" frontend/src/

# Backend
grep -r "phraseset" backend/ --ignore-case
```

---

## 4. Statistics Icon Next to Username

### Goal
Add a small, custom icon next to the username in the header that visually indicates it's clickable and leads to statistics.

### Requirements
- Icon should be brand-consistent with app's design language
- Should be subtle but noticeable
- Should work on mobile and desktop

### Implementation Details

#### Create New Icon Component
**File:** `frontend/src/components/StatisticsIndicatorIcon.tsx`

```tsx
// Small icon suggesting analytics/statistics
// Design options:
// 1. Small bar chart icon (3 ascending bars)
// 2. Pie chart icon
// 3. Trending up arrow
// 4. Graph/chart symbol
// Recommended: Simple bar chart in quip-teal color with hover effect
```

#### Icon Design Specifications
- **Size**: 16x16px or 20x20px (small, subtle)
- **Colors**:
  - Default: `text-quip-teal` or `text-quip-turquoise`
  - Hover: Brighten or change to `text-quip-navy`
- **Animation**: Subtle scale or color transition on hover
- **Style**: Should match treasure chest icon style (SVG-based, simple shapes)

#### Files to Modify
- `frontend/src/components/Header.tsx`

#### Changes
```tsx
// Current username button:
<button onClick={() => navigate('/statistics')} ...>
  {player.username || username}
</button>

// New username button with icon:
<button onClick={() => navigate('/statistics')} ...>
  <div className="flex items-center gap-1.5">
    <span>{player.username || username}</span>
    <StatisticsIndicatorIcon className="w-4 h-4" />
  </div>
</button>
```

#### Mobile Considerations
- Icon size on mobile: `w-3 h-3 md:w-4 md:h-4`
- Gap between username and icon: `gap-1 md:gap-1.5`

---

## 5. Navigation Back Arrow in Header

### Goal
Replace "Back to Dashboard" buttons with a left arrow icon in the header bar for cleaner navigation.

### Requirements
- Arrow visible on Statistics and Tracking pages only
- Arrow invisible/hidden on Dashboard page
- Arrow navigates to `/dashboard`
- Custom, brand-consistent design

### Implementation Details

#### Create Back Arrow Component
**File:** `frontend/src/components/BackArrowIcon.tsx`

```tsx
// Simple left-pointing arrow icon
// Should match style of other custom icons (treasure chest, stats indicator)
// Design: Clean, rounded arrow pointing left
// Colors: quip-teal or quip-turquoise
```

#### Files to Modify
1. **`frontend/src/components/Header.tsx`**
   - Add back arrow to left side of header (before or after logo)
   - Use `useLocation()` to determine current page
   - Show arrow only when `pathname === '/statistics'` or `pathname === '/tracking'`
   - Position: Either integrated with logo or as separate element on far left

2. **Layout Options:**

   **Option A: Before Logo**
   ```tsx
   <div className="flex items-center gap-2">
     {(pathname === '/statistics' || pathname === '/tracking') && (
       <button onClick={() => navigate('/dashboard')}>
         <BackArrowIcon className="w-6 h-6" />
       </button>
     )}
     <img src="/logo.png" />
   </div>
   ```

   **Option B: Integrated with Logo (flex-start alignment)**
   ```tsx
   <div className="flex items-center gap-3">
     <img src="/logo.png" />
     {(pathname === '/statistics' || pathname === '/tracking') && (
       <button onClick={() => navigate('/dashboard')}>
         <BackArrowIcon className="w-5 h-5" />
       </button>
     )}
   </div>
   ```

3. **`frontend/src/pages/Statistics.tsx`**
   - Remove "Back to Dashboard" button
   - Update layout to remove button container

4. **`frontend/src/pages/Tracking.tsx`** (formerly PhrasesetTracking)
   - Remove "Back to Dashboard" button
   - Update layout to remove button container

#### Mobile Considerations
- Arrow size on mobile: `w-5 h-5 md:w-6 md:w-6`
- Ensure adequate touch target size (min 44x44px on mobile)
- May need padding around button: `p-2` for better touch area

---

## 6. Flipcoin Icon Currency Symbol Replacement

### Goal
Replace "$" with the flipcoin icon throughout the UI for consistent branding.

### Scope
Replace dollar signs in:
- Statistics page
- Tracking page
- Dashboard
- Any other pages showing currency amounts
- Keep backend/API responses using numeric values without symbols

### Implementation Details

#### Create Reusable Currency Display Component
**File:** `frontend/src/components/CurrencyDisplay.tsx`

```tsx
interface CurrencyDisplayProps {
  amount: number;
  iconClassName?: string;
  textClassName?: string;
  showIcon?: boolean;
}

// Renders: [flipcoin icon] 1000
// With flexible styling for different contexts
```

#### Files to Modify
1. **`frontend/src/pages/Statistics.tsx`**
   - Find all instances of `${stats.whatever}` or dollar sign displays
   - Replace with `<CurrencyDisplay amount={stats.whatever} />`
   - Examples:
     - Earnings breakdown
     - Balance displays
     - Total earnings
     - Per-round earnings

2. **`frontend/src/pages/Tracking.tsx`**
   - Replace dollar signs in prize amounts
   - Replace in earnings displays

3. **`frontend/src/pages/Dashboard.tsx`**
   - Replace in round cost displays ("Cost: $100")
   - Replace in unclaimed prizes
   - Note: Header balance already shows flipcoin icon

4. **`frontend/src/components/Header.tsx`**
   - Already uses flipcoin icon for balance (no changes needed)
   - Update daily bonus tooltip if it shows "$"

5. **Search for all `$` in frontend**
   ```bash
   grep -r '\$' frontend/src/pages/ --include="*.tsx"
   grep -r 'dollar' frontend/src/ --include="*.tsx"
   ```

#### Alignment Considerations
- Icon should align vertically with text
- Use flexbox: `flex items-center gap-1`
- Icon size should be proportional to text size
  - Small text (text-sm): 12px icon
  - Medium text (text-base): 16px icon
  - Large text (text-2xl): 24px icon

---

## 7. Currency Nomenclature: "$" → "f" in Documentation

### Goal
Update all documentation to use "f" (for Flipcoins) instead of "$" when referring to currency amounts.

### Scope
- All markdown files in `docs/` folder
- Code comments that reference currency values
- README files
- API documentation

### Implementation Details

#### Files to Check/Modify
1. **`docs/ARCHITECTURE.md`**
   - Find references to dollar amounts
   - Example: "$100 entry fee" → "100f entry fee" or "100 Flipcoins"

2. **`docs/MVP_SUMMARY.md`**
   - Update currency references

3. **`docs/PROJECT_PLAN.md`**
   - Update currency references

4. **`docs/FRONTEND_PLAN.md`**
   - Update currency references

5. **`README.md`** (if exists)
   - Update currency references

6. **Backend code comments**
   - Search Python files for comments mentioning "$" or "dollars"
   - Update to "f" or "Flipcoins"

7. **Frontend code comments**
   - Search TypeScript files for comments mentioning "$" or "dollars"
   - Update to "f" or "Flipcoins"

#### Style Guide
- **In documentation prose**: "100 Flipcoins" (spelled out)
- **In technical specs/tables**: "100f" (abbreviated)
- **In UI**: Show flipcoin icon + number (no text)
- **In code comments**: "100f" or "100 Flipcoins"

#### Search Pattern
```bash
# Documentation
grep -r '\$[0-9]' docs/
grep -r 'dollar' docs/ --ignore-case

# Code comments
grep -r '# .*\$[0-9]' backend/
grep -r '// .*\$[0-9]' frontend/src/
grep -r '/\* .*\$[0-9]' frontend/src/
```

---

## 8. Daily Bonus Progress and Claiming on Statistics Page

### Goal
Show daily bonus status on the statistics page and allow claiming directly from there.

### Requirements
- Display progress toward next daily bonus
- Show claim button if bonus is available
- Update balance and progress after claiming
- Consistent with header treasure chest functionality

### Implementation Details

#### Data Requirements
**Backend Changes:**
1. **Enhance statistics endpoint** (`backend/routers/player.py`)
   - Include daily bonus availability in statistics response
   - Add fields to `PlayerStatistics` schema:
     ```python
     daily_bonus_available: bool
     daily_bonus_amount: int
     last_bonus_claimed: Optional[datetime]
     days_until_next_bonus: int  # 0 if available, 1 if must wait
     ```

2. **Update `StatisticsService`** (`backend/services/statistics_service.py`)
   - Include daily bonus data in `get_player_statistics()`
   - Query `DailyBonus` table for last claim date
   - Calculate days until next bonus

#### Frontend Changes
1. **Update TypeScript interface** (`frontend/src/api/types.ts`)
   ```typescript
   export interface PlayerStatistics {
     // ... existing fields
     daily_bonus_available: boolean;
     daily_bonus_amount: number;
     last_bonus_claimed: string | null;
     days_until_next_bonus: number;
   }
   ```

2. **Update Statistics page** (`frontend/src/pages/Statistics.tsx`)
   - Add new section after header: "Daily Bonus Status"
   - Show progress indicator:
     - If `daily_bonus_available`: Show claim button with treasure chest icon
     - If not available: Show countdown/progress bar
   - Design options:
     - **Card style**: Match existing tile-card design
     - **Position**: Below main header, above charts
     - **Layout**: Horizontal layout with progress on left, claim button on right

3. **Progress Display Options**

   **Option A: Simple Text**
   ```tsx
   {stats.daily_bonus_available ? (
     <div className="tile-card p-4 mb-6 border-2 border-quip-orange">
       <div className="flex items-center justify-between">
         <div className="flex items-center gap-3">
           <TreasureChestIcon className="w-12 h-12" isAvailable={true} />
           <div>
             <p className="font-display font-semibold text-quip-orange-deep">
               Daily Bonus Ready!
             </p>
             <p className="text-sm text-quip-teal">
               Claim {stats.daily_bonus_amount} Flipcoins
             </p>
           </div>
         </div>
         <button onClick={handleClaimBonus} className="...">
           Claim Bonus
         </button>
       </div>
     </div>
   ) : (
     <div className="tile-card p-4 mb-6 border-2 border-quip-teal">
       <div className="flex items-center gap-3">
         <TreasureChestIcon className="w-12 h-12" isAvailable={false} />
         <div>
           <p className="font-display font-semibold text-quip-navy">
             Daily Bonus
           </p>
           <p className="text-sm text-quip-teal">
             {stats.days_until_next_bonus === 0
               ? "Already claimed today"
               : `Available in ${stats.days_until_next_bonus} day(s)`}
           </p>
         </div>
       </div>
     </div>
   )}
   ```

   **Option B: Progress Bar**
   - Show visual progress bar filling up over 24 hours
   - Calculate hours since last claim
   - Display "X hours until next bonus"

4. **Claiming Functionality**
   - Reuse `claimBonus()` from GameContext
   - After successful claim:
     - Refresh statistics data
     - Show success message
     - Update progress display
   - Handle errors appropriately

5. **Integration with Earnings Section**
   - Update earnings breakdown to highlight daily bonus earnings
   - Consider adding a "Daily Bonuses Claimed" counter to frequency section

#### Mobile Considerations
- Stack elements vertically on mobile
- Reduce treasure chest icon size: `w-8 h-8 md:w-12 md:h-12`
- Full-width claim button on mobile

---

## Implementation Priority

### Phase 1: Quick Wins (Low Effort, High Impact)
1. ✅ Remove unused `useEffect` from Landing.tsx (COMPLETED)
2. Flipcoin icon replacement (create `CurrencyDisplay` component, replace dollar signs)
3. Documentation currency nomenclature update ($ → f)
4. Mobile header optimization (responsive classes)

### Phase 2: Medium Effort
5. Balance box enhancement (add border around balance)
6. PhrasesetTracking → Tracking rename (file rename, route update, label changes)
7. Statistics icon next to username (create icon component, integrate)

### Phase 3: Higher Effort
8. Back arrow navigation (create icon, add to header, remove old buttons)
9. Daily bonus on statistics page (backend changes, frontend UI, integration)

---

## Testing Checklist

### Mobile Responsiveness
- [ ] Test all changes on iOS Safari
- [ ] Test all changes on Android Chrome
- [ ] Test at 320px, 375px, 414px, 768px widths
- [ ] Verify touch targets are adequate (min 44x44px)

### Navigation
- [ ] Back arrow works from Statistics page
- [ ] Back arrow works from Tracking page
- [ ] Back arrow hidden on Dashboard
- [ ] Username click navigates to Statistics
- [ ] All existing navigation still works

### Visual Consistency
- [ ] All custom icons match design language
- [ ] Colors are consistent with theme
- [ ] Spacing is consistent across pages
- [ ] Flipcoin icons align properly with text

### Functionality
- [ ] Daily bonus can be claimed from Statistics page
- [ ] Daily bonus can be claimed from header
- [ ] Balance updates correctly after claiming
- [ ] Currency displays show correct amounts
- [ ] Progress indicators work correctly

### Accessibility
- [ ] All buttons have proper labels/titles
- [ ] Color contrast meets WCAG standards
- [ ] Keyboard navigation works
- [ ] Screen reader compatibility

---

## Design Assets Needed

### Custom Icons to Create
1. **StatisticsIndicatorIcon** - Small bar chart or graph symbol
2. **BackArrowIcon** - Left-pointing arrow
3. **TreasureChestIcon** - Already created ✅

### Icon Design Guidelines
- **Format**: SVG
- **Base size**: 24x24px viewBox
- **Style**: Simple, geometric shapes
- **Colors**: Use theme colors as props
- **Consistency**: Match existing TreasureChestIcon style
- **Optimization**: Keep paths simple, avoid complex gradients

---

## Rollback Plan

If any changes cause issues:

1. **Mobile header changes**: Easy to revert responsive classes
2. **Balance box**: Easy to remove border wrapper
3. **Rename refactor**: Git revert or manually restore old names
4. **New icons**: Remove icon imports and restore old buttons
5. **Daily bonus on stats**: Feature flag or conditional rendering

---

## Notes and Considerations

### Performance
- New icons are SVG-based (lightweight, no additional HTTP requests)
- Currency component should be memoized if used frequently
- Statistics page may need loading states for daily bonus data

### Backward Compatibility
- Keep `/phrasesets` route even if renaming page
- Ensure existing bookmarks and links continue working
- Consider adding redirects if changing routes

### Future Enhancements
- Animate flipcoin icon when balance changes
- Add "pulse" animation to available daily bonus
- Consider adding daily bonus streak counter
- Add sound effects for bonus claiming

### Known Limitations
- Daily bonus progress requires datetime calculations
- Mobile header may need different layout on very small screens (<320px)
- Icons may need different designs for dark mode (if planned)

---

## Questions for Clarification

1. **Mobile breakpoint**: At what viewport width should mobile styles kick in? (Current assumption: <768px)
2. **Balance box design**: Prefer border only, or border + subtle background color?
3. **Route path**: Keep `/phrasesets` or change to `/tracking`?
4. **Back arrow position**: Before logo or after logo in header?
5. **Daily bonus progress**: Simple text countdown or visual progress bar?
6. **Currency display**: Always show icon, or sometimes just number?
7. **Statistics icon**: Preferred design (bar chart, pie chart, trend arrow)?

---

## Success Metrics

After implementation, measure:
- Mobile user engagement with statistics page (click-through rate on username)
- Daily bonus claim rate from statistics page vs header
- Bounce rate on Tracking page (should decrease with better navigation)
- Mobile page load time (should remain similar or improve)
- User feedback on new navigation pattern

---

*Document created: 2025-01-XX*
*Last updated: 2025-01-XX*
*Status: Planning Phase*
