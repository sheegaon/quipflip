# Migration Guide: Transitioning to a True Claim-to-Receive System

## Overview

This document provides a roadmap for transitioning from **Option A** (current: auto-pay at finalization) to **Option B** (true claim-to-receive system where players must explicitly claim their earnings).

**Current State (Option A):**
- Payouts are automatically added to player balance when phraseset is finalized
- UI shows "automatically added" messaging
- `result_viewed` flag tracks whether player has viewed results (not whether they claimed money)
- Claim endpoint exists but doesn't distribute money (just toggles flag)

**Desired State (Option B):**
- Payouts are NOT automatically added at finalization
- Players must explicitly click "Claim" button to receive their earnings
- `payout_claimed` flag accurately tracks whether money was claimed
- Creates engagement moment and drives players back to view results

## Benefits of Option B

1. **Better Engagement**: Clicking "Claim" creates a satisfying reward moment
2. **Retention Driver**: "You have unclaimed earnings!" notifications bring players back
3. **Player Awareness**: Ensures players know what they earned and why
4. **Analytics**: Clear tracking of when players are aware of earnings vs. auto-distributed
5. **Game Feel**: Makes earning feel more tangible and rewarding

## Migration Steps

### Phase 1: Backend Changes

#### 1.1 Modify Finalization to NOT Auto-Pay

**File:** `backend/services/vote_service.py`
**Method:** `_finalize_phraseset()` (lines 650-710)

**Current behavior:**
```python
async def _finalize_phraseset(...):
    # Calculate payouts
    payouts = await scoring_service.calculate_payouts(phraseset)

    # Create prize transactions for each contributor ← THIS AUTO-PAYS
    for role in ["original", "copy1", "copy2"]:
        payout_info = payouts[role]
        if payout_info["player_id"] is not None and payout_info["payout"] > 0:
            await transaction_service.create_transaction(
                payout_info["player_id"],
                payout_info["payout"],
                "prize_payout",
                phraseset.phraseset_id,
                auto_commit=False,
            )
```

**Change to:**
```python
async def _finalize_phraseset(...):
    # Calculate payouts (keep this - we need to know amounts)
    payouts = await scoring_service.calculate_payouts(phraseset)

    # Store payout amounts in ResultView for later claiming
    # Create ResultView entries for all contributors with payout_claimed=False
    for role in ["original", "copy1", "copy2"]:
        payout_info = payouts[role]
        if payout_info["player_id"] is not None:
            # Create or update ResultView with payout amount
            result_view = ResultView(
                view_id=uuid4(),
                phraseset_id=phraseset.phraseset_id,
                player_id=payout_info["player_id"],
                payout_amount=payout_info["payout"],
                payout_claimed=False,
            )
            self.db.add(result_view)

    # DO NOT create transactions here - they'll be created on claim
```

**Note:** This creates ResultView records proactively at finalization instead of on first view.

#### 1.2 Update Claim Endpoint to Distribute Money

**File:** `backend/services/phraseset_service.py`
**Method:** `claim_prize()` (lines 287-333)

**Current behavior:**
```python
async def claim_prize(...):
    # Just toggles flag, doesn't create transaction
    if not result_view.payout_claimed:
        result_view.payout_claimed = True
        result_view.payout_claimed_at = datetime.now(UTC)
        await self.db.commit()
```

**Change to:**
```python
async def claim_prize(...):
    result_view = await self._load_result_view(phraseset, player_id, create_if_missing=True)

    # Check if already claimed
    if result_view.payout_claimed:
        return {
            "success": True,
            "amount": result_view.payout_amount,
            "new_balance": player.balance,
            "already_claimed": True,
        }

    # Create transaction to add money to balance
    transaction_service = TransactionService(self.db)
    await transaction_service.create_transaction(
        player_id,
        result_view.payout_amount,
        "prize_payout",
        phraseset.phraseset_id,
        auto_commit=False,
    )

    # Mark as claimed
    result_view.payout_claimed = True
    result_view.payout_claimed_at = datetime.now(UTC)
    if not result_view.first_viewed_at:
        result_view.first_viewed_at = datetime.now(UTC)

    await self.db.commit()

    # Refresh player to get new balance
    await self.db.refresh(player)

    # Invalidate cache
    self._invalidate_contributions_cache(player_id)

    return {
        "success": True,
        "amount": result_view.payout_amount,
        "new_balance": player.balance,
        "already_claimed": False,
    }
```

