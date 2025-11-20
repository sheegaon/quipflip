# Party Mode Architecture Overview

> **Purpose**: Comprehensive architectural documentation for Party Mode refactoring, including current state analysis, target architecture, and detailed component interactions.

## Table of Contents

1. [System Overview](#system-overview)
2. [Current Architecture (Before Refactor)](#current-architecture-before-refactor)
3. [Target Architecture (After Refactor)](#target-architecture-after-refactor)
4. [Backend Architecture](#backend-architecture)
5. [Frontend Architecture](#frontend-architecture)
6. [Data Flow Patterns](#data-flow-patterns)
7. [WebSocket Event System](#websocket-event-system)
8. [Database Schema](#database-schema)
9. [API Contract](#api-contract)

---

## System Overview

### What is Party Mode?

Party Mode is a multiplayer extension of QuipFlip's single-player game. Multiple players join a shared session and progress through rounds (Prompt → Copy → Vote) together, with their submissions pooled and results aggregated.

### Key Differences from Normal Mode

| Aspect | Normal Mode | Party Mode |
|--------|-------------|------------|
| **Players** | Single player | 2-10 players |
| **Round Progression** | Immediate | Wait for all players |
| **Results** | Individual score | Aggregated scores + rankings |
| **State Management** | Local only | Synced via WebSocket |
| **API Endpoints** | `/rounds/{id}/*` | `/party/{session_id}/rounds/*` |
| **Navigation** | `/dashboard` | `/party/lobby` |

### Core Design Principles

1. **Transparency**: Round pages don't know if they're in party mode (context provides this)
2. **Delegation**: Party services wrap/delegate to existing round services
3. **Progressive Enhancement**: Normal mode works unchanged; party adds features
4. **Single Source of Truth**: Backend tracks progress; frontend reacts to state changes

---

## Current Architecture (Before Refactor)

### Pain Points Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ CURRENT STATE: Duplication & Inconsistency                   │
└─────────────────────────────────────────────────────────────┘

PartyGame.tsx                    PromptRound.tsx
┌──────────────┐                ┌──────────────┐
│ beginPartyFlow() │ ❌ Wrong!   │ onSubmitPrompt()│
│   ↓              │             │   ↓            │
│ apiClient        │             │ apiClient      │
│  .startPromptRound() ❌        │  .submitPrompt()│
│  (Normal endpoint)│             │  .startCopyRound() ✅
└──────────────┘                └──────────────┘
                                      │
                                      ↓
                  ┌───────────────────────────────────┐
                  │ CopyRound.tsx                      │
                  │ - Duplicate transition logic (60 LOC)│
                  │ - Duplicate home navigation (30 LOC)│
                  │ - Duplicate error handling (20 LOC)│
                  └───────────────────────────────────┘
                                      │
                                      ↓
                  ┌───────────────────────────────────┐
                  │ VoteRound.tsx                      │
                  │ - Duplicate transition logic (60 LOC)│
                  │ - Duplicate home navigation (30 LOC)│
                  │ - Duplicate error handling (20 LOC)│
                  └───────────────────────────────────┘

                  ┌───────────────────────────────────┐
                  │ PartyRoundModal.tsx                │
                  │ - Fetches session status separately│
                  │ - 2 extra API calls per round      │
                  │ - Stale data possible              │
                  └───────────────────────────────────┘

Backend:
┌────────────────────────────────────────────┐
│ POST /rounds/{id}/submit                   │
│ - Calls RoundService.submit()              │
│ - No party awareness ❌                     │
│ - Doesn't increment party progress ❌       │
│ - Doesn't trigger phase advancement ❌      │
└────────────────────────────────────────────┘

Result: 350+ lines of duplicate code, broken progress tracking
```

### Code Duplication Analysis

**PromptRound.tsx + CopyRound.tsx + VoteRound.tsx**:
```typescript
// DUPLICATED 3 TIMES (~180 lines total)
const handleTransition = async () => {
  setIsTransitioning(true);
  try {
    if (partyState.isPartyMode) {
      // Party-specific logic
      const response = await apiClient.startPartyCopyRound(partyState.sessionId);
      partyActions.updateCurrentStep('copy');
      navigate(`/rounds/${response.round_id}/copy`);
    } else {
      // Normal logic
      const response = await apiClient.startCopyRound(roundId);
      navigate(`/rounds/${response.round_id}/copy`);
    }
  } catch (error) {
    // Error handling...
  } finally {
    setIsTransitioning(false);
  }
};

// DUPLICATED 3 TIMES (~90 lines total)
const handleNavigateHome = () => {
  if (partyState.isPartyMode) {
    partyActions.endPartyMode();
    navigate('/party');
  } else {
    navigate('/dashboard');
  }
};

// DUPLICATED 3 TIMES (~60 lines total)
useEffect(() => {
  if (successMessage && partyState.isPartyMode) {
    setTimeout(() => handleTransition(), 2000);
  }
}, [successMessage]);
```

**Total Duplication**: ~330 lines across 3 files that could be consolidated into reusable hooks.

---

## Target Architecture (After Refactor)

### High-Level Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│ TARGET STATE: Unified, Clean, Reusable                       │
└─────────────────────────────────────────────────────────────┘

Frontend Hooks (shared logic)
┌──────────────────────────────────────────────────────────────┐
│ usePartyRoundCoordinator()                                    │
│ - transitionToNextRound(currentRound)                         │
│ - Handles party vs normal detection                          │
│ - Centralized error handling                                 │
│ - Navigation logic                                           │
│                                                              │
│ usePartyNavigation()                                         │
│ - navigateHome()                                             │
│ - navigateToResults()                                        │
│ - isInPartyMode                                              │
│                                                              │
│ usePartyRoundOverlay()                                       │
│ - Auto-renders PartyRoundModal when in party mode            │
│ - Auto-transitions on success                                │
└──────────────────────────────────────────────────────────────┘
                           ↓ Used by
┌──────────────────────────────────────────────────────────────┐
│ Round Pages (party-agnostic, <10 lines of party code)        │
│                                                              │
│ PromptRound.tsx    CopyRound.tsx    VoteRound.tsx           │
│ ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│ │ const { trans-  const { trans-  const { trans-   │       │
│ │   itionToNext   itionToNext      itionToNext      │       │
│ │   Round }       Round }          Round }          │       │
│ │ = useParty-    = useParty-      = useParty-       │       │
│ │   RoundCoord    RoundCoord       RoundCoord       │       │
│ │                                                   │       │
│ │ <PartyRound-   <PartyRound-     <PartyRound-      │       │
│ │  Overlay />     Overlay />       Overlay />       │       │
│ └──────────────┘  └──────────────┘  └──────────────┘       │
└──────────────────────────────────────────────────────────────┘
                           ↓ Calls
┌──────────────────────────────────────────────────────────────┐
│ Unified Backend Endpoints (party-aware)                      │
│                                                              │
│ POST /rounds/{round_id}/submit                               │
│ ↓                                                            │
│ if round.party_round_id:                                     │
│   PartyCoordinationService.submit_party_prompt()             │
│     ├─ Increments participant.prompts_submitted              │
│     ├─ Checks if can_advance_phase()                         │
│     └─ Broadcasts WebSocket update                           │
│ else:                                                        │
│   RoundService.submit_prompt()                               │
│                                                              │
└──────────────────────────────────────────────────────────────┘

Result: 350+ lines removed, single source of truth, clean patterns
```

### Component Interaction Flow

```
User Action (Submit Prompt)
        ↓
┌──────────────────┐
│ PromptRound.tsx  │
│ - Calls submit   │
└──────────────────┘
        ↓
┌──────────────────┐
│ API Client       │
│ POST /rounds/{id}/submit │
└──────────────────┘
        ↓
┌──────────────────────────────┐
│ Backend: round_routes.py     │
│ - Detects party context      │
│ - Routes accordingly         │
└──────────────────────────────┘
        ↓                    ↓
┌──────────────┐    ┌──────────────────────┐
│ Normal Mode  │    │ Party Mode           │
│ RoundService │    │ PartyCoordination-   │
│              │    │ Service              │
│              │    │ ├─ Increment counter │
│              │    │ ├─ Check advancement │
│              │    │ └─ WebSocket notify  │
└──────────────┘    └──────────────────────┘
        ↓                    ↓
┌──────────────────────────────┐
│ Response with party_context  │
│ {                            │
│   round_id: "...",           │
│   party_context: {           │
│     your_progress: {...},    │
│     session_progress: {...}  │
│   }                          │
│ }                            │
└──────────────────────────────┐
        ↓
┌──────────────────────────────┐
│ PartyModeContext updates     │
│ - Stores progress locally    │
│ - No extra API call needed   │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│ PartyRoundModal              │
│ - Reads from context         │
│ - Shows progress UI          │
└──────────────────────────────┘
        ↓
┌──────────────────────────────┐
│ WebSocket Event              │
│ "party_phase_advanced"       │
│ - All clients transition     │
│ - usePartyRoundCoordinator   │
│   handles navigation         │
└──────────────────────────────┘
```

---

## Backend Architecture

### Service Layer Hierarchy

```
┌─────────────────────────────────────────────────────────────┐
│ API Routes Layer                                             │
├─────────────────────────────────────────────────────────────┤
│ /backend/routes/qf/round_routes.py                          │
│ /backend/routes/qf/party_routes.py                          │
└─────────────────────────────────────────────────────────────┘
                           ↓ Calls
┌─────────────────────────────────────────────────────────────┐
│ Coordination Layer (Party-Specific)                          │
├─────────────────────────────────────────────────────────────┤
│ PartyCoordinationService                                     │
│ ├─ start_party_prompt_round()                               │
│ ├─ start_party_copy_round()                                 │
│ ├─ start_party_vote_round()                                 │
│ ├─ submit_party_prompt()                                    │
│ ├─ submit_party_copy()                                      │
│ ├─ submit_party_vote()                                      │
│ └─ can_advance_phase()      ← Phase advancement logic       │
└─────────────────────────────────────────────────────────────┘
                    ↓ Delegates to
┌─────────────────────────────────────────────────────────────┐
│ Core Services Layer (Reusable)                              │
├─────────────────────────────────────────────────────────────┤
│ RoundService                                                 │
│ ├─ create_prompt_round()                                    │
│ ├─ create_copy_round()                                      │
│ ├─ create_vote_round()                                      │
│ ├─ submit_prompt()                                          │
│ ├─ submit_copy()                                            │
│ └─ submit_vote()                                            │
│                                                              │
│ PartySessionService                                          │
│ ├─ update_participant_progress()                            │
│ ├─ get_session_progress()                                   │
│ └─ advance_phase()                                          │
└─────────────────────────────────────────────────────────────┘
                    ↓ Uses
┌─────────────────────────────────────────────────────────────┐
│ Data Access Layer                                            │
├─────────────────────────────────────────────────────────────┤
│ Models: Round, PartySession, PartyParticipant, PartyRound   │
│ Database: PostgreSQL (production) / SQLite (dev)            │
└─────────────────────────────────────────────────────────────┘
```

### Party Coordination Service Pattern

**Design**: Wrapper/Delegation pattern that extends core functionality.

```python
# backend/services/qf/party_coordination_service.py

class PartyCoordinationService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.round_service = RoundService(db)        # Delegation
        self.session_service = PartySessionService(db)

    async def submit_party_prompt(
        self,
        round_id: str,
        player_id: str,
        prompt_text: str,
        party_round_id: str
    ) -> dict:
        """
        Party-aware submission that:
        1. Delegates to core RoundService for business logic
        2. Adds party-specific progress tracking
        3. Triggers phase advancement if ready
        4. Returns enriched response with party context
        """

        # Step 1: Use existing round service
        submission = await self.round_service.submit_prompt(
            round_id=round_id,
            player_id=player_id,
            prompt_text=prompt_text
        )

        # Step 2: Update party progress
        participant = await self.session_service.increment_prompts_submitted(
            party_round_id=party_round_id,
            player_id=player_id
        )

        # Step 3: Check phase advancement
        session = await self.session_service.get_session(party_round_id)
        if await self.can_advance_phase(session):
            await self.session_service.advance_phase(session.id)
            await self._broadcast_phase_advanced(session.id)

        # Step 4: Return enriched response
        return {
            "submission": submission,
            "party_context": {
                "your_progress": {
                    "prompts_submitted": participant.prompts_submitted,
                    "prompts_required": session.config.prompts_per_player
                },
                "session_progress": {
                    "players_ready": await self._count_ready_players(session),
                    "total_players": len(session.participants)
                }
            }
        }
```

**Key Benefits**:
- Core `RoundService` remains unchanged (works for both modes)
- Party logic is additive, not invasive
- Easy to test in isolation
- Clear separation of concerns

### Party-Aware Endpoint Detection

**Phase 1 Implementation**: Automatic party context detection in submission endpoints.

```python
# backend/routes/qf/round_routes.py

@router.post("/rounds/{round_id}/submit/prompt")
async def submit_prompt(
    round_id: str,
    request: PromptSubmissionRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Unified endpoint that works for both normal and party modes.
    Detection happens automatically via round.party_round_id.
    """

    # Fetch round to determine context
    round_obj = await db.get(Round, round_id)
    if not round_obj:
        raise HTTPException(status_code=404, detail="Round not found")

    # Detect party context
    is_party_round = round_obj.party_round_id is not None

    if is_party_round:
        # Route to party coordination service
        coordination_service = PartyCoordinationService(db)
        result = await coordination_service.submit_party_prompt(
            round_id=round_id,
            player_id=request.player_id,
            prompt_text=request.prompt_text,
            party_round_id=round_obj.party_round_id
        )
        return result
    else:
        # Route to normal round service
        round_service = RoundService(db)
        result = await round_service.submit_prompt(
            round_id=round_id,
            player_id=request.player_id,
            prompt_text=request.prompt_text
        )
        return {"submission": result}
```

**Benefits**:
- Frontend doesn't need to know which endpoint to call
- No breaking changes to existing API
- Progressive enhancement (party features added transparently)
- Easier testing (single endpoint to test)

---

## Frontend Architecture

### Context and State Management

```
┌─────────────────────────────────────────────────────────────┐
│ React Context Hierarchy                                      │
└─────────────────────────────────────────────────────────────┘

<App>
  <AuthProvider>
    <GameProvider>              ← Normal game state (activeRound, etc.)
      <PartyModeProvider>       ← Party session state (NEW: enhanced)
        <QuestProvider>
          <Routes>
            <PromptRound />     ← Uses all contexts
            <CopyRound />
            <VoteRound />
            <PartyLobby />
          </Routes>
        </QuestProvider>
      </PartyModeProvider>
    </GameProvider>
  </AuthProvider>
</App>
```

### Enhanced PartyModeContext (Phase 4)

**Before (Current)**:
```typescript
interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;
}
```

**After (Phase 4)**:
```typescript
interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;

  // NEW: Eliminates need for extra API calls
  sessionConfig: {
    prompts_per_player: number;
    copies_per_prompt: number;
    // ... other config
  } | null;

  yourProgress: {
    prompts_submitted: number;
    copies_submitted: number;
    votes_submitted: number;
    prompts_required: number;
    copies_required: number;
    votes_required: number;
  } | null;

  sessionProgress: {
    players_ready_for_next_phase: number;
    total_players: number;
    current_phase: string;
  } | null;
}
```

### Custom Hooks Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ Custom Hooks Layer                                           │
└─────────────────────────────────────────────────────────────┘

usePartyRoundCoordinator()
├─ Uses: usePartyMode(), useNavigate(), useGameContext()
├─ Provides: transitionToNextRound(), isTransitioning, error
└─ Responsibility: Centralized round transition logic

usePartyNavigation()
├─ Uses: usePartyMode(), useNavigate()
├─ Provides: navigateHome(), navigateToResults(), isInPartyMode
└─ Responsibility: Mode-aware navigation

usePartyRoundOverlay() [Phase 5]
├─ Uses: usePartyMode(), usePartyRoundCoordinator()
├─ Provides: overlay (JSX), auto-transition on success
└─ Responsibility: Automatic modal display + transition

usePartyMode() [Enhanced]
├─ Provides: partyState, partyActions, isInPartyMode
├─ Actions: startPartyMode(), endPartyMode(), updateProgress()
└─ Responsibility: Party state management
```

### Hook Usage Pattern (Phase 2)

**Before (180 lines total across 3 files)**:
```typescript
// PromptRound.tsx
const PromptRound = () => {
  const [isTransitioning, setIsTransitioning] = useState(false);
  const { partyState, partyActions } = usePartyMode();
  const navigate = useNavigate();

  const handleTransition = async () => {
    setIsTransitioning(true);
    try {
      if (partyState.isPartyMode) {
        const response = await apiClient.startPartyCopyRound(partyState.sessionId);
        partyActions.updateCurrentStep('copy');
        navigate(`/rounds/${response.round_id}/copy`);
      } else {
        const response = await apiClient.startCopyRound(roundId);
        navigate(`/rounds/${response.round_id}/copy`);
      }
    } catch (error) {
      setError(error.message);
    } finally {
      setIsTransitioning(false);
    }
  };

  // ... 50 more lines of duplicate logic
};
```

**After (15 lines, hook handles complexity)**:
```typescript
// PromptRound.tsx
const PromptRound = () => {
  const { transitionToNextRound, isTransitioning, error } = usePartyRoundCoordinator();

  const handleSuccess = useCallback(() => {
    transitionToNextRound('prompt'); // Hook handles party vs normal
  }, [transitionToNextRound]);

  return (
    <PromptRoundUI onSuccess={handleSuccess} />
  );
};
```

### Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│ Page Component Layer                                         │
├─────────────────────────────────────────────────────────────┤
│ PromptRound.tsx                                              │
│ ├─ usePartyRoundCoordinator() ← Transition logic            │
│ ├─ usePartyNavigation()        ← Home/exit logic            │
│ └─ usePartyRoundOverlay()      ← Modal + auto-transition    │
│                                                              │
│ CopyRound.tsx                                                │
│ ├─ usePartyRoundCoordinator()                               │
│ ├─ usePartyNavigation()                                     │
│ └─ usePartyRoundOverlay()                                   │
│                                                              │
│ VoteRound.tsx                                                │
│ ├─ usePartyRoundCoordinator()                               │
│ ├─ usePartyNavigation()                                     │
│ └─ usePartyRoundOverlay()                                   │
└─────────────────────────────────────────────────────────────┘
                           ↓ Renders
┌─────────────────────────────────────────────────────────────┐
│ Shared Component Layer                                       │
├─────────────────────────────────────────────────────────────┤
│ PartyRoundModal.tsx                                          │
│ ├─ Reads from PartyModeContext (no API calls)               │
│ ├─ Displays progress bars                                   │
│ └─ Shows waiting/ready state                                │
└─────────────────────────────────────────────────────────────┘
```

---

## Data Flow Patterns

### Normal Mode Submission Flow

```
User submits prompt
       ↓
┌──────────────────┐
│ PromptRound.tsx  │
│ onSubmit()       │
└──────────────────┘
       ↓
┌──────────────────────────┐
│ API Client               │
│ POST /rounds/{id}/submit │
└──────────────────────────┘
       ↓
┌──────────────────────────┐
│ Backend                  │
│ round_obj.party_round_id │
│ = None                   │
│ → RoundService           │
└──────────────────────────┘
       ↓
┌──────────────────────────┐
│ Response                 │
│ { submission: {...} }    │
└──────────────────────────┘
       ↓
┌──────────────────────────┐
│ UI Update                │
│ - Show success message   │
│ - Enable next button     │
└──────────────────────────┘
```

### Party Mode Submission Flow

```
User submits prompt
       ↓
┌──────────────────┐
│ PromptRound.tsx  │
│ onSubmit()       │
└──────────────────┘
       ↓
┌──────────────────────────┐
│ API Client               │
│ POST /rounds/{id}/submit │
│ (Same endpoint!)         │
└──────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Backend                         │
│ round_obj.party_round_id != None│
│ → PartyCoordinationService      │
│   ├─ RoundService (delegate)    │
│   ├─ Update progress            │
│   ├─ Check advancement          │
│   └─ WebSocket broadcast        │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Response (enriched)             │
│ {                               │
│   submission: {...},            │
│   party_context: {              │
│     your_progress: {...},       │
│     session_progress: {...}     │
│   }                             │
│ }                               │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ PartyModeContext Update         │
│ - Store yourProgress            │
│ - Store sessionProgress         │
└─────────────────────────────────┘
       ↓                    ↓
┌──────────────────┐  ┌────────────────────┐
│ UI Update        │  │ PartyRoundModal    │
│ - Success message│  │ - Reads context    │
│                  │  │ - Shows progress   │
└──────────────────┘  └────────────────────┘
       ↓
┌─────────────────────────────────┐
│ WebSocket Event (all clients)   │
│ "party_phase_advanced"          │
│ → Auto-transition to next round │
└─────────────────────────────────┘
```

### Round Creation Flow (Party Mode)

```
PartyGame.tsx: beginPartyFlow()
       ↓
┌─────────────────────────────────┐
│ API Client                      │
│ POST /party/{session_id}/       │
│   rounds/prompt                 │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Backend                         │
│ PartyCoordinationService        │
│  .start_party_prompt_round()    │
│   ├─ RoundService.create_...    │
│   ├─ Link round to session      │
│   │   via PartyRound table      │
│   ├─ Set round.party_round_id   │
│   └─ Broadcast WebSocket        │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Response                        │
│ {                               │
│   round_id: "abc123",           │
│   party_round_id: "pr_xyz",     │
│   round_type: "prompt",         │
│   party_context: {...}          │
│ }                               │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ GameContext Update              │
│ setActiveRound(roundData)       │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ Navigation                      │
│ navigate(`/rounds/${round_id}/  │
│   prompt`)                      │
└─────────────────────────────────┘
       ↓
┌─────────────────────────────────┐
│ PromptRound.tsx                 │
│ - Renders with party overlay    │
│ - Submits use unified endpoint  │
└─────────────────────────────────┘
```

---

## WebSocket Event System

### Event Types

```typescript
// Party-specific WebSocket events

interface PartyPhaseAdvancedEvent {
  type: 'party_phase_advanced';
  session_id: string;
  new_phase: 'COPY' | 'VOTE' | 'RESULTS';
  round_id: string;  // New round to navigate to
}

interface PartyProgressUpdateEvent {
  type: 'party_progress_update';
  session_id: string;
  progress: {
    players_ready: number;
    total_players: number;
    ready_player_ids: string[];
  };
}

interface PartyPlayerJoinedEvent {
  type: 'party_player_joined';
  session_id: string;
  player: {
    id: string;
    display_name: string;
  };
  total_players: number;
}

interface PartyPlayerLeftEvent {
  type: 'party_player_left';
  session_id: string;
  player_id: string;
  total_players: number;
}
```

### WebSocket Handler Architecture

```typescript
// frontend/src/contexts/PartyModeContext.tsx

const PartyModeProvider = ({ children }) => {
  const { partyState, partyActions } = usePartyModeState();
  const navigate = useNavigate();
  const gameContext = useGameContext();

  // WebSocket setup
  useEffect(() => {
    if (!partyState.isPartyMode || !partyState.sessionId) return;

    const ws = new WebSocket(`ws://api/party/${partyState.sessionId}/ws`);

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);

      switch (message.type) {
        case 'party_phase_advanced':
          handlePhaseAdvanced(message);
          break;
        case 'party_progress_update':
          partyActions.updateSessionProgress(message.progress);
          break;
        case 'party_player_joined':
          handlePlayerJoined(message);
          break;
        case 'party_player_left':
          handlePlayerLeft(message);
          break;
      }
    };

    return () => ws.close();
  }, [partyState.isPartyMode, partyState.sessionId]);

  const handlePhaseAdvanced = useCallback((message: PartyPhaseAdvancedEvent) => {
    const phaseToStep = {
      'COPY': 'copy',
      'VOTE': 'vote',
      'RESULTS': 'results'
    };

    const newStep = phaseToStep[message.new_phase];
    partyActions.updateCurrentStep(newStep);

    // Update active round so round pages have context
    gameContext.updateActiveRound({
      id: message.round_id,
      type: newStep,
      partyRoundId: partyState.sessionId
    });

    // Navigate all clients simultaneously
    navigate(`/rounds/${message.round_id}/${newStep}`);
  }, [partyActions, gameContext, navigate]);

  // ... rest of provider
};
```

### Backend WebSocket Broadcasting

```python
# backend/services/qf/party_coordination_service.py

class PartyCoordinationService:
    async def _broadcast_phase_advanced(
        self,
        session_id: str,
        new_phase: str,
        new_round_id: str
    ):
        """
        Broadcast phase advancement to all connected clients.
        """
        message = {
            "type": "party_phase_advanced",
            "session_id": session_id,
            "new_phase": new_phase,
            "round_id": new_round_id
        }

        # Get all active WebSocket connections for this session
        connections = await websocket_manager.get_session_connections(session_id)

        for connection in connections:
            await connection.send_json(message)

    async def submit_party_prompt(self, ...):
        # ... submission logic ...

        # Check if all players ready
        if await self.can_advance_phase(session):
            new_round = await self.start_party_copy_round(session.id)
            await self.session_service.advance_phase(session.id, 'COPY')

            # Broadcast to all clients
            await self._broadcast_phase_advanced(
                session_id=session.id,
                new_phase='COPY',
                new_round_id=new_round.id
            )
```

---

## Database Schema

### Entity Relationship Diagram

```
┌────────────────────────────────────────────────────────────┐
│ Core Entities (Existing, Used by Normal + Party Mode)     │
└────────────────────────────────────────────────────────────┘

┌─────────────┐
│ Player      │
│─────────────│
│ id (PK)     │
│ display_name│
│ email       │
└─────────────┘
       │
       │ 1:N
       ↓
┌─────────────────┐
│ Round           │◄────┐
│─────────────────│     │
│ id (PK)         │     │ 1:1 (NEW in Phase 1)
│ type            │     │
│ party_round_id  │─────┘ Links to PartyRound
│ created_at      │       (nullable, indexed)
└─────────────────┘
       │
       │ 1:N
       ↓
┌─────────────────┐
│ Prompt          │
│─────────────────│
│ id (PK)         │
│ round_id (FK)   │
│ player_id (FK)  │
│ text            │
└─────────────────┘

┌────────────────────────────────────────────────────────────┐
│ Party Entities (New, Party-Specific)                       │
└────────────────────────────────────────────────────────────┘

┌─────────────────────┐
│ PartySession        │
│─────────────────────│
│ id (PK)             │
│ session_code        │
│ current_phase       │ ← LOBBY, PROMPT, COPY, VOTE, RESULTS
│ config (JSON)       │ ← prompts_per_player, etc.
│ created_at          │
└─────────────────────┘
       │
       │ 1:N
       ↓
┌─────────────────────┐
│ PartyParticipant    │
│─────────────────────│
│ id (PK)             │
│ session_id (FK)     │
│ player_id (FK)      │
│ prompts_submitted   │ ← Progress tracking (NEW in Phase 1)
│ copies_submitted    │
│ votes_submitted     │
│ is_host             │
└─────────────────────┘
       │
       │ N:1
       ↓
┌─────────────────────┐
│ Player              │
│ (shared entity)     │
└─────────────────────┘

┌─────────────────────┐
│ PartyRound          │ ← Linking table
│─────────────────────│
│ id (PK)             │
│ session_id (FK)     │
│ round_id (FK)       │ ← Links to core Round
│ round_type          │
│ created_at          │
└─────────────────────┘
       │
       └──────┐
              │ 1:1
              ↓
       ┌─────────────┐
       │ Round       │
       │ (shared)    │
       └─────────────┘
```

### Schema Changes (Phase 1)

**New Column on Round Table**:
```sql
-- Migration: Add party_round_id to Round
ALTER TABLE rounds
ADD COLUMN party_round_id UUID NULL;

CREATE INDEX idx_rounds_party_round_id
ON rounds(party_round_id);

ALTER TABLE rounds
ADD CONSTRAINT fk_rounds_party_round
FOREIGN KEY (party_round_id)
REFERENCES party_rounds(id)
ON DELETE SET NULL;
```

**Benefits**:
- Round can detect if it's part of a party session
- Enables automatic routing in submission endpoints
- Maintains referential integrity
- Nullable (doesn't break normal mode)

### Progress Tracking Schema

**PartyParticipant Progress Columns** (already exist, utilized in Phase 1):
```sql
CREATE TABLE party_participants (
    id UUID PRIMARY KEY,
    session_id UUID NOT NULL REFERENCES party_sessions(id),
    player_id UUID NOT NULL REFERENCES players(id),

    -- Progress tracking
    prompts_submitted INT DEFAULT 0,
    copies_submitted INT DEFAULT 0,
    votes_submitted INT DEFAULT 0,

    -- Metadata
    is_host BOOLEAN DEFAULT FALSE,
    joined_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(session_id, player_id)
);
```

**Phase Advancement Logic**:
```python
# backend/services/qf/party_coordination_service.py

async def can_advance_phase(self, session: PartySession) -> bool:
    """
    Check if all participants have met requirements for current phase.
    """
    participants = session.participants
    config = session.config

    if session.current_phase == 'PROMPT':
        required = config['prompts_per_player']
        return all(p.prompts_submitted >= required for p in participants)

    elif session.current_phase == 'COPY':
        required = config['copies_per_prompt'] * config['prompts_per_player']
        return all(p.copies_submitted >= required for p in participants)

    elif session.current_phase == 'VOTE':
        required = config['votes_per_player']
        return all(p.votes_submitted >= required for p in participants)

    return False
```

---

## API Contract

### Unified Submission Endpoint

**Endpoint**: `POST /rounds/{round_id}/submit/prompt`

**Request**:
```json
{
  "player_id": "player-uuid",
  "prompt_text": "A silly prompt"
}
```

**Response (Normal Mode)**:
```json
{
  "submission": {
    "id": "prompt-uuid",
    "round_id": "round-uuid",
    "player_id": "player-uuid",
    "text": "A silly prompt",
    "created_at": "2025-01-19T10:30:00Z"
  }
}
```

**Response (Party Mode - Phase 1)**:
```json
{
  "submission": {
    "id": "prompt-uuid",
    "round_id": "round-uuid",
    "player_id": "player-uuid",
    "text": "A silly prompt",
    "created_at": "2025-01-19T10:30:00Z"
  },
  "party_context": null  // Added but not yet populated
}
```

**Response (Party Mode - Phase 4)**:
```json
{
  "submission": {
    "id": "prompt-uuid",
    "round_id": "round-uuid",
    "player_id": "player-uuid",
    "text": "A silly prompt",
    "created_at": "2025-01-19T10:30:00Z"
  },
  "party_context": {
    "session_id": "party-session-uuid",
    "current_phase": "PROMPT",
    "your_progress": {
      "prompts_submitted": 2,
      "prompts_required": 3,
      "copies_submitted": 0,
      "copies_required": 6,
      "votes_submitted": 0,
      "votes_required": 9
    },
    "session_progress": {
      "players_ready_for_next_phase": 1,
      "total_players": 3,
      "ready_player_ids": ["player-uuid"]
    }
  }
}
```

### Party Round Start Endpoints

**Endpoint**: `POST /party/{session_id}/rounds/prompt`

**Response**:
```json
{
  "round_id": "round-uuid",
  "party_round_id": "party-round-uuid",
  "round_type": "prompt",
  "party_context": {
    "session_id": "party-session-uuid",
    "current_phase": "PROMPT",
    "your_progress": { /* ... */ },
    "session_progress": { /* ... */ }
  }
}
```

**Similar endpoints**:
- `POST /party/{session_id}/rounds/copy`
- `POST /party/{session_id}/rounds/vote`

### Session Status Endpoint (Deprecated in Phase 4)

**Before Phase 4**: PartyRoundModal calls this separately.

**Endpoint**: `GET /party/{session_id}/status`

**After Phase 4**: Data included in submission responses, no extra call needed.

---

## Summary

### Architecture Evolution

| Aspect | Before | After |
|--------|--------|-------|
| **Code Duplication** | 350+ lines | ~0 lines |
| **Endpoint Usage** | Wrong endpoints | Unified, party-aware |
| **Progress Tracking** | Manual, broken | Automatic, server-driven |
| **API Calls/Round** | 5+ | 3 |
| **State Sync** | Manual | WebSocket-driven |
| **Maintainability** | Update 3+ files | Update 1 hook |

### Key Takeaways

1. **Backend Transparency**: Core round services unchanged; party logic wraps them
2. **Frontend Consolidation**: Hooks eliminate duplication and provide clear patterns
3. **Progressive Enhancement**: Normal mode unaffected; party adds features
4. **Data-Driven UI**: Server tracks progress, frontend reacts to state changes
5. **Single Source of Truth**: Backend owns phase management, clients stay in sync

### Next Steps

Proceed to [Phase 1: Backend Foundation →](./phase-1-backend-foundation.md) to begin implementation.

---

**Document Version**: 1.0
**Last Updated**: 2025-01-19
**Maintained By**: Development Team
