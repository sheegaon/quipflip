# Fix: Display Generated Usernames for Deleted Users

## Problem
On the VoteRound results screen (View Details section), deleted users are shown as "Deleted User #..." which looks unprofessional and breaks immersion.

## Solution
Generate fun, themed usernames for deleted users using the existing username pool system, similar to how guest accounts get usernames.

## Implementation Plan

### 1. Create Frontend Username Generator Utility
**File**: `frontend/src/utils/usernameGenerator.ts`

This utility will:
- Port a subset of the username pool from the backend (`backend/data/username_pool.py`)
- Use a deterministic hash function based on user ID to consistently generate the same username for the same deleted user
- Export a helper function to detect and replace "Deleted User #..." patterns

**Key Functions**:
```typescript
// Generates a username deterministically from a user ID
function generateUsernameFromId(userId: string): string

// Detects "Deleted User #..." pattern and replaces with generated name
function formatUsername(username: string, userId: string): string
```

**Username Pool to Port**:
- Use the same `BASE_USERNAMES`, `PREFIXES`, `SUFFIXES`, and `THREE_WORD_SUFFIXES` arrays from the backend
- Build the pool using the same logic (prefix + suffix combinations)
- Use a simple hash function to deterministically select from the pool based on user ID

### 2. Update VoteRound.tsx
**File**: `frontend/src/pages/VoteRound.tsx`

**Changes needed**:

#### Import the utility (line ~12):
```typescript
import { formatUsername } from '../utils/usernameGenerator';
```

#### Update voting results display (line ~282):
Replace:
```typescript
<span className="font-semibold text-ccl-navy">
  {vote.voter_username}
</span>
```

With:
```typescript
<span className="font-semibold text-ccl-navy">
  {formatUsername(vote.voter_username, vote.voter_id)}
</span>
```

### 3. Update PhraseRecapCard.tsx (if needed)
**File**: `frontend/src/components/PhraseRecapCard.tsx`

If contributors in the "The Reveal" section also show "Deleted User #...", update line ~50:

Replace:
```typescript
<span className={`text-sm font-semibold ${contributor?.is_you ? 'text-ccl-orange' : 'text-ccl-navy'}`}>
  {contributor?.username || 'Unknown'}
  {contributor?.is_you && ' (you)'}
</span>
```

With:
```typescript
<span className={`text-sm font-semibold ${contributor?.is_you ? 'text-ccl-orange' : 'text-ccl-navy'}`}>
  {contributor?.username ? formatUsername(contributor.username, contributor.player_id) : 'Unknown'}
  {contributor?.is_you && ' (you)'}
</span>
```

## Benefits
1. **Consistent Branding**: Uses the same playful, game-themed usernames as the rest of the app
2. **Deterministic**: Same user ID always generates the same username, maintaining consistency across views
3. **Immersive**: Players see fun usernames like "Echo Hunter" or "Prompt Voyager" instead of "Deleted User #12345"
4. **Reusable**: The utility can be used anywhere else deleted users are displayed

## Example Output
- Before: "Deleted User #a1b2c3d4"
- After: "Signal Keeper" or "Quip Voyager" (deterministically generated from the user ID)

## Testing
1. Delete a test user account
2. Vote on a phraseset where that deleted user was a contributor or voter
3. Check the VoteRound results "View Details" section
4. Verify the deleted user shows a generated username instead of "Deleted User #..."
5. Verify the same deleted user shows the same username consistently across different views
