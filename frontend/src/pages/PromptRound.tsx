import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { useTimer } from '../hooks/useTimer';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import { promptRoundLogger } from '../utils/logger';
import type { PromptState } from '../api/types';

export const PromptRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound } = state;
  const { currentStep, advanceStep } = useTutorial();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const roundData = activeRound?.round_type === 'prompt' ? activeRound.state as PromptState : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Log component mount and key state changes
  useEffect(() => {
    promptRoundLogger.debug('Component mounted');
    promptRoundLogger.debug('Initial state:', {
      activeRound: activeRound ? {
        type: activeRound.round_type,
        id: activeRound.round_id,
        expiresAt: activeRound.expires_at
      } : 'null',
      currentStep,
      roundData: roundData ? {
        roundId: roundData.round_id,
        promptText: roundData.prompt_text,
        status: roundData.status
      } : 'null'
    });
  }, []);

  useEffect(() => {
    promptRoundLogger.debug('Active round changed:', {
      activeRound: activeRound ? {
        type: activeRound.round_type,
        id: activeRound.round_id,
        expiresAt: activeRound.expires_at
      } : 'null'
    });
  }, [activeRound]);

  useEffect(() => {
    promptRoundLogger.debug('Round data changed:', {
      roundData: roundData ? {
        roundId: roundData.round_id,
        promptText: roundData.prompt_text,
        status: roundData.status,
        cost: roundData.cost
      } : 'null'
    });
  }, [roundData]);

  // Load existing feedback
  useEffect(() => {
    if (!roundData) return;

    const controller = new AbortController();
    const loadFeedback = async () => {
      try {
        const feedbackResponse = await apiClient.getPromptFeedback(roundData.round_id, controller.signal);
        setFeedbackType(feedbackResponse.feedback_type);
      } catch (err: any) {
        // Feedback not found or aborted is ok
        if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
          console.debug('Feedback not found:', err);
        }
      }
    };
    loadFeedback();

    return () => controller.abort();
  }, [roundData?.round_id]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      promptRoundLogger.debug('Round already submitted, redirecting to dashboard');
      navigate('/dashboard');
    }
  }, [roundData?.status, navigate]);

  // Redirect if no active prompt round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'prompt') {
      promptRoundLogger.debug('No active prompt round detected');
      promptRoundLogger.debug('Redirect logic:', {
        hasActiveRound: !!activeRound,
        roundType: activeRound?.round_type,
        currentStep,
        isTutorialPromptStep: currentStep === 'prompt_round',
        successMessage: !!successMessage
      });

      // Don't start a new round if we're showing success message (submission in progress)
      if (successMessage) {
        promptRoundLogger.debug('Success message showing, not starting new round');
        return;
      }

      // Special case for tutorial
      if (currentStep === 'prompt_round') {
        promptRoundLogger.debug('Tutorial mode: advancing to copy_round and returning to dashboard');
        advanceStep('copy_round').then(() => navigate('/dashboard'));
      } else {
        promptRoundLogger.debug('No active round and not in tutorial - redirecting to dashboard');
        navigate('/dashboard');
      }
    } else {
      promptRoundLogger.debug('✅ Active prompt round found, staying on page');
    }
  }, [activeRound, currentStep, advanceStep, navigate, successMessage]);

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
    promptRoundLogger.debug('Form submitted, checking conditions...', {
      hasPhrase: !!phrase.trim(),
      hasRoundData: !!roundData,
      isSubmitting,
      roundStatus: roundData?.status
    });

    if (!phrase.trim() || !roundData || isSubmitting) {
      promptRoundLogger.debug('Submission blocked - conditions not met');
      return;
    }

    // Check if round is already submitted
    if (roundData.status === 'submitted') {
      promptRoundLogger.debug('Round already submitted, ignoring submission attempt');
      return;
    }

    promptRoundLogger.info('Starting submission process...', { phrase: phrase.trim(), roundId: roundData.round_id });
    setIsSubmitting(true);
    setError(null);

    // Create abort controller for this submission
    const controller = new AbortController();

    try {
      await apiClient.submitPhrase(roundData.round_id, phrase.trim());
      promptRoundLogger.info('✅ Phrase submitted successfully');

      // Show success message first to prevent navigation race condition
      setSuccessMessage(getRandomMessage('promptSubmitted'));

      // Update the round state in background with abort signal
      if (activeRound) {
        promptRoundLogger.debug('Triggering dashboard refresh in background');
        actions.refreshDashboard(controller.signal).catch((err) => {
          if (err.name !== 'AbortError') {
            promptRoundLogger.warn('Background dashboard refresh failed:', err);
          }
        });
      }

      // Advance tutorial if in prompt_round step
      if (currentStep === 'prompt_round') {
        await advanceStep('copy_round');
      }

      // Navigate after delay
      setTimeout(() => {
        promptRoundLogger.info('Navigating to dashboard after successful submission');
        controller.abort(); // Cancel any pending refresh
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      promptRoundLogger.error('Submission failed:', err);
      controller.abort();
      setError(extractErrorMessage(err) || 'Unable to submit your phrase. Please check your connection and try again.');
      setIsSubmitting(false);
    }
  };

  if (!roundData) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
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
          disabled={isSubmitting}
          className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
          title={isSubmitting ? "Please wait for submission to complete" : "Back to Dashboard"}
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
