import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { CopyState } from '../api/types';

export const CopyRound: React.FC = () => {
  const { activeRound } = useGame();
  const { currentStep, advanceStep } = useTutorial();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roundData, setRoundData] = useState<CopyState | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const hasInitialized = useRef(false);

  const { isExpired } = useTimer(roundData?.expires_at || null);

  useEffect(() => {
    // Prevent duplicate calls in React StrictMode
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    const initRound = async () => {
      // Check if we have an active copy round
      if (activeRound?.round_type === 'copy' && activeRound.state) {
        setRoundData(activeRound.state as CopyState);

        // If already submitted, redirect to dashboard
        if ((activeRound.state as CopyState).status === 'submitted') {
          navigate('/dashboard');
        }
      } else {
        // No active round, start a new one
        try {
          const response = await apiClient.startCopyRound();
          setRoundData({
            round_id: response.round_id,
            status: 'active',
            expires_at: response.expires_at,
            cost: response.cost,
            original_phrase: response.original_phrase,
            discount_active: response.discount_active,
          });
        } catch (err) {
          setError(extractErrorMessage(err) || 'Unable to start a copy round right now. Please check your balance or try again in a moment.');
          setTimeout(() => navigate('/dashboard'), 2000);
        }
      }
    };

    initRound();
  }, [activeRound, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phrase.trim() || !roundData) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient.submitPhrase(roundData.round_id, phrase.trim());

      // Show success message
      const message = getRandomMessage('copySubmitted');
      setSuccessMessage(message);

      // Advance tutorial if in copy_round step
      if (currentStep === 'copy_round') {
        await advanceStep('vote_round');
      }

      // Navigate after brief delay
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit your phrase. The round may have expired or there may be a connection issue.');
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

  // Show success state
  if (successMessage) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-md w-full p-8 text-center flip-enter">
          <div className="flex justify-center mb-4">
            <img src="/icon_copy.svg" alt="" className="w-24 h-24" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-turquoise mb-2 success-message">
            {successMessage}
          </h2>
          <p className="text-quip-teal">Returning to dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_copy.svg" alt="" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Copy Round</h1>
          </div>
          <p className="text-quip-teal">Submit a similar phrase</p>
        </div>

        {/* Timer */}
        <div className="flex justify-center mb-6">
          <Timer expiresAt={roundData.expires_at} />
        </div>

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>⚠️ Important:</strong> You don't know the prompt! Submit a phrase that could be similar or related to the original phrase.
          </p>
        </div>

        {/* Original Phrase */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6 mb-6">
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Original Phrase:</p>
          <p className="text-3xl text-center font-display font-bold text-quip-turquoise">
            {roundData.original_phrase}
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Input Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              value={phrase}
              onChange={(e) => setPhrase(e.target.value)}
              placeholder="Enter your phrase"
              className="tutorial-copy-input w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
              disabled={isExpired || isSubmitting}
              maxLength={100}
            />
            <p className="text-sm text-quip-teal mt-1">
              1-5 words (4-100 characters), A-Z and spaces only, must be different from the original
            </p>
          </div>

          <button
            type="submit"
            disabled={isExpired || isSubmitting || !phrase.trim()}
            className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            {isExpired ? "Time's Up" : isSubmitting ? loadingMessages.submitting : 'Submit Phrase'}
          </button>
        </form>

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
        <div className="mt-6 p-4 bg-quip-turquoise bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Cost:</strong> ${roundData.cost}
            {roundData.discount_active && (
              <span className="text-quip-turquoise font-semibold"> (10% discount!)</span>
            )}
          </p>
          <p className="text-sm text-quip-teal mt-1">
            If you don't submit, ${roundData.discount_active ? 85 : 95} will be refunded (${roundData.discount_active ? 5 : 5} penalty)
          </p>
        </div>
      </div>
    </div>
  );
};
