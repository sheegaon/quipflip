# Party Mode Refactoring Guide

> **Goal**: Transition Party Mode from duplicate code patterns to a clean, reusable architecture that leverages existing infrastructure.

## Overview

Party Mode currently works but suffers from significant code duplication and architectural inconsistencies. This refactoring eliminates ~350+ lines of duplicate code while making the codebase more maintainable and extending the existing single-player infrastructure to support multi-player sessions transparently.

## Problem Statement

### Current Issues
1. **Wrong Endpoints**: PartyGame.tsx and round pages call normal round endpoints instead of party-specific ones
2. **No Progress Tracking**: Submissions don't increment party counters or trigger phase advancement
3. **Code Duplication**: Round transition logic repeated in 3+ files (~250 lines)
4. **Navigation Duplication**: Home/exit logic repeated in 3 files (~100 lines)
5. **Redundant API Calls**: PartyRoundModal and PartyGame both fetch session status independently

### Impact
- Party mode doesn't properly track player progress
- Phase transitions don't occur automatically
- Bug fixes require updating multiple files
- Inconsistent behavior between party and normal modes

## Solution Architecture

### Core Principles
1. **Backend Transparency**: Normal endpoints detect party context automatically
2. **Frontend Hooks**: Shared logic extracted to reusable hooks
3. **Single Source of Truth**: Party progress tracked in backend, synced via WebSocket
4. **Code Reuse**: Round pages work for both normal and party modes with minimal conditional logic

### Expected Outcomes
- **~350 lines removed** through consolidation
- **Single endpoint** handles both normal and party submissions
- **Automatic phase advancement** based on participant progress
- **Centralized transition logic** in coordinator hook
- **Zero duplication** of navigation patterns

## Implementation Phases

### Phase 1: Backend Foundation (Critical Path) 🔥
**Status**: Completed
**Effort**: 4-6 hours
**Impact**: Enables all other phases

Make submission endpoints party-aware so they automatically handle party context.

📄 [**Phase 1 Implementation Guide →**](./phase-1-backend-foundation.md)

**Key Changes**:
- Add `party_round_id` to Round model
- Make `POST /rounds/{id}/submit` detect party context
- Return party progress metadata in responses
- Create party-specific round start endpoints

**Deliverables**:
- ✅ Submissions automatically increment party progress
- ✅ Phase advancement happens without manual triggers
- ✅ WebSocket broadcasts work correctly
- ✅ Both normal and party modes use same endpoints

---

### Phase 2: Frontend Consolidation (High Impact) ⭐
**Status**: Completed
**Effort**: 3-4 hours
**Dependencies**: Phase 1 complete

Extract duplicate round transition and navigation logic into reusable hooks.

📄 [**Phase 2 Implementation Guide →**](./phase-2-frontend-consolidation.md)

**Key Changes**:
- Create `usePartyRoundCoordinator()` hook
- Create `usePartyNavigation()` hook
- Extend `usePartyMode()` with helpers
- Update round pages to use new hooks

**Deliverables**:
- ✅ ~250 lines of duplicate code removed
- ✅ Single place to update transition logic
- ✅ Consistent error handling across rounds
- ✅ Simplified round page components

---

### Phase 3: Integration Fixes (Critical Path) 🔥
**Status**: Completed
**Effort**: 2-3 hours
**Dependencies**: Phase 1, Phase 2 complete

Fix PartyGame.tsx and round pages to call correct endpoints.

📄 [**Phase 3 Implementation Guide →**](./phase-3-integration-fixes.md)

**Key Changes**:
- Fix PartyGame.tsx to use party endpoints
- Update round pages to use coordinator hook
- Remove manual progress tracking attempts
- Rely on backend for phase management

**Deliverables**:
- ✅ Party rounds correctly linked to sessions
- ✅ Progress tracking works end-to-end
- ✅ Automatic phase transitions function
- ✅ No more endpoint mismatches

---

### Phase 4: Data Model Enhancements (Enabler) 🔧
**Status**: Not Started
**Effort**: 2-3 hours
**Dependencies**: Phase 1, Phase 3 complete

Enhance API responses and frontend context with party metadata.

📄 [**Phase 4 Implementation Guide →**](./phase-4-data-models.md)

**Key Changes**:
- Add `party_context` to round start responses
- Extend PartyModeContext state
- Reduce redundant API calls
- Create standardized DTOs

**Deliverables**:
- ✅ Frontend has party progress without extra calls
- ✅ PartyRoundModal uses context instead of fetching
- ✅ Consistent data shapes across endpoints
- ✅ Better offline/loading states

---

### Phase 5: Maximum Reuse (Polish) 💎
**Status**: Not Started
**Effort**: 4-5 hours
**Dependencies**: All previous phases complete

Advanced refactoring for near-zero duplication between modes.

📄 [**Phase 5 Implementation Guide →**](./phase-5-maximum-reuse.md)

**Key Changes**:
- Create `usePartyRoundOverlay()` hook
- Consolidate success message handling
- Consider unified round page wrapper
- Extract common submission patterns

**Deliverables**:
- ✅ Round pages have <10 lines of party-specific code
- ✅ Adding features requires single-file changes
- ✅ Clear patterns for future modes
- ✅ Maximum maintainability

---

### Phase 6: Testing & Validation (Throughout) ✅
**Status**: Not Started
**Effort**: 3-4 hours (ongoing)
**Dependencies**: Execute after each phase

Comprehensive testing strategy for party mode flows.

📄 [**Phase 6 Testing Guide →**](./phase-6-testing.md)

**Test Scenarios**:
- Happy path: create → join → rounds → results
- Error cases: disconnects, timeouts, edge cases
- WebSocket synchronization
- Migration from old to new system

