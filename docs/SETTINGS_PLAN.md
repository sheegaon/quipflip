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

## Phase 2: Account Management (Backend Required)

### Change Password
**Priority:** High
**User Story:** As a player, I want to change my password for security reasons.

**Backend Requirements:**
- Create `POST /player/password` endpoint
- Request body: `{ current_password: string, new_password: string }`
- Validate current password matches
- Enforce password requirements (min length, complexity)
- Return success/error response

**Frontend Implementation:**
- Add password change form to Settings page
- Current password field (for verification)
- New password field
- Confirm new password field
- Client-side validation matching backend rules
- Success/error notifications

---

### Change Email Address
**Priority:** High
**User Story:** As a player, I want to update my email address.

**Backend Requirements:**
- Create `PATCH /player/email` endpoint
- Request body: `{ new_email: string, password: string }`
- Validate password for security
- Check email uniqueness (not already taken)
- Optional: Send verification email to new address
- Return updated player data

**Frontend Implementation:**
- Add email change form to Settings page
- New email input field
- Password field (for verification)
- Email format validation
- Handle uniqueness errors gracefully
- Success notification with updated email display

---

### Delete Account
**Priority:** Medium
**User Story:** As a player, I want to permanently delete my account and all associated data.

**Backend Requirements:**
- Create `DELETE /player/account` endpoint
- Request body: `{ password: string, confirmation: string }`
- Validate password
- Use existing `CleanupService.cleanup_test_players()` logic
- Delete cascading:
  - All votes
  - All transactions
  - All daily bonuses
  - All result views
  - All abandoned prompts
  - All prompt feedback
  - All phraseset activities
  - All refresh tokens
  - All quests
  - All rounds
  - Player record
- Return success response
- Clear all session tokens

**Frontend Implementation:**
- Add "Delete Account" section (separate, warning-styled)
- Multi-step confirmation process:
  1. "Delete Account" button (red/warning)
  2. Modal with explanation of consequences
  3. Password input for verification
  4. Type "DELETE" to confirm
  5. Final confirmation button
- On success:
  - Clear local storage
  - Navigate to landing page
  - Show farewell message

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
