import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import type { MemeVoteResult, MemeVoteRound } from '../api/types';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { CaptionSubmissionModal } from '../components/CaptionSubmissionModal';

interface ResultsLocationState {
  round?: MemeVoteRound;
  voteResult?: MemeVoteResult | null;
}

export const Results: React.FC = () => {
  const navigate = useNavigate();
  const { state: gameState } = useGame();
  const { player, roundAvailability } = gameState;
  const locationState = (useLocation().state as ResultsLocationState) || {};
  const round = locationState.round;
  const voteResult = locationState.voteResult;
  const [isCaptionModalOpen, setIsCaptionModalOpen] = useState(false);

  const selectedCaption = round && voteResult
    ? round.captions.find((c) => c.caption_id === voteResult.selected_caption_id)
    : null;

  const canSubmitCaption = round && voteResult && !voteResult.has_submitted_caption;

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-10">
        <div className="flex flex-col md:flex-row gap-6 md:items-start">
          {round && (
            <img
              src={round.meme.image_url}
              alt={round.meme.alt_text || 'Meme image'}
              className="w-full md:w-1/2 rounded-tile border-2 border-ccl-navy"
            />
          )}
          <div className="flex-1 space-y-4">
            <div>
              <p className="text-sm text-ccl-teal uppercase tracking-wide">Round complete</p>
              <h1 className="text-3xl font-display font-bold text-ccl-navy">Here are your results</h1>
            </div>

            {voteResult ? (
              <>
                {selectedCaption && (
                  <div className="p-4 border-2 border-ccl-teal rounded-tile bg-white">
                    <p className="text-sm text-ccl-teal mb-1">You chose</p>
                    <p className="text-xl font-display text-ccl-navy">{selectedCaption.text}</p>
                  </div>
                )}

                <div className="p-4 border-2 border-ccl-orange rounded-tile bg-white inline-flex gap-2 items-center">
                  <span className="text-ccl-navy font-semibold">Earnings</span>
                  <CurrencyDisplay amount={voteResult.payout} />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="border-2 border-ccl-navy rounded-tile p-4">
                    <p className="text-sm text-ccl-teal">Wallet</p>
                    <CurrencyDisplay amount={voteResult.wallet ?? player?.wallet ?? 0} />
                  </div>
                  <div className="border-2 border-ccl-navy rounded-tile p-4">
                    <p className="text-sm text-ccl-teal">Vault</p>
                    <CurrencyDisplay amount={voteResult.vault ?? player?.vault ?? 0} />
                  </div>
                </div>
              </>
            ) : (
              <p className="text-ccl-teal">No recent round found. Head back to play again!</p>
            )}

            <div className="flex flex-wrap gap-3 pt-2">
              {canSubmitCaption && (
                <button
                  onClick={() => setIsCaptionModalOpen(true)}
                  className="bg-ccl-teal hover:bg-ccl-turquoise text-white font-semibold px-4 py-2 rounded-tile"
                >
                  Add your caption
                </button>
              )}
              <button
                onClick={() => navigate('/dashboard')}
                className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-semibold px-4 py-2 rounded-tile"
              >
                Play again
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Caption Submission Modal */}
      {canSubmitCaption && round && (
        <CaptionSubmissionModal
          isOpen={isCaptionModalOpen}
          onClose={() => setIsCaptionModalOpen(false)}
          round={round}
          freeCaptionsRemaining={roundAvailability?.free_captions_remaining}
        />
      )}
    </div>
  );
};

export default Results;
