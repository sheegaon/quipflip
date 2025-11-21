import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../../contexts/PartyModeContext';
import { usePartyWebSocket } from '../../hooks/usePartyWebSocket';
import { PartyIcon } from '../icons/NavigationIcons';
import { PartyStep } from '../../contexts/PartyModeContext';
import apiClient, { extractErrorMessage } from '../../api/client';

interface PartyRoundModalProps {
  sessionId: string;
  currentStep: PartyStep;
}

const phaseOrder: { id: PartyStep; label: string }[] = [
  { id: 'prompt', label: 'Quip' },
  { id: 'copy', label: 'Impostor' },
  { id: 'vote', label: 'Vote' },
];

export const PartyRoundModal: React.FC<PartyRoundModalProps> = ({ sessionId, currentStep }) => {
  const navigate = useNavigate();
  const { state: partyState, actions: partyActions } = usePartyMode();
  const [isOpen, setIsOpen] = useState(true);
  const [isLeaving, setIsLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const isProgressMissing = !partyState.yourProgress || !partyState.sessionConfig;

  // WebSocket updates will update context when other players make progress
  usePartyWebSocket({
    sessionId,
    pageContext: 'game',
    onProgressUpdate: (data) => {
      // Update session progress when we receive WebSocket updates about other players
      console.log('🔔 [Party Modal] Received progress update via WebSocket:', data);
      partyActions.updateSessionProgress({
        players_ready_for_next_phase: data.session_progress.players_done_with_phase,
        total_players: data.session_progress.total_players,
      });
    },
    onPhaseTransition: () => {
      // Phase transition handled elsewhere
    },
    onSessionUpdate: () => {
      // Session updates handled via context
    },
  });

  // Derive values from context instead of local state
  const prompts_submitted = partyState.yourProgress?.prompts_submitted ?? 0;
  const prompts_required = partyState.sessionConfig?.prompts_per_player ?? 0;
  const copies_submitted = partyState.yourProgress?.copies_submitted ?? 0;
  const copies_required = partyState.sessionConfig?.copies_per_player ?? 0;
  const votes_submitted = partyState.yourProgress?.votes_submitted ?? 0;
  const votes_required = partyState.sessionConfig?.votes_per_player ?? 0;

  const playersReady = partyState.sessionProgress?.players_ready_for_next_phase ?? 0;
  const totalPlayers = partyState.sessionProgress?.total_players ?? 0;

  const handleLeaveParty = async () => {
    if (isLeaving) return;

    setIsLeaving(true);
    setLeaveError(null);

    try {
      // Try to leave via API (only works before session starts)
      try {
        await apiClient.leavePartySession(sessionId);
      } catch (apiErr) {
        // If leave fails (e.g., session already started), just navigate away
        // The WebSocket will disconnect and the player will be removed from the session
        const message = extractErrorMessage(apiErr) || '';
        if (!message.includes('has started')) {
          throw apiErr;
        }
        // If session has started, silently proceed with navigation
        console.log('Session has started, navigating away without API call');
      }

      // End party mode in context
      partyActions.endPartyMode();

      // Navigate to dashboard
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to leave party';
      setLeaveError(message);
    } finally {
      setIsLeaving(false);
    }
  };

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-4 right-4 z-30 rounded-full bg-quip-orange text-white px-4 py-2 shadow-tile hover:bg-quip-orange-deep"
      >
        Show Party Status
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-quip-navy/40 p-4">
      <div className="w-full max-w-xl rounded-tile bg-quip-warm-ivory p-6 shadow-tile-lg relative">
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="absolute top-4 right-4 text-quip-teal hover:text-quip-turquoise"
          aria-label="Close party status"
        >
          ✕
        </button>

        <div className="flex items-center gap-3 mb-4">
          <PartyIcon className="w-8 h-8" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-quip-teal">Party Mode</p>
            <h3 className="text-2xl font-display font-bold text-quip-navy">Quip · Impostor · Vote</h3>
          </div>
        </div>

        <div className="tile-card p-4 mb-4">
          <div className="flex items-center justify-between gap-2">
            {phaseOrder.map((phase, idx) => {
              const isActive = currentStep === phase.id;
              const isComplete = phaseOrder.findIndex((p) => p.id === currentStep) > idx;

              return (
                <React.Fragment key={phase.id}>
                  <div className="flex flex-col items-center">
                    <div
                      className={`w-10 h-10 rounded-full flex items-center justify-center font-bold ${
                        isActive
                          ? 'bg-quip-orange text-white'
                          : isComplete
                            ? 'bg-quip-turquoise text-white'
                            : 'bg-gray-300 text-gray-600'
                      }`}
                    >
                      {isComplete ? '✓' : idx + 1}
                    </div>
                    <span
                      className={`text-xs mt-1 font-semibold ${isActive ? 'text-quip-orange-deep' : 'text-quip-teal'}`}
                    >
                      {phase.label}
                    </span>
                  </div>
                  {idx < phaseOrder.length - 1 && (
                    <div
                      className={`flex-1 h-1 mx-1 ${
                        isComplete ? 'bg-quip-turquoise' : 'bg-gray-300'
                      }`}
                    />
                  )}
                </React.Fragment>
              );
            })}
          </div>
        </div>

        <div className="tile-card p-4">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-quip-teal">Your Progress</span>
            <span className="text-sm font-semibold text-quip-teal">
              {playersReady} / {totalPlayers} players ready
            </span>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Quips:</span>
              <span className="font-bold text-quip-navy">
                {prompts_submitted} / {prompts_required}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Impostors:</span>
              <span className="font-bold text-quip-navy">
                {copies_submitted} / {copies_required}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Votes:</span>
              <span className="font-bold text-quip-navy">
                {votes_submitted} / {votes_required}
              </span>
            </div>
            {isProgressMissing && (
              <p className="text-xs text-quip-navy/70">
                Party progress will appear once the next round response includes party context.
              </p>
            )}
          </div>

          {/* Leave Party Button */}
          <div className="mt-4 pt-4 border-t border-quip-navy/10">
            {leaveError && (
              <p className="text-xs text-red-600 mb-2">{leaveError}</p>
            )}
            <button
              type="button"
              onClick={handleLeaveParty}
              disabled={isLeaving}
              className="w-full bg-red-500 hover:bg-red-600 disabled:bg-gray-400 text-white font-semibold py-2 px-4 rounded-tile transition-colors text-sm"
            >
              {isLeaving ? 'Leaving...' : 'Leave Party'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyRoundModal;
