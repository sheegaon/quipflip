# Admin Panel Enhancement Plan

## Current Implementation (v1)

The Admin panel is accessible from Settings page after password verification.

### How to Access Admin Panel

1. **Log in with an admin-enabled account.** Emails listed in `ADMIN_EMAILS` (see `backend/config.py`) receive `player.is_admin = true` at login (`backend/services/player_service.py`).
2. **Open Settings.** From the Statistics page, use the gear icon in the header to navigate to `/settings`.
3. **Scroll to “Admin Access.”** This tile renders only when `player.is_admin` is true (`frontend/src/pages/Settings.tsx`).
4. **Click “Access Admin Panel.”** A password prompt appears.
5. **Enter the admin password (the `SECRET_KEY`).**
   - Stored in `.env` as `SECRET_KEY=...`
   - Default development value: `dev-secret-key-change-in-production`
6. **Submit to continue.** On success the app routes to `/admin` (`frontend/src/pages/Admin.tsx`).

**Note:** The frontend currently blocks non-admin players from launching the panel, but the backend `GET/PATCH /admin/config` endpoints only require authentication. Hardening these routes to enforce `player.is_admin` server-side remains a priority (see “Security Considerations”).

### Implemented Features
- **Admin Account Gating**
  - Players are marked `is_admin` when their email matches `ADMIN_EMAILS` (`backend/services/player_service.py`).
  - Settings screen hides the admin tile for non-admins (`frontend/src/pages/Settings.tsx`).

- **Password Challenge (Secret Key)**
  - Frontend prompts for the application `SECRET_KEY` before navigating to `/admin`.
  - Endpoint: `POST /admin/validate-password` (`backend/routers/admin.py`) returns `{ "valid": true | false }`.
  - **Gap:** Config endpoints do not yet enforce `is_admin`; see “Security Considerations.”

- **Configuration Editing & Persistence**
  - Live edit toggles in `frontend/src/pages/Admin.tsx` write through to `SystemConfigService`.
  - `system_config` table captures overrides with metadata (`backend/models/system_config.py`).
  - API:
    - `GET /admin/config` — returns merged defaults and overrides.
    - `PATCH /admin/config` — updates one key with schema validation (`backend/routers/admin.py`).

- **Flagged Prompt Moderation**
  - `/admin/flags` lists reports; `/admin/flags/{id}/resolve` confirms or dismisses (`backend/routers/admin.py`).
  - UI at `frontend/src/pages/AdminFlagged.tsx` supports filtering, resolving, and in-app feedback.

- **Account Cleanup**
  - Admins can delete players via `/admin/players` DELETE, which wraps `CleanupService.delete_player`.
  - Admin search is implemented as `/admin/players/search` for quick lookup by email or username.

- **Phrase Validator Sandbox**
  - `POST /admin/test-phrase-validation` lets admins test prompt/copy validation workflows.
  - Results display detailed scoring in the Admin “Phrase Validator” tab (`frontend/src/pages/Admin.tsx`).

- **Configuration Categories**
  - **Economics:** Costs, payouts, balances, limits
  - **Timing:** Round durations, grace periods, vote windows
  - **Validation:** Phrase word/character limits
  - **AI Service:** Provider settings, models, timeouts

---

## Phase 3: Player Management

### Backend Status

**Implemented**
- `GET /admin/players/search` — single-player lookup by email or username; returns `AdminPlayerSummary` (`backend/routers/admin.py`).
- `DELETE /admin/players` — deletes a player after `"DELETE"` confirmation; wraps `CleanupService` (`backend/routers/admin.py`).

**Outstanding**
- Paginated listing endpoint for browsing/filtering players.
- Player detail endpoint (statistics, outstanding rounds, recent activity).
- Balance adjustment endpoint that records admin-authored transactions.
- Server-side audit trail for the above actions.

---

### Frontend Implementation

#### Implemented UI (v1.1)
- Account cleanup tile on `/settings` for admins only (`frontend/src/pages/Settings.tsx`).
- Admin panel “Account Cleanup” flow with search, confirmation, and deletion feedback (`frontend/src/pages/Admin.tsx`).

#### Remaining UI Enhancements
- Paginated player table with sorting & filters (currently only single-record search).
- Player detail drawer/modal showing statistics and recent activity.
- Balance adjustment workflow with preview and audit note.
- Batch actions (reset tutorial, force logout) once backend endpoints exist.

