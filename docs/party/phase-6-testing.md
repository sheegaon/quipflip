# Phase 6: Testing & Validation

> **Goal**: Comprehensive testing strategy to ensure party mode works correctly and no regressions occur in normal mode.

## Overview

Testing should happen **throughout** the refactoring process, not just at the end. This guide provides test scenarios, scripts, and checklists for each phase, plus end-to-end validation procedures.

## Testing Strategy

### Testing Philosophy

1. **Test After Each Phase**: Don't wait until the end to discover issues
2. **Automated + Manual**: Combine unit tests, integration tests, and manual testing
3. **Regression Focus**: Ensure normal mode still works perfectly
4. **Party Mode Flows**: Test all party-specific paths
5. **Edge Cases**: Disconnects, timeouts, error states

### Test Pyramid

```
        /\
       /  \      E2E Tests (Manual + Automated)
      /____\     - Full party game flows
     /      \    - Multi-player scenarios
    /        \   - WebSocket synchronization
   /__________\
  /            \ Integration Tests
 /              \ - API endpoint behavior
/________________\- Service coordination
                  Unit Tests
                  - Hook behavior
                  - Component rendering
                  - Utility functions
```

---

## Phase-by-Phase Testing

### Phase 1: Backend Foundation

**Unit Tests** (`backend/tests/party/test_party_aware_submissions.py`):

```python
import pytest
from uuid import uuid4
from backend.models.qf.round import Round
from backend.models.qf.party_round import PartyRound
from backend.services.qf.party_coordination_service import PartyCoordinationService

class TestPartyAwareSubmissions:
    """Test that submission endpoints detect and handle party context."""

    @pytest.mark.asyncio
    async def test_normal_submission_has_no_party_metadata(self, db, player, transaction_service):
        """Normal rounds should work identically to before."""
        round_service = RoundService(db)
        round_obj = await round_service.start_prompt_round(player, transaction_service)

        # Verify no party_round_id
        assert round_obj.party_round_id is None

        # Submit normally
        result = await round_service.submit_prompt_phrase(
            round_obj.round_id, "test phrase", player
        )

        assert result['success'] is True
        assert 'party_session_id' not in result
        assert 'party_context' not in result

    @pytest.mark.asyncio
    async def test_party_submission_increments_progress(
        self, db, party_session, player, transaction_service
    ):
        """Party submissions should increment participant counters."""
        coordination_service = PartyCoordinationService(db)
        party_session_service = PartySessionService(db)

        # Start party prompt round
        round_obj, party_round_id = await coordination_service.start_party_prompt_round(
            session_id=party_session.session_id,
            player=player,
            transaction_service=transaction_service
        )

        # Verify party_round_id is set
        assert round_obj.party_round_id == party_round_id

        # Get initial progress
        participant = await party_session_service.get_participant(
            party_session.session_id, player.player_id
        )
        initial_prompts = participant.prompts_submitted

        # Submit via coordination service
        result = await coordination_service.submit_party_prompt(
            session_id=party_session.session_id,
            player=player,
            round_id=round_obj.round_id,
            phrase="test phrase"
        )

        # Verify progress incremented
        participant = await party_session_service.get_participant(
            party_session.session_id, player.player_id
        )
        assert participant.prompts_submitted == initial_prompts + 1

        # Verify party metadata in response
        assert result['success'] is True

    @pytest.mark.asyncio
    async def test_phase_advancement_when_all_players_done(
        self, db, party_session_with_players, transaction_service
    ):
        """Phase should advance when all players submit."""
        # Setup: 2 players, 1 prompt each
        session = party_session_with_players
        players = session.participants

        coordination_service = PartyCoordinationService(db)
        party_session_service = PartySessionService(db)

        # Player 1 submits
        round1, _ = await coordination_service.start_party_prompt_round(
            session.session_id, players[0].player, transaction_service
        )
        await coordination_service.submit_party_prompt(
            session.session_id, players[0].player, round1.round_id, "phrase1"
        )

        # Check phase (should still be PROMPT)
        session = await party_session_service.get_session_by_id(session.session_id)
        assert session.current_phase == 'PROMPT'

        # Player 2 submits (last player)
        round2, _ = await coordination_service.start_party_prompt_round(
            session.session_id, players[1].player, transaction_service
        )
        await coordination_service.submit_party_prompt(
            session.session_id, players[1].player, round2.round_id, "phrase2"
        )

        # Check phase (should now be COPY)
        session = await party_session_service.get_session_by_id(session.session_id)
        assert session.current_phase == 'COPY'
```