#### 1.3 Update get_phraseset_results

**File:** `backend/services/vote_service.py`
**Method:** `get_phraseset_results()` (lines 740-862)

**Current behavior:**
```python
# Creates ResultView with payout_claimed=False (from Option A fix)
result_view = ResultView(
    ...
    payout_claimed=False,
    ...
)
```

**Change to:**
```python
# For Option B: Don't auto-create ResultView here
# It should already exist from finalization
# If it doesn't exist, create it but don't mark as claimed
result_view = result.scalar_one_or_none()
if not result_view:
    # Fallback: calculate and create if missing
    scoring_service = ScoringService(self.db)
    payouts = await scoring_service.calculate_payouts(phraseset)
    player_payout = 0
    for payout_info in payouts.values():
        if payout_info["player_id"] == player_id:
            player_payout = payout_info["payout"]
            break

    result_view = ResultView(
        view_id=uuid.uuid4(),
        phraseset_id=phraseset_id,
        player_id=player_id,
        payout_amount=player_payout,
        payout_claimed=False,  # Not claimed yet!
        first_viewed_at=datetime.now(UTC),
        payout_claimed_at=None,
    )
    self.db.add(result_view)
    await self.db.commit()
else:
    # Update first_viewed_at if this is first view
    if not result_view.first_viewed_at:
        result_view.first_viewed_at = datetime.now(UTC)
        await self.db.commit()
```

### Phase 2: Frontend Changes

#### 2.1 Re-enable Claim Button in Results.tsx

**File:** `frontend/src/pages/Results.tsx`

**Restore claim functionality:**
```typescript
const [claiming, setClaiming] = useState(false);
const [showClaimAnimation, setShowClaimAnimation] = useState(false);

const handleClaim = async () => {
  if (!selectedPhrasesetId || claiming) return;

  try {
    setClaiming(true);
    setShowClaimAnimation(true);
    await apiClient.claimPhrasesetPrize(selectedPhrasesetId);

    // Refresh dashboard and results
    await refreshDashboard();

    // Refresh the current results to update the claimed status
    const data = await apiClient.getPhrasesetResults(selectedPhrasesetId);
    setResults(data);

    // Hide animation after a short delay
    setTimeout(() => {
      setShowClaimAnimation(false);
    }, 1000);
  } catch (err) {
    setError(extractErrorMessage(err) || 'Unable to claim the payout. Please try again.');
    setShowClaimAnimation(false);
  } finally {
    setClaiming(false);
  }
};
```

**Update UI:**
```tsx
{results.already_collected ? (
  <p className="text-sm text-quip-teal mt-3 italic">
    ✓ Payout claimed
  </p>
) : (
  <button
    onClick={handleClaim}
    disabled={claiming}
    className="mt-4 w-full bg-quip-turquoise hover:bg-quip-teal disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm inline-flex items-center justify-center gap-2"
  >
    {claiming ? (
      <>
        <img src="/flipcoin.png" alt="" className="w-6 h-6 balance-flip-active" />
        Claiming...
      </>
    ) : (
      <>
        <img src="/flipcoin.png" alt="" className="w-6 h-6" />
        Claim {results.your_payout} FC
      </>
    )}
  </button>
)}
```

#### 2.2 Update Dashboard Messaging

**File:** `frontend/src/pages/Dashboard.tsx`

