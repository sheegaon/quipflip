import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { ThumbFeedbackButton } from '../components/ThumbFeedbackButton';
import { useTimer } from '../hooks/useTimer';
import { usePhraseValidation } from '../hooks/usePhraseValidation';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { PromptState, SubmitPhraseResponse } from '../api/types';
import { promptRoundLogger } from '../utils/logger';
import { TrackingIcon } from '../components/icons/NavigationIcons';
import { usePartyMode } from '../contexts/PartyModeContext';
import PartyRoundModal from '../components/party/PartyRoundModal';
import { usePartyRoundCoordinator } from '../hooks/usePartyRoundCoordinator';
import { usePartyNavigation } from '../hooks/usePartyNavigation';

const isCanceledRequest = (error: unknown): boolean => {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const maybeError = error as { name?: string; code?: string };
  return maybeError.name === 'AbortError' || maybeError.name === 'CanceledError' || maybeError.code === 'ERR_CANCELED';
};

export const PromptRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability } = state;
  const { refreshDashboard } = actions;
  const { state: partyState, actions: partyActions } = usePartyMode();
  const { setCurrentStep } = partyActions;
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [feedbackType, setFeedbackType] = useState<'like' | 'dislike' | null>(null);
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [feedbackMessage, setFeedbackMessage] = useState<string | null>(null);

  const { transitionToNextRound, isTransitioning: isStartingNextRound, error: nextRoundError } = usePartyRoundCoordinator();
  const { navigateHome, isInPartyMode } = usePartyNavigation();

  const { isPhraseValid, trimmedPhrase } = usePhraseValidation(phrase);

  const roundData = activeRound?.round_type === 'prompt' ? activeRound.state as PromptState : null;

  // Get dynamic penalty from config or use default
  const abandonedPenalty = roundAvailability?.abandoned_penalty || 5;
  const { isExpired } = useTimer(roundData?.expires_at || null);



  const partyOverlay = partyState.isPartyMode && partyState.sessionId ? (
    <PartyRoundModal sessionId={partyState.sessionId} currentStep="prompt" />
  ) : null;

  useEffect(() => {
    if (partyState.isPartyMode) {
      setCurrentStep('prompt');
    }
  }, [partyState.isPartyMode, setCurrentStep]);

  useEffect(() => {
    if (!roundData) {
      promptRoundLogger.debug('Prompt round page mounted without active round');
    } else {
      promptRoundLogger.debug('Prompt round page mounted', {
        roundId: roundData.round_id,
        expiresAt: roundData.expires_at,
        status: roundData.status,
      });
    }
  }, [roundData?.round_id, roundData?.expires_at, roundData?.status]);

  // Load existing feedback
  useEffect(() => {
    if (!roundData) return;

    const controller = new AbortController();
    const loadFeedback = async () => {
      try {
        const feedbackResponse = await apiClient.getPromptFeedback(roundData.round_id, controller.signal);
        setFeedbackType(feedbackResponse.feedback_type);
        promptRoundLogger.debug('Loaded existing prompt feedback', {
          roundId: roundData.round_id,
          feedbackType: feedbackResponse.feedback_type,
        });
      } catch (err: unknown) {
        // Feedback not found or aborted is ok
        if (!isCanceledRequest(err)) {
          promptRoundLogger.warn('Failed to load existing feedback', err);
        }
      }
    };
    loadFeedback();

    return () => controller.abort();
  }, [roundData?.round_id]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      if (partyState.isPartyMode) {
        navigate('/copy');
      } else {
        navigate('/dashboard');
      }
    }
  }, [partyState.isPartyMode, roundData?.status, navigate]);

  // In party mode, DON'T automatically transition to the next round
  // Instead, wait for the session phase to change on the backend
  // The PartyRoundModal will show progress until everyone is ready
  // useEffect(() => {
  //   if (successMessage && isInPartyMode) {
  //     transitionToNextRound('prompt').catch(err => {
  //       console.error('Failed to transition to copy round:', err);
  //     });
  //   }
  // }, [successMessage, isInPartyMode, transitionToNextRound]);

  // Redirect if no active prompt round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'prompt') {
      // Don't navigate if we're showing success message (submission in progress)
      if (successMessage) {
        return;
      }

      // Add a small delay to prevent race conditions during navigation
      const timeoutId = setTimeout(() => {
        const fallbackPath = partyState.isPartyMode && partyState.sessionId
          ? `/party/game/${partyState.sessionId}`
          : '/dashboard';
        navigate(fallbackPath);
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, navigate, partyState.isPartyMode, partyState.sessionId, successMessage]);

  const handleFeedback = async (type: 'like' | 'dislike') => {
    if (!roundData || isSubmittingFeedback) return;

    const newFeedbackType = feedbackType === type ? null : type;

    try {
      setIsSubmittingFeedback(true);
      promptRoundLogger.debug('Submitting prompt feedback', {
        roundId: roundData.round_id,
        feedbackType: newFeedbackType,
      });
      if (newFeedbackType === null) return; // Can't delete feedback yet

      await apiClient.submitPromptFeedback(roundData.round_id, newFeedbackType);
      setFeedbackType(newFeedbackType);
      promptRoundLogger.info('Prompt feedback submitted', {
        roundId: roundData.round_id,
        feedbackType: newFeedbackType,
      });
    } catch (err) {
      promptRoundLogger.error('Failed to submit feedback', err);
    } finally {
      setIsSubmittingFeedback(false);
    }
  };



  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!roundData || isSubmitting || !isPhraseValid) {
      return;
    }

    // Check if round is already submitted
    if (roundData.status === 'submitted') {
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      promptRoundLogger.debug('Submitting prompt round phrase', {
        roundId: roundData.round_id,
      });
      const response: SubmitPhraseResponse = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

      // Update party context if present
      if (response.party_context && partyState.isPartyMode) {
        partyActions.updateFromPartyContext(response.party_context);
        promptRoundLogger.debug('Updated party context after submission', {
          yourProgress: response.party_context.your_progress,
        });
      }

      // Show success messages first to prevent navigation race condition
      const heading = getRandomMessage('promptSubmitted');
      const feedback = getRandomMessage('promptSubmittedFeedback');
      setSuccessMessage(heading);
      setFeedbackMessage(feedback);
      promptRoundLogger.info('Prompt round phrase submitted successfully', {
        roundId: roundData.round_id,
        message: heading,
      });

      // Immediately refresh dashboard to clear the active round state
      // This is the proper way to handle normal completion vs timer expiry
      try {
        promptRoundLogger.debug('Refreshing dashboard immediately after successful submission to clear active round');
        await refreshDashboard();
        promptRoundLogger.debug('Dashboard refreshed successfully - active round should now be cleared');
      } catch (refreshErr) {
        promptRoundLogger.warn('Failed to refresh dashboard after submission:', refreshErr);
        // Continue with navigation even if refresh fails
      }

      // Navigate after delay - dashboard should now show no active round
      setTimeout(() => {
        if (!partyState.isPartyMode) {
          promptRoundLogger.debug('Navigating back to dashboard after prompt submission');
          navigate('/dashboard');
        }
      }, 2000);
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to submit your phrase. Please check your connection and try again.';
      promptRoundLogger.error('Failed to submit prompt round phrase', err);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  // Show success state
  if (successMessage) {
    return (
      <>
        {partyOverlay}
        <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
          <div className="tile-card max-w-md w-full p-8 text-center flip-enter space-y-2">
            <div className="flex justify-center mb-4">
              <TrackingIcon className="w-24 h-24" />
            </div>
            <h2 className="text-2xl font-display font-bold text-quip-turquoise mb-2 success-message">
              {successMessage}
            </h2>
            <p className="text-lg text-quip-teal mb-4">{feedbackMessage}</p>
            <p className="text-sm text-quip-teal">
              {isInPartyMode ? 'Starting the impostor round...' : 'Returning to dashboard...'}
            </p>
            {isStartingNextRound && isInPartyMode && (
              <p className="text-xs text-quip-teal">Loading the next round now...</p>
            )}
            {nextRoundError && (
              <div className="mt-2 text-sm text-red-600">
                {nextRoundError}
                <button
                  type="button"
                  onClick={() => transitionToNextRound('prompt')}
                  className="ml-2 underline text-quip-orange hover:text-quip-orange-deep"
                >
                  Retry
                </button>
              </div>
            )}
          </div>
        </div>
      </>
    );
  }

  if (!roundData) {
    return (
      <>
        {partyOverlay}
        <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
          <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
        </div>
      </>
    );
  }

  return (
    <>
      {partyOverlay}
      <div className="min-h-screen bg-gradient-to-br from-quip-navy to-quip-teal flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-2">
              <TrackingIcon className="w-8 h-8" />
              <h1 className="text-3xl font-display font-bold text-quip-navy">Quip Round</h1>
            </div>
            <p className="text-quip-teal">Write an original quip for the prompt</p>
          </div>

          {/* Timer */}
          <div className="flex justify-center mb-6">
            <Timer expiresAt={roundData.expires_at} />
          </div>

          {/* Instructions */}
          <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-4 mb-6">
            <p className="text-sm text-quip-navy">
              <strong>💡 Tip:</strong> Type a short phrase that completes the sentence.
            </p>
          </div>

          {/* Prompt */}
          <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-6 py-8 mb-6 relative min-h-[120px] flex items-center">
            <p className="text-xl md:text-2xl text-center font-display font-semibold text-quip-navy flex-1 pr-12">
              {roundData.prompt_text}
            </p>

            {/* Feedback Icons */}
            <div className="absolute top-1 md:top-2 right-1 md:right-3 flex gap-1 md:gap-1.5">
              <ThumbFeedbackButton
                type="like"
                isActive={feedbackType === 'like'}
                onClick={() => handleFeedback('like')}
                disabled={isSubmittingFeedback || roundData.status === 'submitted'}
              />
              <ThumbFeedbackButton
                type="dislike"
                isActive={feedbackType === 'dislike'}
                onClick={() => handleFeedback('dislike')}
                disabled={isSubmittingFeedback || roundData.status === 'submitted'}
              />
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
                2-5 words (4-100 characters), A-Z and spaces only, must not repeat prompt, no proper nouns
              </p>
            </div>

            <button
              type="submit"
              disabled={isExpired || isSubmitting || !isPhraseValid}
              className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
            >
              {isExpired ? "Time's Up" : isSubmitting ? loadingMessages.submitting : 'Submit Phrase'}
            </button>
          </form>

          {/* Home Button */}
          <button
            onClick={navigateHome}
            disabled={isSubmitting}
            className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise disabled:opacity-50 disabled:cursor-not-allowed py-2 font-medium transition-colors"
            title={isSubmitting ? "Please wait for submission to complete" : isInPartyMode ? "Leave Party Mode" : "Back to Dashboard"}
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
            </svg>
            <span>{isInPartyMode ? 'Exit Party Mode' : 'Back to Dashboard'}</span>
          </button>

          {/* Info */}
          <div className="mt-6 p-4 bg-quip-navy bg-opacity-5 rounded-tile">
            <p className="text-sm text-quip-teal">
              <strong className="text-quip-navy">Cost:</strong> <CurrencyDisplay amount={roundData.cost} iconClassName="w-3 h-3" textClassName="text-sm" /> (<CurrencyDisplay amount={roundData.cost - abandonedPenalty} iconClassName="w-3 h-3" textClassName="text-sm" /> refunded if you don't submit in time)
            </p>
          </div>
        </div>
      </div>
    </>
  );
};

export default PromptRound;
