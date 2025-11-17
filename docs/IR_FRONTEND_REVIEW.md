# Initial Reaction Frontend Review

## Scope
This review compares the current IR frontend implementation to the intended UX outlined in `IR_DATA_MODELS`, `IR_GAME_RULES`, `IR_MVP_PLAN`, and `IR_UX_FLOW`. Focus areas include guest experience, push-forward navigation, and voting/transition flows.

## Findings

### Guest experience is not simplified
The dashboard renders the same action card, pending results list, and upgrade banner for guests as for registered users. The UX flow calls for a simplified guest dashboard with only the “Start Backronym Battle” action and no general voting options.

- Dashboard shows full action cards and pending results for guests aside from an upgrade banner.【F:ir_frontend/src/pages/Dashboard.tsx†L104-L220】
- UX guidance expects guest dashboards to hide voting affordances and emphasize the single start action.【F:docs/IR_UX_FLOW.md†L22-L29】

### Push-forward navigation is broken
The creation screen includes a “Back to Dashboard” button and allows mid-round backtracking, which conflicts with the push-forward-only flow for rapid mode.

- Backronym creation page offers a direct navigation control back to the dashboard during an active round.【F:ir_frontend/src/pages/BackronymCreate.tsx†L390-L400】
- UX requirements stress never returning to the dashboard mid-round for rapid flow.【F:docs/IR_UX_FLOW.md†L176-L184】

### Vote tracking view is missing
After submitting a vote, the UI immediately navigates to the results page without showing interim vote counts or a countdown, skipping the intended vote-tracking step.

- Voting handler redirects directly to results with a 1-second delay and no intermediate screen.【F:ir_frontend/src/pages/Voting.tsx†L160-L165】
- UX specifies a post-vote tracking view that surfaces live counts and the finalization timer.【F:docs/IR_UX_FLOW.md†L110-L116】

## Next Steps
- Create a guest-specific dashboard mode that hides voting-related navigation and reduces CTAs to the single “Start Backronym Battle” action unless the guest is a participant.
- Remove or guard dashboard back-navigation during active rounds so flows move forward through creation → tracking → voting → results per rapid-mode rules.
- Add a vote-tracking view (or state within the voting page) that polls set status, shows vote counts, and displays the finalization timer before transitioning to results.
