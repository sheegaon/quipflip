import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { PromptState } from '../api/types';

export const PromptRound: React.FC = () => {
  const { activeRound, refreshCurrentRound, refreshBalance } = useGame();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [roundData, setRoundData] = useState<PromptState | null>(null);
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const hasInitialized = useRef(false);

  const { isExpired } = useTimer(roundData?.expires_at || null);

  useEffect(() => {
    // Prevent duplicate calls in React StrictMode
    if (hasInitialized.current) return;
    hasInitialized.current = true;

    const initRound = async () => {
      // Check if we have an active prompt round
      if (activeRound?.round_type === 'prompt' && activeRound.state) {
        const promptState = activeRound.state as PromptState;
        setRoundData(promptState);

        // Load existing feedback
        try {
          const feedbackResponse = await apiClient.getPromptFeedback(promptState.round_id);
          setFeedbackType(feedbackResponse.feedback_type);
        } catch (err) {
          // Feedback not found is ok, just leave as null
          console.log('No existing feedback found');
        }

        // If already submitted, redirect to dashboard
        if (promptState.status === 'submitted') {
          navigate('/dashboard');
        }
      } else {
        // No active round, start a new one
        try {
          const response = await apiClient.startPromptRound();
          await refreshCurrentRound();
          setRoundData({
            round_id: response.round_id,
            status: 'active',
            expires_at: response.expires_at,
            cost: response.cost,
            prompt_text: response.prompt_text,
          });
        } catch (err) {
          setError(extractErrorMessage(err) || 'Failed to start round');
          setTimeout(() => navigate('/dashboard'), 2000);
        }
      }
    };

    initRound();
  }, [activeRound, navigate, refreshCurrentRound]);

  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!roundData || isSubmittingFeedback) return;

    // Toggle off if clicking the same feedback type
    const newFeedbackType = feedbackType === type ? null : type;

    try {
      setIsSubmittingFeedback(true);

      if (newFeedbackType === null) {
        // For now, we just keep the last feedback since backend doesn't support deletion
        // In a future version, we could add a DELETE endpoint
        return;
      }

      await apiClient.submitPromptFeedback(roundData.round_id, newFeedbackType);
      setFeedbackType(newFeedbackType);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
      // Don't show error to user, feedback is optional
    } finally {
      setIsSubmittingFeedback(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!phrase.trim() || !roundData) return;

    setIsSubmitting(true);
    setError(null);

    try {
      await apiClient.submitPhrase(roundData.round_id, phrase.trim());
      await refreshCurrentRound();
      await refreshBalance();

      // Show success message
      const message = getRandomMessage('promptSubmitted');
      setSuccessMessage(message);

      // Navigate after brief delay
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to submit phrase');
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
            <img src="/icon_prompt.svg" alt="" className="w-24 h-24" />
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
    <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-2 mb-2">
            <img src="/icon_prompt.svg" alt="" className="w-8 h-8" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Prompt Round</h1>
          </div>
          <p className="text-quip-teal">Submit a phrase for the prompt</p>
        </div>

        {/* Timer */}
        <div className="flex justify-center mb-6">
          <Timer expiresAt={roundData.expires_at} />
        </div>

        {/* Prompt */}
        <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 mb-6 relative">
          <p className="text-2xl text-center font-display font-semibold text-quip-navy">
            {roundData.prompt_text}
          </p>

          {/* Feedback Icons */}
          <div className="absolute top-4 right-4 flex gap-2">
            <button
              onClick={() => handleFeedback('like')}
              disabled={isSubmittingFeedback || roundData.status === 'submitted'}
              className={`text-2xl transition-all ${
                feedbackType === 'like'
                  ? 'opacity-100 scale-110'
                  : 'opacity-40 hover:opacity-70 hover:scale-105'
              } disabled:opacity-30 disabled:cursor-not-allowed`}
              title="I like this prompt"
              aria-label="Like this prompt"
            >
              👍
            </button>
            <button
              onClick={() => handleFeedback('dislike')}
              disabled={isSubmittingFeedback || roundData.status === 'submitted'}
              className={`text-2xl transition-all ${
                feedbackType === 'dislike'
                  ? 'opacity-100 scale-110'
                  : 'opacity-40 hover:opacity-70 hover:scale-105'
              } disabled:opacity-30 disabled:cursor-not-allowed`}
              title="I dislike this prompt"
              aria-label="Dislike this prompt"
            >
              👎
            </button>
          </div>
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
              className="w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
              disabled={isExpired || isSubmitting}
              maxLength={100}
            />
            <p className="text-sm text-quip-teal mt-1">
              1-5 words (2-100 characters), A-Z and spaces only
            </p>
          </div>

          <button
            type="submit"
            disabled={isExpired || isSubmitting || !phrase.trim()}
            className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
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
        <div className="mt-6 p-4 bg-quip-navy bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Cost:</strong> ${roundData.cost} ($95 refunded if you don't submit in time)
          </p>
        </div>
      </div>
    </div>
  );
};