**Run Tests**:
```bash
cd backend
pytest tests/party/test_party_aware_submissions.py -v
```

---

### Phase 2: Frontend Consolidation

**Unit Tests** (`qf_frontend/src/hooks/__tests__/usePartyRoundCoordinator.test.ts`):

```typescript
import { renderHook, act, waitFor } from '@testing-library/react';
import { usePartyRoundCoordinator } from '../usePartyRoundCoordinator';
import { PartyModeProvider } from '../../contexts/PartyModeContext';
import apiClient from '../../api/client';

jest.mock('../../api/client');
jest.mock('react-router-dom', () => ({
  useNavigate: () => jest.fn(),
}));

describe('usePartyRoundCoordinator', () => {
  const wrapper = ({ children }: any) => (
    <PartyModeProvider>{children}</PartyModeProvider>
  );

  it('should transition from prompt to copy round', async () => {
    const mockStartCopy = jest.fn().mockResolvedValue({
      round_id: 'copy123',
      party_round_id: 'pr456',
    });
    (apiClient.startPartyCopyRound as jest.Mock) = mockStartCopy;

    const { result } = renderHook(() => usePartyRoundCoordinator(), { wrapper });

    await act(async () => {
      await result.current.transitionToNextRound('prompt');
    });

    expect(mockStartCopy).toHaveBeenCalled();
    expect(result.current.isTransitioning).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it('should handle transition errors gracefully', async () => {
    const mockError = new Error('Network error');
    const mockStartCopy = jest.fn().mockRejectedValue(mockError);
    (apiClient.startPartyCopyRound as jest.Mock) = mockStartCopy;

    const { result } = renderHook(() => usePartyRoundCoordinator(), { wrapper });

    await act(async () => {
      try {
        await result.current.transitionToNextRound('prompt');
      } catch (err) {
        // Expected to throw
      }
    });

    expect(result.current.error).toContain('Network error');
    expect(result.current.isTransitioning).toBe(false);
  });

  it('should navigate to results for vote round', async () => {
    const mockNavigate = jest.fn();
    (require('react-router-dom').useNavigate as jest.Mock).mockReturnValue(mockNavigate);

    const { result } = renderHook(() => usePartyRoundCoordinator(), { wrapper });

    await act(async () => {
      await result.current.transitionToNextRound('vote');
    });

    expect(mockNavigate).toHaveBeenCalledWith(
      expect.stringContaining('/party/results/'),
      { replace: true }
    );
  });
});
```

**Run Tests**:
```bash
cd qf_frontend
npm test -- usePartyRoundCoordinator
```

---

### Phase 3: Integration Fixes

**Integration Test** (API + Frontend):

```bash
# Start backend
cd backend
uvicorn main:app --reload &

# Start frontend
cd qf_frontend
npm start &

# Test script
node test_integration.js
```

