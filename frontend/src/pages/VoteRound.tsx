import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { VoteResponse } from '../api/types';

export const VoteRound: React.FC = () => {
  const { state } = useGame();
  const { activeRound } = state;
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [voteResult, setVoteResult] = useState<VoteResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const roundData = activeRound?.round_type === 'vote' ? activeRound.state : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Redirect if no active vote round
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'vote') {
      // Start a new round
      apiClient.startVoteRound()
        .catch(() => navigate('/dashboard'));
    }
  }, [activeRound, navigate]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      navigate('/dashboard');
    }
  }, [roundData?.status, navigate]);

  const handleVote = async (phrase: string) => {
    if (!roundData || isSubmitting) return;

    try {
      setIsSubmitting(true);
      setError(null);
      const result = await apiClient.submitVote(roundData.phraseset_id, phrase);
      setSuccessMessage(result.correct ? getRandomMessage('voteSubmitted') : null);
      setVoteResult(result);

      // Navigate after showing results for 3 seconds
      setTimeout(() => navigate('/dashboard'), 3000);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit your vote. The round may have expired or someone else may have already voted.');
      setIsSubmitting(false);
    }
  };

  if (!roundData) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner message={loadingMessages.starting} />
      </div>
    );
  }

  // Show vote result
  if (voteResult) {
    const successMsg = voteResult.correct
      ? successMessage!
      : 'Better luck next time!';
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="max-w-2xl w-full tile-card p-8 text-center flip-enter">
          <div className="flex justify-center mb-4">
            <img src="/icon_vote.svg" alt="" className="w-24 h-24" />
          </div>
          <h2 className={`text-3xl font-display font-bold mb-4 ${voteResult.correct ? 'text-quip-turquoise' : 'text-quip-orange'}`}>
            {voteResult.correct ? successMsg : 'Incorrect'}
          </h2>
          <p className="text-lg text-quip-navy mb-2">
            The original phrase was: <strong className="text-quip-turquoise">{voteResult.original_phrase}</strong>
          </p>
          <p className="text-lg text-quip-teal mb-4">
            You chose: <strong>{voteResult.your_choice}</strong>
          </p>
          {voteResult.correct && (
            <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4">
              <p className="text-2xl font-display font-bold text-quip-turquoise">
                +{voteResult.payout} Flipcoins
              </p>
              <p className="text-sm text-quip-teal">Added to your balance!</p>
            </div>
          )}
          <p className="text-sm text-quip-teal mt-6">Returning to dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-orange-deep flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_vote.svg" alt="" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Vote Round</h1>
          </div>
          <p className="text-quip-teal">Identify the original phrase</p>
        </div>

        {/* Timer */}
        <div className="flex justify-center mb-6">
          <Timer expiresAt={roundData.expires_at} />
        </div>

        {/* Prompt */}
        <div className="bg-quip-orange bg-opacity-5 border-2 border-quip-orange rounded-tile p-6 mb-6">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Prompt:</p>
          <p className="text-2xl text-center font-display font-semibold text-quip-orange-deep">
            {roundData.prompt_text}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Phrase Choices */}
        <div className="tutorial-vote-options space-y-4 mb-6">
          <p className="text-center text-quip-navy font-display font-semibold mb-4 text-lg">
            Which phrase is the original?
          </p>
          {roundData.phrases.map((phrase, idx) => (
            <button
              key={phrase}
              onClick={() => handleVote(phrase)}
              disabled={isExpired || isSubmitting}
              className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-400 text-white font-bold py-4 px-6 rounded-tile transition-all hover:shadow-tile-sm text-xl shuffle-enter"
              style={{ animationDelay: `${idx * 0.1}s` }}
            >
              {phrase}
            </button>
          ))}
        </div>

        {isExpired && (
          <div className="text-center text-quip-orange-deep font-semibold">
            Time's up! You forfeited $1
          </div>
        )}

        {/* Home Button */}
        <button
          onClick={() => navigate('/dashboard')}
          className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise py-2 font-medium transition-colors"
          title="Back to Dashboard"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>Back to Dashboard</span>
        </button>

        {/* Info */}
        <div className="mt-6 p-4 bg-quip-orange bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Cost:</strong> $1 • <strong className="text-quip-navy">Correct answer:</strong> +$5 (+$4 net)
          </p>
        </div>
      </div>
    </div>
  );
};