**Change back from "earned" to "to claim":**
```tsx
{totalUnclaimedCount > 0 && (
  <p>
    {unclaimedPromptCount} prompt{unclaimedPromptCount === 1 ? '' : 's'} •
    {unclaimedCopyCount} cop{unclaimedCopyCount === 1 ? 'y' : 'ies'} •
    <CurrencyDisplay amount={totalUnclaimedAmount} iconClassName="w-3 h-3" textClassName="text-sm" /> to claim
  </p>
)}

<button
  onClick={handleViewResults}
  className="..."
>
  {totalUnclaimedCount > 0 ? 'View & Claim' : 'View Results'}
</button>
```

#### 2.3 Restore Claim in Tracking Page

**File:** `frontend/src/pages/Tracking.tsx`

Re-add:
```typescript
const { getPlayerPhrasesets, getPhrasesetDetails, claimPhrasesetPrize } = actions;
const claiming = getLoadingState('claim')?.isLoading || false;

const handleClaim = async (phrasesetId: string) => {
  setLoading('claim', {
    isLoading: true,
    type: 'submit',
    message: 'Claiming your prize...'
  });

  try {
    await claimPhrasesetPrize(phrasesetId);
    await Promise.all([
      fetchDetails(selectedSummary),
      fetchPhrasesets(),
    ]);
    setError(null);
  } catch (err) {
    const errorMessage = getActionErrorMessage('claim-prize', err);
    setError(errorMessage);
  } finally {
    clearLoading('claim');
  }
};
```

**Update summary card:**
```tsx
<div className="tile-card p-4 bg-quip-turquoise bg-opacity-10">
  <p className="text-xs uppercase text-quip-teal font-medium">Unclaimed</p>
  <p className="text-lg font-display font-semibold text-quip-turquoise">
    <CurrencyDisplay
      amount={phrasesetSummary.total_unclaimed_amount}
      iconClassName="w-5 h-5"
      textClassName="text-lg font-display font-semibold text-quip-turquoise"
    />
  </p>
</div>
```

**Pass claim handler to PhrasesetDetails:**
```tsx
<PhrasesetDetails
  phraseset={details}
  summary={selectedSummary}
  loading={detailsLoading}
  claiming={claiming}
  onClaim={handleClaim}
/>
```

#### 2.4 Restore Claim Button in PhrasesetDetails

**File:** `frontend/src/components/PhrasesetDetails.tsx`

**Re-add interface props:**
```typescript
interface PhrasesetDetailsProps {
  phraseset: PhrasesetDetailsType | null;
  summary?: PhrasesetSummary | null;
  loading?: boolean;
  claiming?: boolean;
  onClaim?: (phrasesetId: string) => void;
}
```

**Re-add claim section:**
```tsx
const canClaim = phraseset.status === 'finalized' && !phraseset.payout_claimed && phraseset.phraseset_id;

// ... in the render section, before Activity:

{canClaim && (
  <section>
    <button
      onClick={() => phraseset.phraseset_id && onClaim?.(phraseset.phraseset_id)}
      disabled={claiming}
      className="w-full sm:w-auto bg-green-600 hover:bg-green-700 disabled:opacity-60 disabled:cursor-not-allowed text-white font-bold py-2 px-6 rounded-lg"
    >
      {claiming ? 'Claiming…' : `Claim $${phraseset.your_payout ?? 0}`}
    </button>
  </section>
)}
```

**Update payout display:**
```tsx
<div className="bg-green-50 border border-green-200 rounded-lg p-4">
  <p className="text-xs text-green-700 uppercase tracking-wide">Payout</p>
  <p className="text-lg font-semibold text-green-900">
    {phraseset.your_payout != null ? `$${phraseset.your_payout}` : '—'}
  </p>
  <p className="text-xs text-green-700 mt-3 uppercase tracking-wide">Status</p>
  <p className="text-sm font-medium text-green-800">
    {phraseset.payout_claimed ? 'Claimed' : 'Not Claimed'}
  </p>
</div>
```

### Phase 3: Data Migration

#### 3.1 Handle Existing Data

Since we're changing when payouts are distributed, we need to handle existing finalized phrasesets:

**Create migration script:**

