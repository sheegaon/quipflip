import React, { useEffect, useMemo, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '../api/client';
import { useGame } from '../contexts/GameContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { MemeVoteResult, VoteRoundState, VoteResult, Caption } from '../api/types';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { HomeIcon } from '../components/icons/NavigationIcons';

interface VoteLocationState {
  round?: VoteRoundState;
  voteResult?: MemeVoteResult | null;
}

export const VoteRound: React.FC = () => {
  const navigate = useNavigate();
  const locationState = (useLocation().state as VoteLocationState) || {};
  const {
    state: { currentVoteRound, roundAvailability },
    actions,
  } = useGame();

  const [round, setRound] = useState<VoteRoundState | null>(locationState.round ?? currentVoteRound ?? null);
  const [result, setResult] = useState<VoteResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingRound, setIsLoadingRound] = useState(false);

  const voteCost = roundAvailability?.round_entry_cost ?? 5;
  const captionCost = roundAvailability?.caption_submission_cost ?? 100;

  // recover round when arriving without navigation state
  useEffect(() => {
    if (round || isLoadingRound) return;

    setIsLoadingRound(true);
    const controller = new AbortController();

    actions
      .startVoteRound(controller.signal)
      .then(setRound)
      .catch((err) => {
        console.error('Failed to start vote round:', err);
        setError(extractErrorMessage(err) || 'Unable to start a vote round.');
      })
      .finally(() => setIsLoadingRound(false));

    return () => {
      controller.abort();
      setIsLoadingRound(false);
    };
  }, [actions, round]);

  const selectedCaption = useMemo(() => {
    if (!round || !result) return null;
    return round.captions.find((c) => c.caption_id === result.chosen_caption_id) ?? null;
  }, [result, round]);

  const handleVote = async (caption: Caption) => {
    if (!round || isSubmitting) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const voteResult = await actions.submitVote(round.round_id, caption.caption_id);
      setResult(voteResult);
      await actions.refreshDashboard();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit your vote. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const goToCaption = () => {
    if (!round) return;
    navigate('/game/caption', { state: { round, voteResult: result } });
  };

  const handlePlayAgain = async () => {
    setError(null);
    setResult(null);
    setIsLoadingRound(true);
    setRound(null);

    try {
      const newRound = await actions.startVoteRound();
      setRound(newRound);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to start a new vote round. Please try again.');
    } finally {
      setIsLoadingRound(false);
    }
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
              src={round.image_url}
              alt={round.attribution_text || 'Meme image'}
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
                  className="bg-quip-teal hover:bg-quip-turquoise text-white font-semibold px-4 py-2 rounded-tile flex items-center gap-2"
                >
                  <span>Add your caption</span>
                  <CurrencyDisplay amount={captionCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                </button>
                {/* TODO: Enable when round results feature is implemented
                <button
                  onClick={goToResults}
                  className="bg-quip-orange hover:bg-quip-orange-deep text-white font-semibold px-4 py-2 rounded-tile"
                >
                  See round results
                </button>
                */}
                <button
                  onClick={handlePlayAgain}
                  className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile hover:bg-quip-navy hover:text-white transition-colors flex items-center gap-2"
                >
                  <span>Play again</span>
                  <CurrencyDisplay amount={voteCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                </button>
                <button
                  onClick={() => navigate('/dashboard')}
                  className="border-2 border-quip-navy text-quip-navy font-semibold px-4 py-2 rounded-tile hover:bg-quip-navy hover:text-white transition-colors flex items-center gap-2"
                >
                  <HomeIcon className="w-4 h-4" />
                  <span>Back to Dashboard</span>
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
          <div className="w-full md:w-1/2">
            <img
              src={round.image_url}
              alt={round.attribution_text || 'Meme image'}
              className="w-full rounded-tile border-2 border-quip-navy max-h-96 object-contain bg-white"
            />
          </div>

          {/* Voting Interface */}
          <div className="flex-1 space-y-6">
            <div>
              <p className="text-sm text-quip-teal uppercase tracking-wide">Vote Round</p>
              <h1 className="text-3xl font-display font-bold text-quip-navy">Choose your favorite caption</h1>
            </div>

            {error && (
              <div className="p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile">
                {error}
              </div>
            )}

            {/* Caption Options */}
            <div className="tutorial-vote-options space-y-3">
              {round.captions.map((caption, index) => (
                <button
                  key={caption.caption_id}
                  onClick={() => handleVote(caption)}
                  disabled={isSubmitting}
                  className="w-full text-left p-4 rounded-tile border-2 border-quip-navy hover:border-quip-teal hover:bg-quip-teal hover:bg-opacity-5 disabled:opacity-60 disabled:cursor-not-allowed transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-quip-navy text-white text-sm flex items-center justify-center font-semibold">
                      {String.fromCharCode(65 + index)}
                    </span>
                    <div className="flex-1">
                      <p className="text-quip-navy font-medium">{caption.text}</p>
                    </div>
                  </div>
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