**test_integration.js**:
```javascript
const axios = require('axios');

async function testPartyModeIntegration() {
  const baseURL = 'http://localhost:8000';

  // 1. Register test users
  const player1 = await axios.post(`${baseURL}/auth/register`, {
    username: 'test_player1',
    email: 'test1@example.com',
    password: 'test123',
  });

  const player2 = await axios.post(`${baseURL}/auth/register`, {
    username: 'test_player2',
    email: 'test2@example.com',
    password: 'test123',
  });

  const token1 = player1.data.access_token;
  const token2 = player2.data.access_token;

  // 2. Create party session
  const partyRes = await axios.post(
    `${baseURL}/party/create`,
    {
      min_players: 2,
      max_players: 9,
      prompts_per_player: 1,
      copies_per_player: 1,
      votes_per_player: 1,
    },
    { headers: { Authorization: `Bearer ${token1}` } }
  );

  const sessionId = partyRes.data.session_id;
  const partyCode = partyRes.data.party_code;

  console.log('✓ Party created:', partyCode);

  // 3. Player 2 joins
  await axios.post(
    `${baseURL}/party/join`,
    { party_code: partyCode },
    { headers: { Authorization: `Bearer ${token2}` } }
  );

  console.log('✓ Player 2 joined');

  // 4. Start session
  await axios.post(
    `${baseURL}/party/${sessionId}/start`,
    {},
    { headers: { Authorization: `Bearer ${token1}` } }
  );

  console.log('✓ Session started');

  // 5. Start prompt rounds (both players)
  const prompt1Res = await axios.post(
    `${baseURL}/party/${sessionId}/rounds/prompt`,
    {},
    { headers: { Authorization: `Bearer ${token1}` } }
  );

  const round1Id = prompt1Res.data.round_id;
  console.log('✓ Player 1 started prompt round');

  // VERIFY: Response includes party_context
  if (!prompt1Res.data.party_context) {
    throw new Error('❌ Missing party_context in response');
  }
  console.log('✓ party_context present in response');

  const prompt2Res = await axios.post(
    `${baseURL}/party/${sessionId}/rounds/prompt`,
    {},
    { headers: { Authorization: `Bearer ${token2}` } }
  );

  const round2Id = prompt2Res.data.round_id;

  // 6. Submit prompts
  await axios.post(
    `${baseURL}/rounds/${round1Id}/submit`,
    { phrase: 'test phrase 1' },
    { headers: { Authorization: `Bearer ${token1}` } }
  );

  console.log('✓ Player 1 submitted prompt');

  // Check phase (should still be PROMPT)
  let status = await axios.get(`${baseURL}/party/${sessionId}/status`, {
    headers: { Authorization: `Bearer ${token1}` },
  });

  if (status.data.current_phase !== 'PROMPT') {
    throw new Error('❌ Phase should still be PROMPT');
  }
  console.log('✓ Phase still PROMPT after first submission');

  // Player 2 submits (should trigger phase advancement)
  await axios.post(
    `${baseURL}/rounds/${round2Id}/submit`,
    { phrase: 'test phrase 2' },
    { headers: { Authorization: `Bearer ${token2}` } }
  );

  console.log('✓ Player 2 submitted prompt');

  // Check phase (should now be COPY)
  status = await axios.get(`${baseURL}/party/${sessionId}/status`, {
    headers: { Authorization: `Bearer ${token1}` },
  });

  if (status.data.current_phase !== 'COPY') {
    throw new Error(`❌ Phase should be COPY but is ${status.data.current_phase}`);
  }
  console.log('✓ Phase auto-advanced to COPY');

  console.log('\n✅ All integration tests passed!');
}

testPartyModeIntegration().catch(console.error);
```

---

## End-to-End Testing

### Manual Test Scenario: Full Party Game

**Participants**: 2-3 testers with different browsers/devices

**Steps**:

1. **Setup**:
   - Tester A: Create party (becomes host)
   - Testers B, C: Join party via party code
   - All mark ready
   - Verify: Lobby shows all players as ready

2. **Host Starts Session**:
   - Host clicks "Start Party"
   - Verify: All players navigate to `/party/game/{sessionId}`
   - Verify: PartyGame calls `POST /party/{sessionId}/rounds/prompt`
   - Verify: All navigate to `/prompt`

3. **Prompt Phase**:
   - All players submit prompts
   - Verify: PartyRoundModal shows progress updating
   - Verify: After last submission, phase advances to COPY
   - Verify: WebSocket broadcasts phase_transition event

4. **Copy Phase**:
   - All players navigate back to `/party/game/{sessionId}`
   - Verify: System routes to `/copy`
   - All submit copies
   - Verify: Progress tracked correctly
   - Verify: Phase advances to VOTE

5. **Vote Phase**:
   - All players navigate back to `/party/game/{sessionId}`
   - Verify: System routes to `/vote`
   - All submit votes
   - Verify: Phase advances to RESULTS

6. **Results**:
   - All players navigate to `/party/results/{sessionId}`
   - Verify: Rankings displayed correctly
   - Verify: Awards shown
   - Verify: Phraseset summaries visible
   - Verify: "Play Again" button works

### Automated E2E Test (Playwright)