```python
# Migration: Backfill ResultView entries for existing finalized phrasesets
from backend.models import Phraseset, Round, ResultView
from backend.services import ScoringService
from datetime import datetime, UTC
from uuid import uuid4


async def backfill_result_views(db):
    """Create ResultView entries for all finalized phrasesets that don't have them."""

    # Get all finalized phrasesets
    result = await db.execute(
        select(Phraseset).where(Phraseset.status == "finalized")
    )
    phrasesets = result.scalars().all()

    scoring_service = ScoringService(db)

    for phraseset in phrasesets:
        # Get contributors
        prompt_round = await db.get(Round, phraseset.prompt_round_id)
        copy1_round = await db.get(Round, phraseset.copy_round_1_id)
        copy2_round = await db.get(Round, phraseset.copy_round_2_id)

        # Calculate payouts
        payouts = await scoring_service.calculate_payouts(phraseset)

        # Create ResultView for each contributor if missing
        for role, payout_info in payouts.items():
            player_id = payout_info["player_id"]
            if not player_id:
                continue

            # Check if ResultView exists
            existing = await db.execute(
                select(ResultView)
                .where(ResultView.phraseset_id == phraseset.phraseset_id)
                .where(ResultView.player_id == player_id)
            )

            if not existing.scalar_one_or_none():
                # Create new ResultView
                # Mark as claimed=True because payout was already distributed in Option A
                result_view = ResultView(
                    view_id=uuid4(),
                    phraseset_id=phraseset.phraseset_id,
                    player_id=player_id,
                    payout_amount=payout_info["payout"],
                    payout_claimed=True,  # Already paid out under old system
                    first_viewed_at=phraseset.finalized_at,  # Approximate
                    payout_claimed_at=phraseset.finalized_at,  # Approximate
                )
                db.add(result_view)

    await db.commit()
```

**Run this migration BEFORE deploying Option B changes** to ensure all existing phrasesets have ResultView entries marked as already claimed.

### Phase 4: Testing

#### 4.1 Test Checklist

- [ ] New phraseset finalizes WITHOUT auto-paying
- [ ] Claim button appears for unclaimed results
- [ ] Clicking claim creates transaction and adds money to balance
- [ ] Balance updates correctly after claim
- [ ] Already-claimed results show "claimed" state
- [ ] Can't claim twice (idempotent)
- [ ] Dashboard shows correct "unclaimed" count
- [ ] Unclaimed count decreases after claiming
- [ ] Analytics track claim events
- [ ] Claim button works on both Results and Tracking pages

#### 4.2 Edge Cases to Test

- Player never claims (ensure no issues)
- Player claims after long delay
- Multiple unclaimed results from same player
- Claim during high concurrency
- Result view missing (fallback creation works)

### Phase 5: Optional Enhancements

Once Option B is working:

1. **Auto-claim after 30 days**: Prevent indefinite unclaimed balances
2. **Push notifications**: "You have $X unclaimed!"
3. **Claim all button**: Batch claim multiple results
4. **Leaderboard**: Show top earners by unclaimed amount
5. **Achievement**: "Claim Collector" for claiming X results

## Rollback Plan

If Option B needs to be rolled back:

1. Revert frontend changes (restore Option A messaging)
2. Revert backend to auto-pay at finalization
3. Mark all unclaimed ResultViews as claimed
4. No data loss - transactions already created during Option B will remain

## Timeline Estimate

- **Phase 1 (Backend)**: 2-3 hours
- **Phase 2 (Frontend)**: 2-3 hours
- **Phase 3 (Migration)**: 1 hour
- **Phase 4 (Testing)**: 2-4 hours
- **Total**: ~1 day of development + testing

## Summary

The API infrastructure for Option B already exists - we just need to:
1. Stop auto-paying at finalization
2. Make the claim endpoint actually distribute money
3. Re-enable claim buttons in UI
4. Update messaging from "earned" back to "to claim"

All the pieces are in place; it's primarily a matter of moving the transaction creation from finalization to the claim endpoint.