---

## Phase 4: System Monitoring

> **Status:** Not implemented. No `/admin/stats` or `/admin/activity` endpoints exist in `backend/routers/admin.py`.

### Backend Requirements

**Endpoint:** `GET /admin/stats`
- Returns system-wide statistics:
  - Total players
  - Active players (last 24h, last 7d, last 30d)
  - Total phrasesets (pending, active, completed)
  - Total rounds (by type and status)
  - AI backup status
  - Database size
  - Cache hit rate (if Redis)

**Endpoint:** `GET /admin/activity`
- Query params: `{ since?: timestamp, limit?: number }`
- Returns recent activity stream:
  - New players registered
  - Rounds started/completed
  - Phrasesets finalized
  - Errors/exceptions
  - Config changes
  - Admin actions

---

### Frontend Implementation

#### System Dashboard
- Real-time statistics cards
- Active players count
- Rounds in progress
- Pending phrasesets
- System health indicators

#### Activity Feed
- Live stream of recent events
- Filterable by event type
- Auto-refresh every 30s
- Timestamp display
- Event details expansion

#### Performance Metrics
- Charts showing:
  - Player registrations over time
  - Active users over time
  - Round completion rates
  - Average round times
  - AI backup frequency
- Date range selector

---

## Phase 5: Data Management

### Bulk Operations

**Endpoint:** `POST /admin/bulk/adjust-balances`
- Adjust balances for multiple players
- CSV upload or selection from player list
- Preview changes before applying
- Create batch transaction records

**Endpoint:** `POST /admin/bulk/delete-players`
- Delete multiple test accounts at once
- Confirmation required
- Progress indicator
- Summary report

**Endpoint:** `POST /admin/bulk/reset-tutorials`
- Reset tutorial for selected players
- Useful for testing or support

---

### Database Maintenance

**Endpoint:** `POST /admin/maintenance/cleanup`
- Run cleanup tasks:
  - Delete abandoned rounds older than X days
  - Archive old transactions
  - Clean up orphaned records
  - Vacuum database (PostgreSQL)
- Returns cleanup summary

**Endpoint:** `GET /admin/maintenance/status`
- Last cleanup timestamp
- Database size
- Pending cleanup items count

---

## Phase 6: Security & Permissions

### Role-Based Access Control (RBAC)

**Database Changes:**
- Add `role` column to `player` table
  - Values: `'player'`, `'admin'`, `'super_admin'`
- Add `permissions` table for granular control

**Permission Levels:**
- **Player:** Normal user access
- **Admin:** View config, view players, basic monitoring
- **Super Admin:** Edit config, manage players, bulk operations

**Backend:**
- Add `@require_role("admin")` decorator to admin endpoints
- Middleware to check role on each request
- JWT token includes role claim

**Frontend:**
- Show/hide admin features based on role
- Role displayed in header when in admin panel
- Conditional rendering of edit/delete buttons

---

### Audit Logging

**Create `admin_audit_log` Table:**
```sql
CREATE TABLE admin_audit_log (
  id SERIAL PRIMARY KEY,
  timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
  admin_player_id VARCHAR(100) NOT NULL,
  admin_username VARCHAR(100) NOT NULL,
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50),  -- 'config', 'player', 'system'
  resource_id VARCHAR(100),
  details JSON,  -- Old value, new value, reason, etc.
  ip_address VARCHAR(45)
);
```

**Log All Admin Actions:**
- Configuration changes
- Player balance adjustments
- Player deletions
- Bulk operations
- System maintenance

**Frontend:**
- Audit log viewer in admin panel
- Filter by action type, admin, date range
- Export audit logs to CSV

---

## Phase 7: Advanced Features

### AI Service Management

**Monitor AI Usage:**
- Total AI calls (by provider)
- Success/failure rates
- Average response times
- Cost tracking (if using paid APIs)

**AI Controls:**
- Enable/disable AI backup system
- Switch between OpenAI/Gemini
- Adjust backup delay
- View AI-generated content

---

### Feature Flags

**Database Table:**
```sql
CREATE TABLE feature_flags (
  flag_name VARCHAR(100) PRIMARY KEY,
  enabled BOOLEAN NOT NULL DEFAULT FALSE,
  description TEXT,
  updated_at TIMESTAMP,
  updated_by VARCHAR(100)
);
```

