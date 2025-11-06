import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { useTimer } from '../hooks/useTimer';
import { usePhraseValidation } from '../hooks/usePhraseValidation';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { CopyState, FlagCopyRoundResponse } from '../api/types';
import { copyRoundLogger } from '../utils/logger';

export const CopyRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability } = state;
  const { flagCopyRound, refreshDashboard } = actions;
  const { currentStep, advanceStep } = useTutorial();
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [showFlagConfirm, setShowFlagConfirm] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);
  const [flagError, setFlagError] = useState<string | null>(null);
  const [flagResult, setFlagResult] = useState<FlagCopyRoundResponse | null>(null);
  const [secondCopyEligibility, setSecondCopyEligibility] = useState<{
    eligible: boolean;
    cost: number;
    promptRoundId: string;
    originalPhrase: string;
  } | null>(null);
  const [isStartingSecondCopy, setIsStartingSecondCopy] = useState(false);

  const { isPhraseValid, trimmedPhrase } = usePhraseValidation(phrase);

  const roundData = activeRound?.round_type === 'copy' ? activeRound.state as CopyState : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Get dynamic penalty from config or use default
  const abandonedPenalty = roundAvailability?.abandoned_penalty || 5;

  useEffect(() => {
    if (!roundData) {
      copyRoundLogger.debug('Copy round page mounted without active round');
    } else {
      copyRoundLogger.debug('Copy round page mounted', {
        roundId: roundData.round_id,
        expiresAt: roundData.expires_at,
        status: roundData.status,
      });
    }
  }, [roundData?.round_id, roundData?.expires_at, roundData?.status]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      navigate('/dashboard');
    }
  }, [roundData?.status, navigate]);

  // Redirect if no active copy round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'copy') {
      // Don't navigate if we're showing success message (submission in progress)
      if (successMessage) {
        return;
      }

      // Add a small delay to prevent race conditions during navigation
      const timeoutId = setTimeout(() => {
        // Special case for tutorial
        if (currentStep === 'copy_round') {
          advanceStep('vote_round');
          navigate('/dashboard');
        } else {
          // Redirect to dashboard instead of starting new rounds
          navigate('/dashboard');
        }
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, currentStep, advanceStep, navigate, successMessage]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roundData || isSubmitting || !isPhraseValid) return;

    setIsSubmitting(true);
    setError(null);
    setFlagResult(null);

    try {
      copyRoundLogger.debug('Submitting copy round phrase', {
        roundId: roundData.round_id,
      });
      const response = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

      // Show success message first to prevent navigation race condition
      const message = getRandomMessage('copySubmitted');
      setSuccessMessage(message);
      copyRoundLogger.info('Copy round phrase submitted successfully', {
        roundId: roundData.round_id,
        message,
      });

      // Check if eligible for second copy
      if (response.eligible_for_second_copy && response.second_copy_cost && response.prompt_round_id && response.original_phrase) {
        setSecondCopyEligibility({
          eligible: true,
          cost: response.second_copy_cost,
          promptRoundId: response.prompt_round_id,
          originalPhrase: response.original_phrase,
        });
        copyRoundLogger.info('Player eligible for second copy', {
          cost: response.second_copy_cost,
          promptRoundId: response.prompt_round_id,
        });
      }

      // Advance tutorial if in copy_round step
      if (currentStep === 'copy_round') {
        advanceStep('vote_round');
      }

      // Immediately refresh dashboard to clear the active round state
      // This is the proper way to handle normal completion vs timer expiry
      try {
        copyRoundLogger.debug('Refreshing dashboard immediately after successful submission to clear active round');
        await refreshDashboard();
        copyRoundLogger.debug('Dashboard refreshed successfully - active round should now be cleared');
      } catch (refreshErr) {
        copyRoundLogger.warn('Failed to refresh dashboard after submission:', refreshErr);
        // Continue with navigation even if refresh fails
      }

      // Only auto-navigate if NOT eligible for second copy
      if (!response.eligible_for_second_copy) {
        // Navigate after delay - dashboard should now show no active round
        setTimeout(() => {
          copyRoundLogger.debug('Navigating back to dashboard after copy submission');
          navigate('/dashboard');
        }, 1500);
      }
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to submit your phrase. The round may have expired or there may be a connection issue.';
      copyRoundLogger.error('Failed to submit copy round phrase', err);
      setError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleOpenFlagConfirm = () => {
    setFlagError(null);
    setShowFlagConfirm(true);
  };

  const handleCancelFlag = () => {
    setShowFlagConfirm(false);
  };

  const handleConfirmFlag = async () => {
    if (!roundData) return;

    setIsFlagging(true);
    setFlagError(null);

    try {
      copyRoundLogger.debug('Flagging copy round phrase', {
        roundId: roundData.round_id,
      });
      const response = await flagCopyRound(roundData.round_id);
      setFlagResult(response);
      setSuccessMessage('Thanks for looking out!');
      setShowFlagConfirm(false);
      copyRoundLogger.info('Copy round flagged', {
        roundId: roundData.round_id,
        flagId: response.flag_id,
      });

      setTimeout(() => {
        copyRoundLogger.debug('Navigating back to dashboard after flagging copy round');
        navigate('/dashboard');
      }, 1500);
    } catch (err) {
      const message = extractErrorMessage(err, 'flag-copy-round') ||
        'Unable to flag this phrase right now. Please try again.';
      copyRoundLogger.error('Failed to flag copy round', err);
      setFlagError(message);
      setShowFlagConfirm(false);
    } finally {
      setIsFlagging(false);
    }
  };

  const handleStartSecondCopy = async () => {
    if (!secondCopyEligibility) return;

    setIsStartingSecondCopy(true);
    setError(null);

    try {
      copyRoundLogger.info('Starting second copy round', {
        promptRoundId: secondCopyEligibility.promptRoundId,
        cost: secondCopyEligibility.cost,
      });

      await apiClient.startCopyRound(secondCopyEligibility.promptRoundId);
      await refreshDashboard();

      copyRoundLogger.debug('Second copy round started, staying on page');
      // Reset states to allow for the new round
      setSuccessMessage(null);
      setSecondCopyEligibility(null);
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to start second copy round. Please try again.';
      copyRoundLogger.error('Failed to start second copy round', err);
      setError(message);
    } finally {
      setIsStartingSecondCopy(false);
    }
  };

  const handleDeclineSecondCopy = () => {
    copyRoundLogger.info('Player declined second copy option');
    navigate('/dashboard');
  };

  // Show success state
  if (successMessage) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
        <div className="tile-card max-w-2xl w-full p-8 text-center flip-enter">
          <div className="flex justify-center mb-4">
            <img src="/icon_copy.svg" alt="" className="w-24 h-24" />
          </div>
          <h2 className="text-2xl font-display font-bold text-quip-turquoise mb-2 success-message">
            {successMessage}
          </h2>
          {flagResult ? (
            <div className="text-quip-teal space-y-2">
              <p>
                We refunded{' '}
                <CurrencyDisplay
                  amount={flagResult.refund_amount}
                  iconClassName="w-4 h-4"
                  textClassName="font-semibold text-quip-turquoise"
                />
                . Our team will review this phrase shortly.
              </p>
              <p>Returning to dashboard...</p>
            </div>
          ) : secondCopyEligibility ? (
            <div className="space-y-4">
              <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-6 mb-4">
                <p className="text-lg text-quip-navy mb-3">
                  <strong>🎯 Want to submit another copy for the same phrase?</strong>
                </p>
                <p className="text-quip-teal mb-4">
                  You can submit a second copy for <strong>"{secondCopyEligibility.originalPhrase}"</strong> for{' '}
                  <CurrencyDisplay
                    amount={secondCopyEligibility.cost}
                    iconClassName="w-4 h-4"
                    textClassName="font-semibold text-quip-turquoise"
                  />
                  . This gives you two chances to match the prompt!
                </p>
              </div>

              {error && (
                <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                  {error}
                </div>
              )}

              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <button
                  onClick={handleStartSecondCopy}
                  disabled={isStartingSecondCopy}
                  className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  {isStartingSecondCopy ? 'Starting...' : `Submit Second Copy (${secondCopyEligibility.cost} FC)`}
                </button>
                <button
                  onClick={handleDeclineSecondCopy}
                  disabled={isStartingSecondCopy}
                  className="bg-white hover:bg-gray-50 border-2 border-quip-navy text-quip-navy font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm disabled:opacity-50"
                >
                  Return to Dashboard
                </button>
              </div>
            </div>
          ) : (
            <p className="text-quip-teal">Returning to dashboard...</p>
          )}
        </div>
      </div>
    );
  }

  if (!roundData) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <LoadingSpinner isLoading={true} message={loadingMessages.starting} />
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
            <strong>💡 Tip:</strong> You don't know the prompt! Submit a phrase that could be <em>similar or related</em> to the phrase shown below. Do NOT submit your best guess of the prompt.
          </p>
        </div>

        {/* Original Phrase */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6 mb-6 relative">
          <button
            type="button"
            onClick={handleOpenFlagConfirm}
            disabled={isSubmitting || isFlagging}
            className="absolute top-3 right-3 z-10 inline-flex h-10 w-10 items-center justify-center rounded-full bg-white/90 text-quip-orange shadow-tile-sm transition hover:scale-105 hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-orange disabled:cursor-not-allowed disabled:opacity-50"
            title="Flag this phrase"
            aria-label="Flag this phrase"
          >
            <span className="sr-only">Flag this phrase</span>
            <img src="/icon_flag.svg" alt="" className="h-5 w-5 pointer-events-none" aria-hidden="true" />
          </button>
          <p className="text-sm text-quip-teal mb-2 text-center font-medium">Original Phrase:</p>
          <p className="text-3xl text-center font-display font-bold text-quip-turquoise">
            {roundData.original_phrase}
          </p>
        </div>

        {/* Error Message */}
        {(error || flagError) && (
          <div className="mb-4 space-y-1 rounded border border-red-400 bg-red-100 p-4 text-red-700">
            {error && <p>{error}</p>}
            {flagError && <p>{flagError}</p>}
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
              disabled={isExpired || isSubmitting || isFlagging}
              maxLength={100}
            />
            <p className="text-sm text-quip-teal mt-1">
              2-5 words (4-100 characters), A-Z and spaces only, must be different from the original
            </p>
          </div>

          <button
            type="submit"
            disabled={isExpired || isSubmitting || isFlagging || !isPhraseValid}
            className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            {isExpired ? "Time's Up" : isSubmitting ? loadingMessages.submitting : 'Submit Phrase'}
          </button>
        </form>

        {showFlagConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-quip-navy/60 p-4">
            <div className="w-full max-w-md rounded-tile bg-white p-6 shadow-tile-lg">
              <h3 className="text-xl font-display font-bold text-quip-navy mb-2">Flag this phrase?</h3>
              <p className="text-quip-teal">
                Are you sure you want to mark this phrase as “offensive, inappropriate, or nonsensical”? This will abandon the round
                and we'll review the phrase.
              </p>
              <div className="mt-6 flex justify-end gap-3">
                <button
                  type="button"
                  onClick={handleCancelFlag}
                  className="rounded-tile border-2 border-quip-navy px-4 py-2 font-semibold text-quip-navy transition hover:bg-quip-navy hover:text-white"
                  disabled={isFlagging}
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleConfirmFlag}
                  disabled={isFlagging}
                  className="rounded-tile bg-quip-orange px-4 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-quip-orange/90 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isFlagging ? 'Flagging...' : 'Yes, flag it'}
                </button>
              </div>
            </div>
          </div>
        )}

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
        <div className="mt-6 p-4 bg-quip-turquoise bg-opacity-5 rounded-tile">
          <p className="text-sm text-quip-teal">
            <strong className="text-quip-navy">Cost:</strong> <CurrencyDisplay amount={roundData.cost} iconClassName="w-3 h-3" textClassName="text-sm" />
            {roundData.discount_active && (
              <span className="text-quip-turquoise font-semibold"> (10% discount!)</span>
            )}
          </p>
          <p className="text-sm text-quip-teal mt-1">
            If you don't submit, <CurrencyDisplay amount={roundData.cost - abandonedPenalty} iconClassName="w-3 h-3" textClassName="text-sm" /> will be refunded (<CurrencyDisplay amount={abandonedPenalty} iconClassName="w-3 h-3" textClassName="text-sm" /> penalty)
          </p>
        </div>
      </div>
    </div>
  );
};

export default CopyRound;
