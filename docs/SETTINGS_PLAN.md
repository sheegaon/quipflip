# Settings Page Enhancement Plan

## Current Implementation (v1)

The Settings page is accessible from the Statistics page and provides:

### Implemented Features
- **Account Information Display** (Read-only)
  - Username, email, pseudonym
  - Account creation date
  - Last login date
  - Outstanding prompts count

- **Balance Information** (Read-only)
  - Current balance
  - Starting balance

- **Tutorial Management** (Functional)
  - Reset tutorial button
  - Uses existing `POST /player/tutorial/reset` endpoint

- **Admin Access** (Functional)
  - Password-protected link to Admin panel
  - Validates current user password via login endpoint

- **Future Features Preview**
  - Grayed-out section showing coming soon features

---

## Phase 2: Account Management (Completed)

Phase 2 shipped in the Phase 2 settings work and is live in the current build. The following
features were delivered end-to-end across the backend and frontend:

### Change Password
**Shipped Functionality:**
- `POST /player/password` endpoint validates the current password, applies the strengthened
  password policy, and rotates active credentials after a successful change.
- Settings page now includes current/new/confirm password inputs with matching client-side
  validation and inline error messaging.

### Change Email Address
**Shipped Functionality:**
- `PATCH /player/email` endpoint verifies the caller's password, enforces uniqueness, and
  returns the updated player profile.
- Settings UI contains an email update form that surfaces validation errors (format or
  duplication) and refreshes the displayed account info on success.

### Delete Account
**Shipped Functionality:**
- `DELETE /player/account` endpoint reuses the centralized cleanup service to remove the player
  and all associated data after verifying the password and a "DELETE" confirmation token.
- The frontend implements the multi-step confirmation modal, collects the password, clears
  local auth state, and routes back to the landing page when the deletion succeeds.

### Administrative Controls
**Shipped Functionality:**
- Admins can search for any account via `GET /admin/players/search` and trigger the same
  cleanup workflow through `DELETE /admin/players`, both of which now enforce admin-only access
  before performing the lookup or deletion.

---

## Phase 3: Data Export & Privacy (GDPR Compliance)

### Export Account Data
**Priority:** Medium
**User Story:** As a player, I want to download all my account data for record-keeping.

**Backend Requirements:**
- Create `GET /player/export` endpoint
- Generate JSON/CSV export containing:
  - Player profile data
  - All phrasesets (prompts, copies, votes)
  - Transaction history
  - Quest history
  - Statistics
  - Tutorial progress
- Return downloadable file or JSON response

**Frontend Implementation:**
- "Export Data" button in Settings
- Choose format (JSON/CSV)
- Download file with timestamp
- Loading indicator during export generation

---

## Phase 4: Preferences & Customization

### Notification Preferences
**Priority:** Low
**User Story:** As a player, I want to control what notifications I receive.

**Backend Requirements:**
- Add preferences columns to `player` table:
  - `email_notifications_enabled: bool`
  - `result_notifications: bool`
  - `quest_notifications: bool`
  - `daily_bonus_reminders: bool`
- Create `PATCH /player/preferences` endpoint
- Return updated preferences

**Frontend Implementation:**
- Add "Notification Preferences" section
- Toggle switches for each preference type
- Save preferences button
- Auto-save on toggle (optional)

---

### Display Preferences
**Priority:** Low
**User Story:** As a player, I want to customize my display preferences.

**Potential Options:**
- Dark mode toggle
- Color scheme preferences
- Font size adjustment
- Animation/transition speed
- Compact/spacious layout mode

**Backend Requirements:**
- Add `display_preferences: JSON` column to player table
- Store preferences as JSON object
- Create `PATCH /player/display-preferences` endpoint

**Frontend Implementation:**
- Add "Display" section in Settings
- Various toggle/select controls
- Live preview of changes
- Save preferences to backend
- Apply preferences globally via context

---

## Phase 5: Username Change (Complex)

### Change Username
**Priority:** Low (Complex due to pseudonym system)
**User Story:** As a player, I want to change my display username.

**Considerations:**
- Username is visible to the player
- Pseudonym is shown to other players in results
- Changing username doesn't affect game history
- Must maintain uniqueness

**Backend Requirements:**
- Create `PATCH /player/username` endpoint
- Request body: `{ new_username: string, password: string }`
- Validate uniqueness
- Enforce username requirements (length, characters)
- Password verification for security
- Return updated player data

**Frontend Implementation:**
- Add username change form
- Availability check (real-time or on blur)
- Password verification
- Preview new username
- Success notification

---

## UI/UX Improvements

### Mobile Responsiveness
- Ensure all forms work well on mobile
- Stack fields vertically on small screens
- Touch-friendly buttons and inputs

### Accessibility
- Proper ARIA labels for all form fields
- Keyboard navigation support
- Screen reader friendly
- High contrast mode support

### Error Handling
- Clear, actionable error messages
- Field-level validation feedback
- Recovery suggestions for common errors

### Loading States
- Skeleton loaders for initial page load
- Button loading states during actions
- Optimistic UI updates where appropriate

---

## Security Considerations

### Authentication
- All sensitive operations require password re-entry
- Session timeout after inactivity
- Logout on password change

### Data Protection
- HTTPS only in production
- Rate limiting on sensitive endpoints
- Input sanitization and validation
- SQL injection prevention (already handled by SQLAlchemy)

### Audit Logging
- Log all account changes (password, email, deletion)
- Store IP address and timestamp
- Create audit trail table in database

---

## Testing Requirements

### Unit Tests
- Form validation logic
- API error handling
- State management

### Integration Tests
- Complete flows (e.g., change password end-to-end)
- Backend endpoint integration
- Error scenarios

### User Acceptance Testing
- Real user testing of sensitive flows
- Usability testing for forms
- Accessibility testing

---

## Implementation Priority

1. **Phase 2 - Account Management** (Change Password, Change Email)
   - Essential security and account management features
   - 2-3 weeks development time

2. **Phase 3 - Data Export** (GDPR Compliance)
   - Important for legal compliance
   - 1 week development time

3. **Phase 4 - Preferences** (Nice to have)
   - Improves user experience
   - 1-2 weeks development time

4. **Phase 5 - Username Change** (Optional)
   - Lower priority, more complex
   - 1 week development time

**Total Estimated Time:** 5-7 weeks for complete implementation
