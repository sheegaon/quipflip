import React, { useState } from 'react';
import { usePartyMode } from '../../contexts/PartyModeContext';
import { usePartyWebSocket } from '../../hooks/usePartyWebSocket';
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
  const { state: partyState } = usePartyMode();
  const [isOpen, setIsOpen] = useState(true);
  const isProgressMissing = !partyState.yourProgress || !partyState.sessionConfig;

  // WebSocket updates will update context automatically via submission responses
  // This hook just listens for phase transitions
  usePartyWebSocket({
    sessionId,
    pageContext: 'game',
    onProgressUpdate: () => {
      // Context is already updated by submission response
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
        </div>
      </div>
    </div>
  );
};

export default PartyRoundModal;
