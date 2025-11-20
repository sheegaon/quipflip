import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useGame } from '../../contexts/GameContext';
import { usePartyWebSocket } from '../../hooks/usePartyWebSocket';
import apiClient from '../../api/client';
import type { PartySessionStatusResponse } from '../../api/types';
import { PartyIcon } from '../icons/NavigationIcons';
import { PartyStep } from '../../contexts/PartyModeContext';

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
  const { state: gameState } = useGame();
  const [sessionStatus, setSessionStatus] = useState<PartySessionStatusResponse | null>(null);
  const [isOpen, setIsOpen] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadStatus = useCallback(async () => {
    if (!sessionId) return;

    setIsLoading(true);
    try {
      const status = await apiClient.getPartySessionStatus(sessionId);
      setSessionStatus(status);
      setError(null);
    } catch (err) {
      console.error('Failed to load party session status', err);
      setError('Unable to refresh party status right now.');
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  const handleSessionUpdate = useCallback(
    (payload: unknown) => {
      const maybeStatus = payload as Partial<PartySessionStatusResponse>;
      const hasParticipants = Array.isArray(maybeStatus.participants);
      const hasProgress =
        typeof maybeStatus.progress === 'object' && maybeStatus.progress !== null;
      const hasPhase = typeof maybeStatus.current_phase === 'string';

      if (hasParticipants && hasProgress && hasPhase) {
        setSessionStatus(maybeStatus as PartySessionStatusResponse);
        setError(null);
        return;
      }

      void loadStatus();
    },
    [loadStatus]
  );

  usePartyWebSocket({
    sessionId,
    onProgressUpdate: () => void loadStatus(),
    onPhaseTransition: () => void loadStatus(),
    onSessionUpdate: handleSessionUpdate,
  });

  const currentPlayer = useMemo(() => {
    if (!sessionStatus || !gameState.player?.player_id) return null;
    return sessionStatus.participants.find((p) => p.player_id === gameState.player?.player_id) ?? null;
  }, [sessionStatus, gameState.player?.player_id]);

  const playersReady = sessionStatus?.progress.players_ready_for_next_phase ?? 0;
  const totalPlayers = sessionStatus?.progress.total_players ?? 0;

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

          {error && (
            <p className="text-sm text-red-600 mb-2">{error}</p>
          )}

          {isLoading && (
            <p className="text-sm text-quip-teal mb-2">Refreshing party status...</p>
          )}

          <div className="space-y-2 text-sm">
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Quips:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer?.prompts_submitted ?? 0} / {currentPlayer?.prompts_required ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Impostors:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer?.copies_submitted ?? 0} / {currentPlayer?.copies_required ?? 0}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-quip-navy">Votes:</span>
              <span className="font-bold text-quip-navy">
                {currentPlayer?.votes_submitted ?? 0} / {currentPlayer?.votes_required ?? 0}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyRoundModal;