**Examples:**
- `enable_daily_bonus`
- `enable_ai_backup`
- `enable_new_quest_system`
- `maintenance_mode`

**Frontend:**
- Toggle switches for each feature flag
- Preview mode (enable for specific users)
- Rollout percentage slider

---

### System Announcements

**Create `announcements` Table:**
```sql
CREATE TABLE announcements (
  id SERIAL PRIMARY KEY,
  message TEXT NOT NULL,
  type VARCHAR(20) NOT NULL,  -- 'info', 'warning', 'error', 'maintenance'
  active BOOLEAN NOT NULL DEFAULT TRUE,
  start_date TIMESTAMP,
  end_date TIMESTAMP,
  created_by VARCHAR(100),
  created_at TIMESTAMP DEFAULT NOW()
);
```

**Admin Interface:**
- Create/edit/delete announcements
- Schedule announcements
- Preview before publishing

**User-Facing:**
- Banner at top of dashboard
- Dismiss button (stores in localStorage)
- Auto-hide after end_date

---

## Implementation Priority

### Phase 2: Configuration Editing (High Priority)
**Effort:** 2-3 weeks
- Most requested admin feature
- Enables rapid game balancing
- Critical for production management

### Phase 3: Player Management (High Priority)
**Effort:** 2 weeks
- Essential for support and troubleshooting
- Balance adjustments common need
- Test account cleanup important

### Phase 4: System Monitoring (Medium Priority)
**Effort:** 2 weeks
- Important for production health
- Helps identify issues early
- Nice-to-have for launch

### Phase 5: Data Management (Medium Priority)
**Effort:** 1-2 weeks
- Useful for bulk operations
- Not critical for launch
- Can be added iteratively

### Phase 6: Security & Permissions (High Priority if Multi-Admin)
**Effort:** 2-3 weeks
- Critical if multiple admins
- Can defer if single admin
- Audit logging very valuable

### Phase 7: Advanced Features (Low Priority)
**Effort:** 3-4 weeks
- Nice-to-have enhancements
- Can be added over time
- Feature flags valuable for safe releases

---

## Security Considerations

### Authentication
- All admin endpoints require authentication
- Re-verify password for destructive actions
- Session timeout for admin panel
- Logout on sensitive operations

### Authorization
- Role-based access control
- Principle of least privilege
- Audit all admin actions
- IP whitelisting (optional)
- Enforce `player.is_admin` (and ideally an admin session token) on `GET/PATCH /admin/config` and `/admin/test-phrase-validation`, which currently only require authentication.

### Data Protection
- Sanitize all inputs
- Prevent SQL injection (use parameterized queries)
- Rate limiting on admin endpoints
- CSRF protection

### Monitoring
- Alert on suspicious admin activity
- Track failed admin login attempts
- Monitor for unusual config changes
- Log all database modifications

---

## Testing Requirements

### Unit Tests
- Admin endpoint authorization
- Configuration validation
- Balance adjustment logic
- Bulk operation safety

### Integration Tests
- Complete admin workflows
- Role-based access control
- Audit log creation
- Error handling

### Security Testing
- Penetration testing
- Authorization bypass attempts
- Input validation
- SQL injection attempts

### Load Testing
- Bulk operations performance
- Concurrent admin users
- Large player list pagination
- Export functionality

---

## UI/UX Guidelines

### Destructive Actions
- Always require confirmation
- Use warning colors (red)
- Show preview of impact
- Provide undo option when possible

### Bulk Operations
- Show progress indicator
- Allow cancellation mid-operation
- Provide detailed summary report
- Handle partial failures gracefully

### Responsive Design
- Admin panel should work on tablets
- Consider mobile-friendly views
- Keyboard shortcuts for power users
- Optimize for large datasets

### Error Handling
- Clear error messages
- Recovery suggestions
- Contact support option
- Automatic error reporting

---

## Deployment Considerations

### Rollout Strategy
1. Deploy read-only admin panel (v1) ✅
2. Add configuration editing (v2)
3. Add player management (v2.1)
4. Add monitoring and audit logs (v2.2)
5. Add advanced features iteratively

### Monitoring
- Track admin panel usage
- Monitor performance impact
- Alert on errors
- Gather user feedback

### Documentation
- Admin user guide
- API documentation
- Security best practices
- Troubleshooting guide

**Total Estimated Time:** 12-16 weeks for complete implementation