**File**: `e2e/party-mode-flow.spec.ts`

```typescript
import { test, expect } from '@playwright/test';

test.describe('Party Mode Full Flow', () => {
  test('should complete full party game with 2 players', async ({ browser }) => {
    // Create two browser contexts (two players)
    const context1 = await browser.newContext();
    const context2 = await browser.newContext();

    const page1 = await context1.newPage();
    const page2 = await context2.newPage();

    // Player 1: Register and create party
    await page1.goto('http://localhost:3000/register');
    await page1.fill('[name="username"]', 'player1');
    await page1.fill('[name="email"]', 'player1@test.com');
    await page1.fill('[name="password"]', 'test123');
    await page1.click('button[type="submit"]');

    await page1.waitForURL('**/dashboard');
    await page1.click('text=Party Mode');
    await page1.click('text=Create Party');

    // Get party code
    const partyCodeElement = await page1.locator('[data-testid="party-code"]');
    const partyCode = await partyCodeElement.textContent();

    // Player 2: Register and join party
    await page2.goto('http://localhost:3000/register');
    await page2.fill('[name="username"]', 'player2');
    await page2.fill('[name="email"]', 'player2@test.com');
    await page2.fill('[name="password"]', 'test123');
    await page2.click('button[type="submit"]');

    await page2.waitForURL('**/dashboard');
    await page2.click('text=Party Mode');
    await page2.fill('[placeholder="Enter party code"]', partyCode);
    await page2.click('text=Join Party');

    // Both should be in lobby
    await expect(page1.locator('text=Party Lobby')).toBeVisible();
    await expect(page2.locator('text=Party Lobby')).toBeVisible();

    // Host starts session
    await page1.click('text=Start Party');

    // Both navigate to prompt round
    await expect(page1.locator('text=Quip Round')).toBeVisible({ timeout: 5000 });
    await expect(page2.locator('text=Quip Round')).toBeVisible({ timeout: 5000 });

    // Both submit prompts
    await page1.fill('[placeholder="Enter your phrase"]', 'player one phrase');
    await page1.click('button[type="submit"]');

    await page2.fill('[placeholder="Enter your phrase"]', 'player two phrase');
    await page2.click('button[type="submit"]');

    // Should auto-advance to copy round
    await expect(page1.locator('text=Impostor Round')).toBeVisible({ timeout: 10000 });
    await expect(page2.locator('text=Impostor Round')).toBeVisible({ timeout: 10000 });

    // Submit copies
    await page1.fill('[placeholder="Enter your phrase"]', 'player one copy');
    await page1.click('button[type="submit"]');

    await page2.fill('[placeholder="Enter your phrase"]', 'player two copy');
    await page2.click('button[type="submit"]');

    // Should auto-advance to vote round
    await expect(page1.locator('text=Guess the Original')).toBeVisible({ timeout: 10000 });
    await expect(page2.locator('text=Guess the Original')).toBeVisible({ timeout: 10000 });

    // Vote (click first option)
    await page1.click('.tutorial-vote-options button:first-child');
    await page2.click('.tutorial-vote-options button:first-child');

    // Should navigate to results
    await expect(page1.locator('text=Party Results')).toBeVisible({ timeout: 10000 });
    await expect(page2.locator('text=Party Results')).toBeVisible({ timeout: 10000 });

    // Verify rankings displayed
    await expect(page1.locator('text=Final Rankings')).toBeVisible();
    await expect(page2.locator('text=Final Rankings')).toBeVisible();

    await context1.close();
    await context2.close();
  });
});
```

**Run**:
```bash
npx playwright test e2e/party-mode-flow.spec.ts
```

---

## Regression Testing

### Normal Mode Regression Checklist

After completing refactoring, verify normal mode still works:

- [ ] Create account and login
- [ ] Start normal prompt round
- [ ] Submit prompt → navigate to dashboard
- [ ] Start normal copy round
- [ ] Submit copy → navigate to dashboard
- [ ] Start normal vote round
- [ ] Submit vote → navigate to dashboard
- [ ] Check Round Tracking page
- [ ] View phrasesets
- [ ] All normal flows work identically to before

### Performance Testing

**Metrics to Monitor**:

| Metric | Before | After | Target |
|--------|--------|-------|--------|
| Round start time | 500ms | ? | <600ms |
| Submission time | 300ms | ? | <400ms |
| API calls per round | 5 | ? | ≤3 |
| Bundle size | 2.1MB | ? | <2.2MB |
| Time to Interactive | 3.2s | ? | <3.5s |

**Tools**:
- Chrome DevTools Network tab
- Lighthouse performance audit
- `npm run build -- --stats` for bundle analysis

---

## Test Data Fixtures

### Backend Fixtures

**File**: `backend/tests/conftest.py`

```python
import pytest
from backend.models.qf.party_session import PartySession
from backend.models.qf.party_participant import PartyParticipant

@pytest.fixture
async def party_session(db, player):
    """Create a party session with one participant (host)."""
    from backend.services.qf.party_session_service import PartySessionService

    service = PartySessionService(db)
    session = await service.create_session(
        host_player_id=player.player_id,
        min_players=2,
        max_players=9,
        prompts_per_player=1,
        copies_per_player=1,
        votes_per_player=1,
    )
    return session

@pytest.fixture
async def party_session_with_players(db, player, player2):
    """Create a party session with 2 participants."""
    from backend.services.qf.party_session_service import PartySessionService

    service = PartySessionService(db)
    session = await service.create_session(
        host_player_id=player.player_id,
        min_players=2,
        max_players=9,
        prompts_per_player=1,
        copies_per_player=1,
        votes_per_player=1,
    )

    # Add second player
    await service.add_participant(session.session_id, player2.player_id)

    return session
```

---

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Party Mode Tests

on: [push, pull_request]

jobs:
  backend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
          pip install pytest pytest-asyncio
      - name: Run tests
        run: |
          cd backend
          pytest tests/party/ -v

  frontend-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Node
        uses: actions/setup-node@v2
        with:
          node-version: '18'
      - name: Install dependencies
        run: |
          cd qf_frontend
          npm ci
      - name: Run tests
        run: |
          cd qf_frontend
          npm test -- --watchAll=false

  e2e-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup environment
        run: |
          # Start backend and frontend
          # Run Playwright tests
      - name: Run E2E tests
        run: npx playwright test
```

---

## Success Criteria

### Phase Completion Checklist

- [ ] **Phase 1**: Backend tests pass, party submissions work
- [ ] **Phase 2**: Frontend tests pass, hooks consolidate logic
- [ ] **Phase 3**: Integration tests pass, PartyGame uses correct endpoints
- [ ] **Phase 4**: No redundant API calls, context updates correctly
- [ ] **Phase 5**: Round pages are mode-agnostic, minimal party code
- [ ] **Phase 6**: All E2E scenarios pass, no regressions

### Overall Success Metrics

- [ ] Party mode completes end-to-end without errors
- [ ] Normal mode works identically to before refactoring
- [ ] WebSocket events sync UI correctly
- [ ] Progress tracking accurate
- [ ] Phase advancement automatic
- [ ] Code coverage >85%
- [ ] No console errors or warnings
- [ ] Performance metrics within target ranges

---

## Troubleshooting Common Test Failures

### "Phase doesn't advance after all submissions"

**Check**:
- Backend logs: Is `can_advance_phase()` being called?
- Participant progress: Are counters incrementing?
- WebSocket: Is `notify_phase_transition` broadcasting?

**Fix**: Verify Phase 1 submission routing is correct

### "PartyRoundModal shows stale data"

**Check**:
- Context updates: Is `updateFromPartyContext()` being called?
- WebSocket connection: Is `usePartyWebSocket` connected?
- Response structure: Does API response include `party_context`?

**Fix**: Verify Phase 4 context updates

### "Round pages stuck in loading state"

**Check**:
- GameContext: Is `activeRound` populated?
- Navigation: Did `updateActiveRound` get called?
- Network: Did round start API call succeed?

**Fix**: Verify Phase 3 PartyGame integration

---

## Estimated Time

- **Phase-specific testing**: 30min per phase × 5 = 2.5 hours
- **E2E manual testing**: 1 hour
- **E2E automated tests**: 1.5 hours
- **Regression testing**: 1 hour
- **Total**: **3-4 hours** (ongoing throughout refactoring)