---

## Architecture Documentation

📐 [**Architecture Overview →**](./architecture-overview.md)

Detailed diagrams and explanations of:
- Current architecture and pain points
- Target architecture and data flows
- Backend service interaction patterns
- Frontend hook composition
- WebSocket event flows

---

## Getting Started

### Recommended Implementation Order

1. **Phase 1** - Fixes critical backend issues (foundation)
2. **Phase 2** - Creates reusable hooks (consolidation)
3. **Phase 3** - Wires everything together (integration)
4. **Phase 6** - Test thoroughly before proceeding
5. **Phase 4** - Optimize data flow (enhancement)
6. **Phase 5** - Polish and maximize reuse (optional)

### Quick Start

```bash
# 1. Review architecture
cat docs/party/architecture-overview.md

# 2. Start with backend fixes
cat docs/party/phase-1-backend-foundation.md

# 3. Follow checklist in each phase doc
```

### Time Estimates

| Phase | Effort | Can Run Tests? | Critical? |
|-------|--------|----------------|-----------|
| Phase 1 | 4-6h | ✅ Yes | 🔥 Critical |
| Phase 2 | 3-4h | ✅ Yes | ⭐ High Impact |
| Phase 3 | 2-3h | ✅ Yes | 🔥 Critical |
| Phase 4 | 2-3h | ✅ Yes | 🔧 Enabler |
| Phase 5 | 4-5h | ✅ Yes | 💎 Polish |
| Phase 6 | 3-4h | N/A (continuous) | ✅ Essential |
| **Total** | **18-25h** | | |

**Minimum Viable Refactor**: Phases 1-3 (~9-13 hours)
**Production Ready**: Add Phase 4 and 6 (~14-19 hours)
**Best Practice**: Complete all phases (~18-25 hours)

---

## Migration Strategy

### Backwards Compatibility

All phases are designed to be **additive** and **backwards compatible**:

- Phase 1: New code paths added, old ones still work
- Phase 2-3: Frontend refactor doesn't change API contracts
- Phase 4: Optional fields in responses (non-breaking)
- Phase 5: Internal refactor only

### Rollback Plan

Each phase includes rollback instructions in case of issues:
- Phase 1: Feature flags for party-aware endpoints
- Phase 2: Keep old functions until migration complete
- Phase 3: Revert to direct API calls if hooks fail
- Phases 4-5: Purely additive, can skip if needed

### Testing Between Phases

After each phase:
1. Run backend tests: `pytest backend/tests/party/`
2. Run frontend tests: `npm test`
3. Manual testing: Create party → complete rounds → verify results
4. Check logs for errors or warnings

---

## Success Metrics

### Code Quality
- [ ] Lines of code reduced by ~350+
- [ ] Duplicate code blocks eliminated
- [ ] Cyclomatic complexity reduced in round pages
- [ ] Test coverage increased to >85%

### Functionality
- [ ] Party mode works end-to-end
- [ ] Automatic phase transitions function
- [ ] Progress tracking accurate for all players
- [ ] WebSocket events sync UI correctly

### Performance
- [ ] Reduced API calls (PartyRoundModal fetches eliminated)
- [ ] Faster round transitions (no manual delays)
- [ ] Better perceived performance (instant feedback)

### Maintainability
- [ ] Single place to update round transition logic
- [ ] Clear patterns for adding new features
- [ ] Comprehensive documentation
- [ ] Easier onboarding for new developers

---

## Support & Troubleshooting

### Common Issues

**Issue**: Phase transitions don't happen automatically
**Solution**: Check Phase 1 implementation, verify `can_advance_phase()` logic

**Issue**: Round pages still duplicate code
**Solution**: Verify Phase 2 hooks are imported and used correctly

**Issue**: PartyRoundModal shows stale data
**Solution**: Check Phase 4 context updates and WebSocket handlers

**Issue**: AI players not submitting prompts/copies/votes
**Solution**: Verify automatic AI submission triggering is enabled in party coordination service. AI submissions are triggered synchronously when sessions start and when phases transition. See [AI Submission Pattern](./architecture-overview.md#ai-submission-automatic-triggering) for implementation details.

### Getting Help

- Review [architecture-overview.md](./architecture-overview.md) for system understanding
- Check phase-specific troubleshooting sections
- Run diagnostic scripts (see Phase 6 testing guide)
- Check git history for working implementations

---

## Contributing

When adding new party mode features:

1. **Add backend logic** in `party_coordination_service.py`
2. **Extend hooks** in `usePartyRoundCoordinator.ts` or similar
3. **Update DTOs** if response shapes change
4. **Add tests** for new flows
5. **Update docs** in this directory

### File Organization

```
docs/party/
├── README.md                        # This file (overview)
├── architecture-overview.md         # System diagrams and flows
├── phase-1-backend-foundation.md    # Backend party awareness
├── phase-2-frontend-consolidation.md # Hook creation
├── phase-3-integration-fixes.md     # Wiring fixes
├── phase-4-data-models.md           # Response enhancements
├── phase-5-maximum-reuse.md         # Advanced patterns
└── phase-6-testing.md               # Test strategy
```

---

## Glossary

- **Party Context**: Metadata linking a round to a party session
- **Phase**: Server-side game stage (LOBBY, PROMPT, COPY, VOTE, RESULTS)
- **Step**: Client-side UI state (matches phase but stored locally)
- **Coordinator**: Hook that manages round transitions in party mode
- **PartyRound**: Linking table between Round and PartySession
- **Progress Tracking**: Counting submitted prompts/copies/votes per participant

---

**Next Steps**: Start with [Phase 1: Backend Foundation →](./phase-1-backend-foundation.md)
