# WebSocket Push Notification System - Implementation Plan

## Overview
Establish a persistent WebSocket connection that enables real-time push notifications when HUMAN players interact with phrasesets where the current user participated (as prompt or copy submitter). WebSocket failures will be silent with no REST polling fallback.

## User Experience

### Notification Behavior
- **When**: A human player copies your prompt OR votes on your phraseset
- **Where**: Notifications appear anywhere in the app (global toast system)
- **How**: Brief toast notification slides in from bottom-right
- **Silent Failures**: If WebSocket is unavailable, no notifications appear (no error messages, no fallback)

### Notification Message Format
```
{username} {action} your {role} submission of "{phrase}"
Visit the tracking page for details [TrackingIcon]
```

**Examples:**
- "Alice **copied** your **prompt** submission of \"a dog wearing a hat\""
  Visit the tracking page for details 💡

- "Bob **voted on** your **copy** submission of \"feline fashion show\""
  Visit the tracking page for details 💡

### Notification Interaction
- Auto-dismiss after 5 seconds
- Manual dismiss button (×)
- Click on tracking icon → navigate to `/tracking` page
- Stack max 3 notifications at once

---

## Architecture

### Backend Components

#### 1. Notification Model
**File**: `backend/models/notification.py`

```python
class Notification(Base):
    __tablename__ = "notifications"

    notification_id = Column(UUID, primary_key=True, default=uuid.uuid4)
    player_id = Column(UUID, ForeignKey("players.player_id"), nullable=False, index=True)
    notification_type = Column(String(50), nullable=False)  # 'copy_submitted', 'vote_submitted'
    phraseset_id = Column(UUID, ForeignKey("phrasesets.phraseset_id"), nullable=False)
    actor_player_id = Column(UUID, ForeignKey("players.player_id"), nullable=True)
    metadata = Column(JSON, nullable=True)  # {phrase_text, role, etc.}
    read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False)

    # Relationships
    player = relationship("Player", foreign_keys=[player_id])
    actor_player = relationship("Player", foreign_keys=[actor_player_id])
    phraseset = relationship("Phraseset")

    # Indexes
    __table_args__ = (
        Index('ix_notifications_player_read', 'player_id', 'read'),
        Index('ix_notifications_player_created', 'player_id', 'created_at'),
    )
```

**Metadata Structure:**
```json
{
  "phrase_text": "the actual phrase",
  "recipient_role": "prompt" | "copy",
  "actor_username": "Alice"
}
```

#### 2. Notification Service
**File**: `backend/services/notification_service.py`

**Key Methods:**

```python
class NotificationService:

    async def notify_copy_submission(
        self,
        phraseset: Phraseset,
        copy_player_id: UUID,
        prompt_round: Round
    ):
        """
        Notify the prompt player when someone copies their prompt.
        Only notifies if both players are human.
        """
        # 1. Check prompt player is human
        # 2. Check copy player is human
        # 3. Check copy player != prompt player
        # 4. Create notification record
        # 5. Send via WebSocket if connected

    async def notify_vote_submission(
        self,
        phraseset: Phraseset,
        voter_player_id: UUID
    ):
        """
        Notify all contributors (prompt + both copies) when someone votes.
        Only notifies human contributors, excludes voter.
        """
        # 1. Get all contributor player_ids with their roles
        # 2. Check voter is human
        # 3. For each contributor:
        #    - Skip if AI
        #    - Skip if same as voter
        #    - Create notification with appropriate role/phrase
        #    - Send via WebSocket if connected

    async def _is_human_player(self, player_id: UUID) -> bool:
        """Check if player is human (not AI)."""
        player = await self.db.get(Player, player_id)
        return not player.email.endswith('@quipflip.internal')

    async def _get_contributor_data(self, phraseset: Phraseset) -> List[Dict]:
        """
        Get all contributors with their role and phrase.
        Returns: [
            {player_id, role: 'prompt', phrase: 'prompt_text'},
            {player_id, role: 'copy', phrase: 'copy1_text'},
            {player_id, role: 'copy', phrase: 'copy2_text'}
        ]
        """

    async def _create_notification(
        self,
        player_id: UUID,
        notification_type: str,
        phraseset_id: UUID,
        actor_player_id: UUID,
        metadata: dict
    ) -> Notification:
        """Create notification record in database."""

    async def _send_websocket_notification(
        self,
        player_id: UUID,
        notification: Notification,
        actor_username: str
    ):
        """Send notification via WebSocket if player is connected."""
        # Use NotificationConnectionManager singleton
        # Format message and send to player_id
        # Fail silently if not connected
```

