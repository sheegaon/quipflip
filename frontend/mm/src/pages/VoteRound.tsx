import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { extractErrorMessage } from '@crowdcraft/api/client.ts';
import { useGame } from '../contexts/GameContext';
import { LoadingSpinner } from '../components/LoadingSpinner';
import type { MMMemeVoteResult, MMVoteRoundState, MMVoteResult, Caption } from '@crowdcraft/api/types.ts';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { BotIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { CircleIcon } from '@crowdcraft/components/icons/NavigationIcons.tsx';

interface VoteLocationState {
  round?: MMVoteRoundState;
  voteResult?: MMMemeVoteResult | null;
}

export const VoteRound: React.FC = () => {
  const navigate = useNavigate();
  const locationState = (useLocation().state as VoteLocationState) || {};
  const {
    state: { currentVoteRound, roundAvailability },
    actions,
  } = useGame();

  const [round, setRound] = useState<MMVoteRoundState | null>(locationState.round ?? currentVoteRound ?? null);
  const [result, setResult] = useState<MMVoteResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingRound, setIsLoadingRound] = useState(false);

  const voteCost = roundAvailability?.round_entry_cost ?? 5;
  const freeCaptionAvailable = (roundAvailability?.free_captions_remaining ?? 0) > 0;
  const captionCost = freeCaptionAvailable ? 0 : (roundAvailability?.caption_submission_cost ?? 100);
  const hasVoted = Boolean(result);

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
  }, [actions, isLoadingRound, round]);

  const isBotAuthor = (caption: Caption) => {
    return Boolean(
      caption.is_bot ||
        caption.is_ai ||
        caption.is_system ||
        caption.is_seed_caption ||
        caption.author_username == null,
    );
  };

  const isCircleAuthor = (caption: Caption) => {
    return Boolean(caption.is_circle_member ?? caption.in_circle);
  };

  const handleVote = async (caption: Caption) => {
    if (!round || isSubmitting || hasVoted) return;
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

  const handleAbandonRound = async () => {
    if (round) {
      try {
        await actions.abandonRound(round.round_id);
      } catch (err) {
        console.warn('Failed to abandon vote round', err);
      }
    }

    navigate('/dashboard');
  };

  const payoutAmount = result ? result.refund_amount ?? result.payout : 0;
  const payoutLabel = result?.refund_amount != null ? 'Refund' : 'Payout';

  if (!round) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading message="Loading your meme..." />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-5xl w-full tile-card p-6 md:p-10 relative">
        <button
          type="button"
          onClick={handleAbandonRound}
          className="absolute top-4 right-4 text-ccl-navy hover:opacity-80 transition transform hover:scale-105"
          aria-label="Return to dashboard"
        >
          <svg className="h-7 w-7" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.08" />
            <path d="M8 8L16 16M16 8L8 16" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
        <div className="flex flex-col md:flex-row gap-6 md:items-start">
          <div className="w-full md:w-1/2">
            <img
              src={round.image_url}
              alt={round.attribution_text || 'Meme image'}
              className="w-full rounded-tile border-2 border-ccl-navy max-h-96 object-contain bg-white"
            />
            {hasVoted && result && (
              <div className="mt-4 text-center">
                <p className="text-sm text-ccl-teal uppercase tracking-wide">{payoutLabel}</p>
                <div className="text-2xl font-bold text-ccl-navy flex items-center justify-center gap-2">
                  <CurrencyDisplay amount={payoutAmount} iconClassName="w-6 h-6" textClassName="text-2xl" />
                </div>
              </div>
            )}
          </div>

          {/* Voting Interface */}
          <div className="flex-1 space-y-6">
            <div>
              <h1 className="text-3xl font-display font-bold text-ccl-navy">Choose your favorite caption</h1>
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
                  disabled={isSubmitting || hasVoted}
                  className={`w-full text-left p-4 rounded-tile border-2 border-ccl-navy hover:border-ccl-teal hover:bg-ccl-teal hover:bg-opacity-5 disabled:opacity-60 disabled:cursor-not-allowed transition-colors ${
                    hasVoted && result?.chosen_caption_id === caption.caption_id
                      ? 'border-ccl-orange bg-ccl-orange bg-opacity-10 shadow-lg shadow-ccl-orange/20'
                      : hasVoted
                      ? 'opacity-70'
                      : ''
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <span className="flex-shrink-0 w-6 h-6 rounded-full bg-ccl-navy text-white text-sm flex items-center justify-center font-semibold">
                      {String.fromCharCode(65 + index)}
                    </span>
                    <div className="flex-1 space-y-2">
                      <p className="text-ccl-navy font-medium">{caption.text}</p>
                      {hasVoted && (
                        <div className="flex items-center gap-2 text-sm text-ccl-navy/80">
                          <span className="font-semibold">{caption.author_username ?? 'Mint Mixer'}</span>
                          <div className="flex items-center gap-1 text-ccl-navy">
                            {isBotAuthor(caption) && <BotIcon className="h-4 w-4" />}
                            {isCircleAuthor(caption) && <CircleIcon className="h-4 w-4" />}
                          </div>
                        </div>
                      )}
                    </div>
                  </div>
                </button>
              ))}
            </div>

            {hasVoted && (
                <p className="text-sm font-semibold text-ccl-navy">Add your own caption or play again below.</p>
            )}

            {hasVoted && result && (
              <div className="space-y-4 pt-4">
                <div className="flex flex-wrap gap-3">
                  <button
                    onClick={goToCaption}
                    className="bg-ccl-teal hover:bg-ccl-turquoise text-white font-semibold px-4 py-2 rounded-tile flex items-center gap-2"
                  >
                    <span>Add your caption</span>
                    <CurrencyDisplay amount={captionCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                  </button>
                  <button
                    onClick={handlePlayAgain}
                    className="border-2 border-ccl-navy text-ccl-navy font-semibold px-4 py-2 rounded-tile hover:bg-ccl-navy hover:text-white transition-colors flex items-center gap-2"
                  >
                    <span>Play again</span>
                    <CurrencyDisplay amount={voteCost} iconClassName="w-4 h-4" textClassName="font-semibold" />
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default VoteRound;
