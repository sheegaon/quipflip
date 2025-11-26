import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import { useGame } from '../contexts/GameContext';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { MemeCaptionOption, MemeVoteResult, MemeVoteRound } from '../api/types';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

interface VoteLocationState {
  round?: MemeVoteRound;
}

export const VoteRound: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { state: gameState, actions } = useGame();
  const { refreshDashboard } = actions;
  const locationState = (location.state as VoteLocationState) || {};

  const [round, setRound] = useState<MemeVoteRound | null>(locationState.round ?? null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [result, setResult] = useState<MemeVoteResult | null>(null);

  useEffect(() => {
    if (!round && gameState.activeRound && (gameState.activeRound.state as any)?.meme) {
      setRound(gameState.activeRound.state as unknown as MemeVoteRound);
    }
  }, [gameState.activeRound, round]);

  const selectedCaption = useMemo(() => {
    if (!round || !result) return null;
    return round.captions.find((c) => c.caption_id === result.selected_caption_id) ?? null;
  }, [result, round]);

  const handleVote = async (caption: MemeCaptionOption) => {
    if (!round || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const voteResult = await apiClient.submitMemeVote(round.round_id, caption.caption_id);
      setResult(voteResult);
      await refreshDashboard();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit your vote. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const goToCaption = () => {
    if (!round) return;
    navigate('/caption', { state: { round, voteResult: result } });
  };

  const goToResults = () => {
    navigate('/results', { state: { round, voteResult: result } });
  };

  if (!round) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading message="Loading your meme..." />
      </div>
    );
  }

  if (result) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="max-w-4xl w-full tile-card p-6 md:p-10">
          <div className="flex flex-col md:flex-row gap-6 md:items-start">
            <img
              src={round.meme.image_url}
              alt={round.meme.alt_text || 'Meme image'}
              className="w-full md:w-1/2 rounded-tile border-2 border-quip-navy"
            />
            <div className="flex-1 space-y-4">
              <p className="text-sm text-quip-teal uppercase tracking-wide">Your vote is in!</p>
              <h1 className="text-3xl font-display font-bold text-quip-navy">Thanks for playing</h1>
              {selectedCaption && (
                <div className="p-4 border-2 border-quip-teal rounded-tile bg-white">
                  <p className="text-sm text-quip-teal mb-1">You chose</p>
                  <p className="text-xl font-display text-quip-navy">{selectedCaption.text}</p>
                </div>
              )}
              <div className="p-4 border-2 border-quip-orange rounded-tile bg-white inline-flex gap-2 items-center">
                <span className="text-quip-navy font-semibold">Payout</span>
                <CurrencyDisplay amount={result.payout} />
              </div>
              <div className="flex flex-wrap gap-3 pt-2">
                <button
                  onClick={goToCaption}
                  className="bg-quip-teal hover:bg-quip-turquoise text-white font-semibold px-4 py-2 rounded-tile"
                >
                  Add your caption
                </button>
                <button
                  onClick={goToResults}
                  className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile"
                >
                  See round results
                </button>
                <button
                  onClick={() => navigate('/dashboard')}
                  className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile"
                >
                  Play again
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-10">
        <div className="flex flex-col md:flex-row gap-6 md:items-start">
          <img
            src={round.meme.image_url}
            alt={round.meme.alt_text || 'Meme image'}
            className="w-full md:w-1/2 rounded-tile border-2 border-quip-navy"
          />
          <div className="flex-1">
            <div className="flex items-center justify-between mb-4">
              <div>
                <p className="text-sm text-quip-teal uppercase tracking-wide">Vote for your favorite</p>
                <h1 className="text-3xl font-display font-bold text-quip-navy">Which caption wins?</h1>
              </div>
              {round.expires_at && <Timer expiresAt={round.expires_at} />}
            </div>

            {error && (
              <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {round.captions.map((caption) => (
                <button
                  key={caption.caption_id}
                  onClick={() => handleVote(caption)}
                  disabled={isSubmitting}
                  className="text-left bg-white border-2 border-quip-orange hover:border-quip-orange-deep rounded-tile p-4 shadow-tile-sm hover:shadow-tile transition-all disabled:opacity-60"
                >
                  <p className="text-lg font-display text-quip-navy">{caption.text}</p>
                  {caption.author && (
                    <p className="text-xs text-quip-teal mt-2">by {caption.author}</p>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoteRound;