**Human Player Identification:**
```python
# AI players have emails ending with '@quipflip.internal'
AI_PLAYER_EMAIL_DOMAIN = '@quipflip.internal'

def is_human(player: Player) -> bool:
    return not player.email.endswith(AI_PLAYER_EMAIL_DOMAIN)
```

#### 3. WebSocket Router
**File**: `backend/routers/notifications.py`

**Endpoint**: `GET /qf/notifications/ws?token={short_lived_token}`

**Authentication Flow:**
1. Frontend fetches short-lived token via REST: `GET /api/auth/ws-token`
2. Frontend connects to WebSocket with token: `/qf/notifications/ws?token=...`
3. Backend validates token using `AuthService.decode_access_token()`
4. If valid: accept connection, add to connection manager
5. If invalid: reject with code 1008 (policy violation)

**Connection Manager Pattern:**
```python
class NotificationConnectionManager:
    """
    Manages WebSocket connections for push notifications.
    Unlike OnlineUsers (broadcast), this targets specific players.
    """

    def __init__(self):
        # Map player_id → websocket connection
        self.active_connections: Dict[UUID, WebSocket] = {}

    async def connect(self, player_id: UUID, websocket: WebSocket):
        """Add player's WebSocket connection."""
        await websocket.accept()
        self.active_connections[player_id] = websocket

    async def disconnect(self, player_id: UUID):
        """Remove player's WebSocket connection."""
        if player_id in self.active_connections:
            del self.active_connections[player_id]

    async def send_to_player(self, player_id: UUID, message: dict):
        """
        Send message to specific player if connected.
        Fails silently if player not connected.
        """
        if player_id in self.active_connections:
            try:
                await self.active_connections[player_id].send_json(message)
            except Exception:
                # Connection failed, remove it
                await self.disconnect(player_id)

# Singleton instance
manager = NotificationConnectionManager()
```

**WebSocket Message Format:**
```json
{
  "type": "notification",
  "notification_type": "copy_submitted" | "vote_submitted",
  "actor_username": "Alice",
  "action": "copied" | "voted on",
  "recipient_role": "prompt" | "copy",
  "phrase_text": "the actual phrase text",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

#### 4. Integration Points

**In `backend/services/round_service.py`:**
```python
# Method: submit_copy_phrase()
# Location: After activity recording (line ~750)

async def submit_copy_phrase(self, round_id: UUID, phrase: str, player: Player):
    # ... existing code ...

    # After recording activity:
    await self.activity_service.record_activity(...)

    # ADD NOTIFICATION HOOK:
    notification_service = NotificationService(self.db)
    await notification_service.notify_copy_submission(
        phraseset=phraseset,
        copy_player_id=player.player_id,
        prompt_round=prompt_round
    )

    # ... rest of method ...
```

**In `backend/services/vote_service.py`:**
```python
# Method: submit_vote()
# Location: After activity recording (line ~726)

async def submit_vote(self, phraseset_id: UUID, phrase: str, player: Player):
    # ... existing code ...

    # After recording activity:
    await self.activity_service.record_activity(...)

    # ADD NOTIFICATION HOOK:
    notification_service = NotificationService(self.db)
    await notification_service.notify_vote_submission(
        phraseset=phraseset,
        voter_player_id=player.player_id
    )

    # ... rest of method ...
