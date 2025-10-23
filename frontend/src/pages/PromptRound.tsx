import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';

export const PromptRound: React.FC = () => {
  const { state } = useGame();
  const { activeRound } = state;
  const { currentStep, advanceStep } = useTutorial();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const roundData = activeRound?.round_type === 'prompt' ? activeRound.state : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Load existing feedback
  useEffect(() => {
    if (!roundData) return;

    const loadFeedback = async () => {
      try {
        const feedbackResponse = await apiClient.getPromptFeedback(roundData.round_id);
        setFeedbackType(feedbackResponse.feedback_type);
      } catch (err) {
        // Feedback not found is ok
      }
    };
    loadFeedback();
  }, [roundData?.round_id]);

  // Redirect if no active prompt round
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'prompt') {
      // Special case for tutorial
      if (currentStep === 'prompt_round') {
        advanceStep('copy_round').then(() => navigate('/dashboard'));
      } else {
        // Start a new round
        apiClient.startPromptRound()
          .catch(() => navigate('/dashboard'));
      }
    }
  }, [activeRound, currentStep, advanceStep, navigate]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      navigate('/dashboard');
    }
  }, [roundData?.status, navigate]);

  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!roundData || isSubmittingFeedback) return;

    const newFeedbackType = feedbackType === type ? null : type;

    try {
      setIsSubmittingFeedback(true);
      if (newFeedbackType === null) return; // Can't delete feedback yet

      await apiClient.submitPromptFeedback(roundData.round_id, newFeedbackType);
      setFeedbackType(newFeedbackType);
    } catch (err) {
      console.error('Failed to submit feedback:', err);
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

      // Show success message
      setSuccessMessage(getRandomMessage('promptSubmitted'));

      // Advance tutorial if in prompt_round step
      if (currentStep === 'prompt_round') {
        await advanceStep('copy_round');
      }

      // Navigate after delay
      setTimeout(() => navigate('/dashboard'), 1500);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to submit your phrase. Please check your connection and try again.');
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

        {/* Instructions */}
        <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
          <p className="text-sm text-quip-navy">
            <strong>💡 Tip:</strong> Type a word or short phrase that completes the sentence.
          </p>
        </div>

        {/* Prompt */}
        <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 py-8 mb-6 relative min-h-[120px] flex items-center">
          <p className="text-xl md:text-2xl text-center font-display font-semibold text-quip-navy flex-1 pr-12">
            {roundData.prompt_text}
          </p>

          {/* Feedback Icons */}
          <div className="absolute top-1 md:top-4 right-2 md:right-5 flex gap-1 md:gap-2">
            <button
              onClick={() => handleFeedback('like')}
              disabled={isSubmittingFeedback || roundData.status === 'submitted'}
              className={`text-lg md:text-2xl transition-all ${
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
              className={`text-lg md:text-2xl transition-all ${
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
              className="tutorial-prompt-input w-full px-4 py-3 text-lg border-2 border-quip-teal rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
              disabled={isExpired || isSubmitting}
              maxLength={100}
            />
            <p className="text-sm text-quip-teal mt-1">
              1-5 words (4-100 characters), A-Z and spaces only
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
