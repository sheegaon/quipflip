import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { usePartyMode } from '../../contexts/PartyModeContext';
import { usePartyWebSocket } from '@/hooks/usePartyWebSocket.ts';
import { CircleIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';
import { PartyStep } from '../../contexts/PartyModeContext';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import { usePartyRoundStarter } from '@/hooks/usePartyRoundStarter.ts';
import { useGame } from '../../contexts/GameContext';

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
  const { state: gameState } = useGame();
  const { state: partyState, actions: partyActions } = usePartyMode();
  const [isOpen, setIsOpen] = useState(true);
  const [isLeaving, setIsLeaving] = useState(false);
  const [leaveError, setLeaveError] = useState<string | null>(null);
  const [syncError, setSyncError] = useState<string | null>(null);
  const syncInFlightRef = useRef(false);
  const { startRoundForPhase, endSessionAndShowResults } = usePartyRoundStarter();
  const isProgressMissing = !partyState.yourProgress || !partyState.sessionConfig;

  const syncSessionStatus = useCallback(async () => {
    if (!sessionId || syncInFlightRef.current) return;

    syncInFlightRef.current = true;

    try {
      const status = await apiClient.getPartySessionStatus(sessionId);
      const normalizedPhase = status.current_phase.toLowerCase();

      const selfParticipant = gameState.player
        ? status.participants.find((participant) => participant.player_id === gameState.player?.player_id)
        : null;

      if (selfParticipant) {
        partyActions.updateYourProgress({
          prompts_submitted: selfParticipant.prompts_submitted,
          copies_submitted: selfParticipant.copies_submitted,
          votes_submitted: selfParticipant.votes_submitted,
        });
      }

      partyActions.updateSessionProgress({
        players_ready_for_next_phase: status.progress.players_ready_for_next_phase,
        total_players: status.progress.total_players,
      });

      if (normalizedPhase === 'results' || status.status === 'COMPLETED') {
        endSessionAndShowResults(sessionId);
        setSyncError(null);
        return;
      }

      if (['prompt', 'copy', 'vote'].includes(normalizedPhase) && normalizedPhase !== partyState.currentStep) {
        await startRoundForPhase(normalizedPhase as PartyStep, { sessionId });
      }

      setSyncError(null);
    } catch (err) {
      setSyncError(extractErrorMessage(err) || 'Unable to sync party progress.');
    } finally {
      syncInFlightRef.current = false;
    }
  }, [endSessionAndShowResults, gameState.player, partyActions, partyState.currentStep, sessionId, startRoundForPhase]);

  useEffect(() => {
    let timeoutId: number | null = null;
    let cancelled = false;

    const poll = async () => {
      await syncSessionStatus();
      if (!cancelled) {
        timeoutId = window.setTimeout(poll, 5000);
      }
    };

    void poll();

    return () => {
      cancelled = true;
      if (timeoutId !== null) {
        window.clearTimeout(timeoutId);
      }
    };
  }, [syncSessionStatus]);

  // WebSocket updates will update context when other players make progress
  usePartyWebSocket({
    sessionId,
    pageContext: 'game',
    onProgressUpdate: () => {
      // Update session progress when we receive WebSocket updates about other players
      void syncSessionStatus();
    },
    onPhaseTransition: () => {
      // Phase transition handled elsewhere
    },
    onSessionUpdate: () => {
      // Session updates handled via REST sync
      void syncSessionStatus();
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
        className="fixed bottom-4 right-4 z-30 rounded-full bg-ccl-orange text-white px-4 py-2 shadow-tile hover:bg-ccl-orange-deep"
      >
        Show Party Status
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-ccl-navy/40 p-4">
      <div className="w-full max-w-xl rounded-tile bg-ccl-warm-ivory p-6 shadow-tile-lg relative">
        <button
          type="button"
          onClick={() => setIsOpen(false)}
          className="absolute top-4 right-4 text-ccl-teal hover:text-ccl-turquoise"
          aria-label="Close party status"
        >
          ✕
        </button>

        <div className="flex items-center gap-3 mb-4">
          <CircleIcon className="w-8 h-8" />
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-ccl-teal">Party Mode</p>
            <h3 className="text-2xl font-display font-bold text-ccl-navy">Quip · Impostor · Vote</h3>
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
                          ? 'bg-ccl-orange text-white'
                          : isComplete
                            ? 'bg-ccl-turquoise text-white'
                            : 'bg-gray-300 text-gray-600'
                      }`}
                    >
                      {isComplete ? '✓' : idx + 1}
                    </div>
                    <span
                      className={`text-xs mt-1 font-semibold ${isActive ? 'text-ccl-orange-deep' : 'text-ccl-teal'}`}
                    >
                      {phase.label}
                    </span>
                  </div>
                  {idx < phaseOrder.length - 1 && (
                    <div
                      className={`flex-1 h-1 mx-1 ${
                        isComplete ? 'bg-ccl-turquoise' : 'bg-gray-300'
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
            <span className="text-sm font-semibold text-ccl-teal">Your Progress</span>
            <span className="text-sm font-semibold text-ccl-teal">
              {playersReady} / {totalPlayers} players ready
            </span>
          </div>

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-ccl-navy">Quips:</span>
              <span className="font-bold text-ccl-navy">
                {prompts_submitted} / {prompts_required}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ccl-navy">Impostors:</span>
              <span className="font-bold text-ccl-navy">
                {copies_submitted} / {copies_required}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-ccl-navy">Votes:</span>
              <span className="font-bold text-ccl-navy">
                {votes_submitted} / {votes_required}
              </span>
            </div>
            {isProgressMissing && (
              <p className="text-xs text-ccl-navy/70">
                Party progress will appear once the next round response includes party context.
              </p>
            )}
          </div>

          {/* Leave Party Button */}
          <div className="mt-4 pt-4 border-t border-ccl-navy/10">
            {leaveError && (
              <p className="text-xs text-red-600 mb-2">{leaveError}</p>
            )}
            {syncError && (
              <p className="text-xs text-red-600 mb-2">{syncError}</p>
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