```

#### 5. Database Migration
**File**: `backend/alembic/versions/{timestamp}_add_notifications_table.py`

```python
def upgrade():
    op.create_table(
        'notifications',
        sa.Column('notification_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('player_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('notification_type', sa.String(50), nullable=False),
        sa.Column('phraseset_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('actor_player_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('metadata', postgresql.JSON, nullable=True),
        sa.Column('read', sa.Boolean, default=False, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['player_id'], ['players.player_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['phraseset_id'], ['phrasesets.phraseset_id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_player_id'], ['players.player_id'], ondelete='CASCADE'),
    )

    op.create_index('ix_notifications_player_read', 'notifications', ['player_id', 'read'])
    op.create_index('ix_notifications_player_created', 'notifications', ['player_id', 'created_at'])

def downgrade():
    op.drop_table('notifications')
```

#### 6. Router Registration
**File**: `backend/main.py`

```python
# Add import
from backend.routers import notifications

# Register router (with other routers around line 497)
app.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
```

---

### Frontend Components

#### 1. NotificationContext
**File**: `frontend/src/contexts/NotificationContext.tsx`

**Responsibilities:**
- Manage WebSocket connection lifecycle
- Authenticate connection using short-lived token
- Listen for notification messages
- Maintain notification queue for display
- No UI rendering (pure state management)

**State:**
```typescript
interface NotificationContextState {
  connectionStatus: 'disconnected' | 'connecting' | 'connected';
  notifications: NotificationMessage[];
  addNotification: (message: NotificationMessage) => void;
  removeNotification: (id: string) => void;
}

interface NotificationMessage {
  id: string;
  actor_username: string;
  action: 'copied' | 'voted on';
  recipient_role: 'prompt' | 'copy';
  phrase_text: string;
  timestamp: string;
}
```

**WebSocket Lifecycle:**
```typescript
// 1. Connect when authenticated
useEffect(() => {
  if (isAuthenticated) {
    connectWebSocket();
  } else {
    disconnectWebSocket();
  }
}, [isAuthenticated]);

// 2. Fetch token
const connectWebSocket = async () => {
  try {
    const tokenResponse = await fetch('/api/auth/ws-token', {
      credentials: 'include',
    });
    const { token } = await tokenResponse.json();

    // 3. Build WebSocket URL
    const wsUrl = buildWebSocketUrl('/qf/notifications/ws', token);

    // 4. Connect
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      setConnectionStatus('connected');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      if (message.type === 'notification') {
        addNotification({
          id: uuidv4(),
          actor_username: message.actor_username,
          action: message.action,
          recipient_role: message.recipient_role,
          phrase_text: message.phrase_text,
          timestamp: message.timestamp,
        });
      }
    };

    ws.onerror = () => {
      // Fail silently - no error message
      setConnectionStatus('disconnected');
    };

    ws.onclose = () => {
      // No reconnect attempts - fail silently
      setConnectionStatus('disconnected');
    };

    wsRef.current = ws;
  } catch (err) {
    // Fail silently
    setConnectionStatus('disconnected');
  }
};
```

**Key Differences from OnlineUsers.tsx:**
- No polling fallback
- No error messages to user
- No reconnect attempts
- Connected on authentication, not on page load

#### 2. NotificationDisplay Component
**File**: `frontend/src/components/NotificationDisplay.tsx`

**Design:**
- Reuses SuccessNotification styling
- Position: **bottom-right** (fixed)
- Stack max 3 notifications
- Auto-dismiss after 5 seconds
- Slide-in animation from right

**Component Structure:**
```typescript
interface NotificationDisplayProps {
  // Consumes from NotificationContext
}

const NotificationDisplay: React.FC = () => {
  const { notifications, removeNotification } = useNotifications();
  const navigate = useNavigate();

  // Only show last 3 notifications
  const visibleNotifications = notifications.slice(-3);

  return (
    <div className="fixed bottom-4 right-4 z-50 space-y-2">
      {visibleNotifications.map((notification, index) => (
        <NotificationToast
          key={notification.id}
          notification={notification}
          onDismiss={() => removeNotification(notification.id)}
          onTrackingClick={() => navigate('/tracking')}
          style={{ marginBottom: `${index * 8}px` }}
        />
      ))}
    </div>
  );
};
```

**NotificationToast Component:**
```typescript
interface NotificationToastProps {
  notification: NotificationMessage;
  onDismiss: () => void;
  onTrackingClick: () => void;
}

const NotificationToast: React.FC<NotificationToastProps> = ({
  notification,
  onDismiss,
  onTrackingClick,
}) => {
  const [isExiting, setIsExiting] = useState(false);

  // Auto-dismiss after 5 seconds
  useEffect(() => {
    const timer = setTimeout(() => {
      setIsExiting(true);
      setTimeout(onDismiss, 300); // Wait for exit animation
    }, 5000);

    return () => clearTimeout(timer);
  }, []);

  // Format message
  const icon = notification.action === 'copied' ? '📝' : '🗳️';
  const message = `${notification.actor_username} ${notification.action} your ${notification.recipient_role} submission of "${notification.phrase_text}"`;

  return (
    <div className={`
      tile-card p-4 max-w-md
      bg-gradient-to-r from-quip-turquoise to-teal-500
      transition-all duration-300
      ${isExiting ? 'opacity-0 translate-x-full' : 'opacity-100 translate-x-0'}
    `}>
      <div className="flex items-start gap-3">
        <span className="text-2xl">{icon}</span>

        <div className="flex-1">
          <p className="text-white font-semibold">{message}</p>

          <button
            onClick={onTrackingClick}
            className="mt-2 flex items-center gap-1 text-white/90 hover:text-white text-sm"
          >
            <TrackingIcon className="w-4 h-4" />
            <span>Visit the tracking page for details</span>
          </button>
        </div>

        <button
          onClick={() => {
            setIsExiting(true);
            setTimeout(onDismiss, 300);
          }}
          className="text-white/80 hover:text-white text-xl"
        >
          ×
        </button>
      </div>
    </div>
  );
};
```

#### 3. App Integration

**Update `frontend/src/contexts/AppProviders.tsx`:**
```typescript
import { NotificationProvider } from './NotificationContext';

export const AppProviders: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <NetworkProvider>
      <TutorialProvider>
        <GameProvider>
          <NotificationProvider>  {/* Add after GameProvider */}
            <NavigationHistoryProvider>
              <ResultsProvider>
                <QuestProvider>
                  <ContextBridge>
                    {children}
                  </ContextBridge>
                </QuestProvider>
              </ResultsProvider>
            </NavigationHistoryProvider>
          </NotificationProvider>
        </GameProvider>
      </TutorialProvider>
    </NetworkProvider>
  );
};
```

**Update `frontend/src/App.tsx`:**
```typescript
import NotificationDisplay from './components/NotificationDisplay';

// Add to global components (around line 115)
<OfflineBanner />
<ErrorNotification />
<GuestWelcomeOverlay />
<TutorialOverlay />
<NotificationDisplay />  {/* Add here */}
```

#### 4. Type Definitions

**Update `frontend/src/api/types.ts`:**
```typescript
export interface NotificationMessage {
  id: string;
  actor_username: string;
  action: 'copied' | 'voted on';
  recipient_role: 'prompt' | 'copy';
  phrase_text: string;
  timestamp: string;
}

export type NotificationType = 'copy_submitted' | 'vote_submitted';
```

---

## Notification Logic Matrix

### Copy Submission Notifications

| Scenario | Prompt Player | Copy Player | Notification Sent? | Message |
|----------|--------------|-------------|-------------------|---------|
| Human copies human prompt | Human | Human | ✅ Yes | "Alice copied your prompt submission of \"...\"" |
| AI copies human prompt | Human | AI | ❌ No | (AI actions don't trigger notifications) |
| Human copies AI prompt | AI | Human | ❌ No | (AI recipients don't get notifications) |
| Human copies own prompt | Human | Same Human | ❌ No | (No self-notifications) |

### Vote Submission Notifications

| Scenario | Contributors | Voter | Notifications Sent? | Messages |
|----------|-------------|-------|-------------------|----------|
| Human votes on all-human phraseset | 3 humans | Human | ✅ Yes (2 notifications) | To prompt: "Bob voted on your prompt submission of \"...\"" <br> To copy1: "Bob voted on your copy submission of \"...\"" <br> (Voter gets no notification) |
| Human votes on mixed phraseset | 1 human, 2 AI | Human | ✅ Yes (1 notification) | To human contributor only |
| AI votes on human phraseset | 3 humans | AI | ❌ No | (AI voters don't trigger notifications) |
| Human votes on own phraseset | Human (all 3 roles) | Same Human | ❌ No | (No self-notifications) |

---

## Implementation Checklist

### Phase 1: Backend Foundation
- [ ] Create `backend/models/notification.py`
- [ ] Create Alembic migration for notifications table
- [ ] Run migration: `alembic upgrade head`
- [ ] Create `backend/schemas/notification.py`
- [ ] Create `backend/services/notification_service.py`
- [ ] Write unit tests for notification service

### Phase 2: Backend WebSocket
- [ ] Create `backend/routers/notifications.py`
- [ ] Implement `NotificationConnectionManager`
- [ ] Implement WebSocket endpoint with authentication
- [ ] Register router in `backend/main.py`
- [ ] Test WebSocket connection with manual client

### Phase 3: Backend Integration
- [ ] Integrate into `round_service.py` (copy submission)
- [ ] Integrate into `vote_service.py` (vote submission)
- [ ] Test notifications fire on copy submission
- [ ] Test notifications fire on vote submission
- [ ] Test human-only filtering
- [ ] Test no self-notifications

### Phase 4: Frontend Foundation
- [ ] Create `frontend/src/contexts/NotificationContext.tsx`
- [ ] Implement WebSocket connection lifecycle
- [ ] Implement token fetch and authentication
- [ ] Test connection/disconnection on login/logout
- [ ] Verify silent failure behavior

### Phase 5: Frontend UI
- [ ] Create `frontend/src/components/NotificationDisplay.tsx`
- [ ] Create `NotificationToast` component
- [ ] Implement message formatting
- [ ] Add TrackingIcon and tracking page link
- [ ] Implement slide-in/out animations
- [ ] Test auto-dismiss timing
- [ ] Test notification stacking (max 3)

### Phase 6: Frontend Integration
- [ ] Update `frontend/src/contexts/AppProviders.tsx`
- [ ] Update `frontend/src/App.tsx`
- [ ] Update `frontend/src/api/types.ts`
- [ ] Test notifications appear globally (all pages)
- [ ] Test navigation to tracking page

### Phase 7: End-to-End Testing
- [ ] Create test accounts (human players only)
- [ ] Test copy notification flow:
  - [ ] Player A creates prompt
  - [ ] Player B copies → Player A sees notification
  - [ ] Verify message format
  - [ ] Click tracking icon → navigate to /tracking
- [ ] Test vote notification flow:
  - [ ] Create phraseset with Players A, B, C
  - [ ] Player D votes → Players A, B, C see notification
  - [ ] Verify role-specific messages (prompt vs copy)
- [ ] Test filtering:
  - [ ] AI copy → no notification
  - [ ] AI vote → no notification
  - [ ] Self-copy → no notification (edge case, shouldn't happen)
- [ ] Test silent failures:
  - [ ] Kill backend WebSocket → frontend stays silent
  - [ ] Block WebSocket connection → no error messages
  - [ ] User continues using app normally

### Phase 8: Production Deployment
- [ ] Run database migration on production
- [ ] Deploy backend changes
- [ ] Deploy frontend changes
- [ ] Monitor WebSocket connections
- [ ] Monitor notification delivery rate
- [ ] Verify Heroku WebSocket support

---

## Technical Considerations

### WebSocket URLs (Development vs Production)

**Development:**
```typescript
// REST API: http://localhost:8000/qf
// WebSocket: ws://localhost:8000/qf/notifications/ws
```

**Production:**
```typescript
// REST API: /api (proxied through Vercel to Heroku)
// WebSocket: wss://quipflip-c196034288cd.herokuapp.com/qf/notifications/ws
// (Direct connection, cannot proxy WebSocket through Vercel)
```

### Environment Variables
```env
VITE_API_URL=/api  # Production: proxied REST API
VITE_BACKEND_WS_URL=wss://quipflip-c196034288cd.herokuapp.com  # Production: direct WebSocket
```

### Performance Considerations
- **Connection limit**: Heroku allows ~50-100 concurrent WebSocket connections per dyno
- **Scaling**: Consider adding Redis pub/sub if users > 100 concurrent
- **Database load**: Notifications table will grow - consider archival strategy
- **WebSocket timeout**: Heroku closes idle WebSocket after 55 seconds (should send keepalive)

### Security Considerations
- **Token expiration**: 60-second tokens prevent replay attacks
- **CORS**: WebSocket direct to Heroku bypasses Vercel CORS
- **Rate limiting**: Consider rate limiting notification creation (prevent spam)
- **XSS prevention**: Sanitize usernames and phrase text in notifications

### Error Handling Philosophy
- **Silent failures**: WebSocket failures don't interrupt user experience
- **Graceful degradation**: App works fully without notifications
- **No retry logic**: Simplifies implementation, reduces server load
- **User experience**: Notifications are "nice to have", not critical

---

## Future Enhancements (Not in Scope)

1. **Notification History**: API endpoint to fetch past notifications
2. **Mark as Read**: Track which notifications user has seen
3. **Notification Preferences**: Let users opt out of certain notification types
4. **Unread Badge**: Show count of unread notifications in header
5. **Sound Effects**: Optional audio notification
6. **Push Notifications**: Browser push API for background notifications
7. **Email Notifications**: Digest emails for inactive users
8. **Redis Pub/Sub**: Scale beyond single dyno
9. **Notification Center**: Dropdown panel to view all notifications
10. **Deep Linking**: Navigate directly to specific phraseset from notification

---

## Success Metrics

- **Connection Rate**: % of authenticated users with active WebSocket connection
- **Delivery Rate**: % of created notifications successfully sent via WebSocket
- **Engagement Rate**: % of notifications clicked (tracking page navigation)
- **Error Rate**: WebSocket connection errors (should be gracefully handled)
- **User Satisfaction**: Feedback on notification usefulness

---

## Questions & Decisions

### Resolved
- ✅ **Silent failures**: Confirmed - no error messages, no polling fallback
- ✅ **Human-only**: Confirmed - filter AI players via email domain
- ✅ **Message format**: Confirmed - "{username} {action} your {role} submission of \"{phrase}\""
- ✅ **Tracking page**: Confirmed - use TrackingIcon, link to /tracking
- ✅ **Toast position**: Confirmed - bottom-right

### Open Questions
- ❓ Should we store notification history? (Not critical for MVP)
- ❓ Should we add read/unread tracking? (Not critical for MVP)
- ❓ Should we limit notification rate per user? (Probably yes - max 10/minute?)
- ❓ Should we add keepalive pings to prevent Heroku timeout? (Probably yes - every 30s)
- ❓ Should we truncate long phrases in notifications? (Probably yes - max 50 chars)

---

## References

- **OnlineUsers WebSocket Pattern**: `/Users/tfish/PycharmProjects/quipflip/frontend/src/pages/OnlineUsers.tsx`
- **SuccessNotification Component**: `/Users/tfish/PycharmProjects/quipflip/frontend/src/components/SuccessNotification.tsx`
- **TrackingIcon Component**: `/Users/tfish/PycharmProjects/quipflip/frontend/src/components/icons/TrackingIcon.tsx`
- **Phraseset Activity Service**: `/Users/tfish/PycharmProjects/quipflip/backend/services/phraseset_activity_service.py`
- **Round Service**: `/Users/tfish/PycharmProjects/quipflip/backend/services/round_service.py`
- **Vote Service**: `/Users/tfish/PycharmProjects/quipflip/backend/services/vote_service.py`

---

## Document Version
- **Version**: 1.0
- **Date**: 2025-01-15
- **Author**: AI Planning Session
- **Status**: Ready for Implementation
