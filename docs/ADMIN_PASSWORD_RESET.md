# Admin Password Reset Feature

## Overview

Admin feature to reset a user's password by auto-generating an 8-character alphanumeric password (no special characters) for the admin to send to the user.

## Backend Changes

### New Endpoint

**Route:** `POST /admin/players/reset-password`

**Location:** `/backend/routers/admin.py`

### Request Schema

```python
class AdminResetPasswordRequest(BaseModel):
    player_id: Optional[UUID] = None
    email: Optional[EmailLike] = None
    username: Optional[str] = None
```

One of the three identifiers must be provided to find the target player.

### Response Schema

```python
class AdminResetPasswordResponse(BaseModel):
    player_id: UUID
    username: str
    email: EmailLike
    generated_password: str
    message: str
```

The `generated_password` field contains the 8-character alphanumeric password.

### Password Generation

**Utility Function:**
- Location: `/backend/utils/passwords.py`
- Function: `generate_temporary_password(length: int = 8) -> str`
- Character set: Uppercase letters (A-Z), lowercase letters (a-z), digits (0-9)
- Uses Python's `secrets` module for cryptographic randomness
- Default length: 8 characters

### Endpoint Logic

1. Verify admin authentication (existing `is_admin` check)
2. Find target player by player_id, email, or username using `PlayerService`
3. Generate 8-character alphanumeric password
4. Update password using existing `PlayerService.update_password()`
5. Revoke all refresh tokens using `AuthService.revoke_all_refresh_tokens()` to force re-login
6. Return player information and generated password

### Reused Existing Services

- `PlayerService.get_player_by_id()`
- `PlayerService.get_player_by_email()`
- `PlayerService.get_player_by_username()`
- `PlayerService.update_password()`
- `AuthService.revoke_all_refresh_tokens()`

## Frontend Changes

### API Client

**Location:** `/frontend/src/api/client.ts`

Add method:
```typescript
async adminResetPassword(
  payload: { player_id?: string; email?: string; username?: string },
  signal?: AbortSignal,
): Promise<AdminResetPasswordResponse>
```

### TypeScript Types

**Location:** `/frontend/src/api/types.ts`

```typescript
export interface AdminResetPasswordResponse {
  player_id: string;
  username: string;
  email: string;
  generated_password: string;
  message: string;
}
```

### Admin Page UI

**Location:** `/frontend/src/pages/Admin.tsx`

Add new "Password Reset" section positioned between the header and "Account Cleanup" section.

**State management:**
- Search identifier type (email/username)
- Search input value
- Found player data
- Generated password result
- Loading states
- Error/success messages

**UI workflow:**
1. Select search type (email or username)
2. Enter identifier and click "Find Player"
3. Display player overview when found
4. Click "Generate New Password" button
5. Display generated password with copy-to-clipboard functionality
6. Show clear success message

**Design pattern:** Follow existing "Account Cleanup" section styling and structure for consistency.

## Security Considerations

### Authentication & Authorization
- Admin-only endpoint (requires `is_admin` flag)
- All requests require valid authentication token

### Session Management
- Revoke all refresh tokens on password reset
- Forces user to re-login with new password
- Prevents hijacked sessions from remaining active

### Password Generation
- Uses cryptographically secure random number generator (`secrets` module)
- 8-character alphanumeric format balances security and usability
- No special characters for easier communication to users

### Audit Trail
- Log all password reset actions with admin user and target player information
- Include timestamp and success/failure status

## UI Notes

**Section placement:** Between main admin header and "Account Cleanup" section

**Visual hierarchy:**
- Border color: Orange (matches admin panel theme)
- Section title: "Password Reset"
- Clear warnings about action permanence

**Workflow:**
1. Search → 2. Confirm player → 3. Generate → 4. Copy password

**Key UX elements:**
- Disabled state for "Generate New Password" until player is found
- Clear display of generated password in monospace font
- Copy-to-clipboard button for easy password sharing
- Auto-clear search after successful reset
- Success message displays username and email for confirmation
