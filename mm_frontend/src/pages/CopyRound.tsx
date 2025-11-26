import React, { useState, useEffect, useCallback, useRef, useReducer } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { useTimer } from '../hooks/useTimer';
import { usePhraseValidation } from '../hooks/usePhraseValidation';
import { getRandomMessage, loadingMessages } from '../utils/brandedMessages';
import type { CopyState, FlagCopyRoundResponse, SubmitPhraseResponse } from '../api/types';
import { copyRoundLogger } from '../utils/logger';
import { CopyRoundIcon } from '../components/icons/RoundIcons';
import { FlagIcon } from '../components/icons/EngagementIcons';
import { usePartyRoundCoordinator } from '../hooks/usePartyRoundCoordinator';
import { usePartyNavigation } from '../hooks/usePartyNavigation';

const AUTO_HINT_ROUND_LIMIT = 10;
const hintProgressKey = (playerId: string) => `impostorHintProgress:${playerId}`;

type HintProgress = {
  roundIds: string[];
};

const loadHintProgress = (playerId: string): HintProgress => {
  try {
    const stored = localStorage.getItem(hintProgressKey(playerId));
    if (stored) {
      return JSON.parse(stored) as HintProgress;
    }
  } catch (err) {
    copyRoundLogger.warn('Failed to load impostor hint progress from storage', err);
  }

  return { roundIds: [] };
};

const saveHintProgress = (playerId: string, progress: HintProgress) => {
  try {
    localStorage.setItem(hintProgressKey(playerId), JSON.stringify(progress));
  } catch (err) {
    copyRoundLogger.warn('Failed to save impostor hint progress to storage', err);
  }
};

type SecondCopyEligibility = {
  eligible: boolean;
  cost: number;
  promptRoundId: string;
  originalPhrase: string;
};

type CompletionState = {
  successMessage: string | null;
  feedbackMessage: string | null;
  awaitingSecondCopyDecision: boolean;
  showSecondCopyDetails: boolean;
  secondCopyEligibility: SecondCopyEligibility | null;
  isStartingSecondCopy: boolean;
  isPromptRevealLoading: boolean;
  promptRevealError: string | null;
  originalPromptText: string | null;
  hasRequestedPromptReveal: boolean;
};

const initialCompletionState: CompletionState = {
  successMessage: null,
  feedbackMessage: null,
  awaitingSecondCopyDecision: false,
  showSecondCopyDetails: false,
  secondCopyEligibility: null,
  isStartingSecondCopy: false,
  isPromptRevealLoading: false,
  promptRevealError: null,
  originalPromptText: null,
  hasRequestedPromptReveal: false,
};

type CompletionAction =
  | { type: 'RESET' }
  | { type: 'SET_SUCCESS'; payload: { successMessage: string; feedbackMessage: string | null } }
  | { type: 'SET_SECOND_COPY_ELIGIBILITY'; payload: SecondCopyEligibility }
  | { type: 'CLEAR_SECOND_COPY_ELIGIBILITY' }
  | { type: 'TOGGLE_SECOND_COPY_DETAILS' }
  | { type: 'START_SECOND_COPY_REQUEST' }
  | { type: 'START_SECOND_COPY_COMPLETE' }
  | { type: 'PROMPT_REVEAL_REQUESTED' }
  | { type: 'PROMPT_REVEAL_SUCCESS'; payload: string }
  | { type: 'PROMPT_REVEAL_ERROR'; payload: string }
  | { type: 'PROMPT_REVEAL_RESET' };

const completionReducer = (state: CompletionState, action: CompletionAction): CompletionState => {
  switch (action.type) {
    case 'RESET':
      return { ...initialCompletionState };
    case 'SET_SUCCESS':
      return {
        ...state,
        successMessage: action.payload.successMessage,
        feedbackMessage: action.payload.feedbackMessage,
      };
    case 'SET_SECOND_COPY_ELIGIBILITY':
      return {
        ...state,
        secondCopyEligibility: action.payload,
        awaitingSecondCopyDecision: true,
        showSecondCopyDetails: false,
      };
    case 'CLEAR_SECOND_COPY_ELIGIBILITY':
      return {
        ...state,
        secondCopyEligibility: null,
        awaitingSecondCopyDecision: false,
        showSecondCopyDetails: false,
      };
    case 'TOGGLE_SECOND_COPY_DETAILS':
      return { ...state, showSecondCopyDetails: !state.showSecondCopyDetails };
    case 'START_SECOND_COPY_REQUEST':
      return { ...state, isStartingSecondCopy: true };
    case 'START_SECOND_COPY_COMPLETE':
      return { ...state, isStartingSecondCopy: false };
    case 'PROMPT_REVEAL_REQUESTED':
      return {
        ...state,
        hasRequestedPromptReveal: true,
        isPromptRevealLoading: true,
        promptRevealError: null,
        originalPromptText: null,
      };
    case 'PROMPT_REVEAL_SUCCESS':
      return {
        ...state,
        originalPromptText: action.payload,
        promptRevealError: null,
        isPromptRevealLoading: false,
      };
    case 'PROMPT_REVEAL_ERROR':
      return {
        ...state,
        promptRevealError: action.payload,
        originalPromptText: null,
        isPromptRevealLoading: false,
      };
    case 'PROMPT_REVEAL_RESET':
      return {
        ...state,
        hasRequestedPromptReveal: false,
        isPromptRevealLoading: false,
        promptRevealError: null,
        originalPromptText: null,
      };
    default:
      return state;
  }
};

export const CopyRound: React.FC = () => {
  const { state, actions } = useGame();
  const { activeRound, roundAvailability, copyRoundHints, player } = state;
  const { flagCopyRound, refreshDashboard, fetchCopyHints } = actions;
  const partyState = { isPartyMode: false, sessionId: null as string | null };
  const partyActions = {
    setCurrentStep: (_step: unknown) => {},
    updateFromPartyContext: (_context: unknown) => {},
  };
  const { setCurrentStep } = partyActions;
  const navigate = useNavigate();
  const [phrase, setPhrase] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [completionState, dispatchCompletion] = useReducer(completionReducer, initialCompletionState);
  const [showFlagConfirm, setShowFlagConfirm] = useState(false);
  const [isFlagging, setIsFlagging] = useState(false);
  const [flagError, setFlagError] = useState<string | null>(null);
  const [flagResult, setFlagResult] = useState<FlagCopyRoundResponse | null>(null);
  const [isFetchingHints, setIsFetchingHints] = useState(false);
  const [hintError, setHintError] = useState<string | null>(null);
  const [showHints, setShowHints] = useState(false);
  const [isEarlyImpostorPlayer, setIsEarlyImpostorPlayer] = useState(false);
  const autoFetchTriggeredRef = useRef(false);
  const hintAbortControllerRef = useRef<AbortController | null>(null);
  const promptRevealRequestRef = useRef<string | null>(null);

  // Use party mode hooks for transitions and navigation
  const { transitionToNextRound, isTransitioning: isStartingNextRound, error: nextRoundError } = usePartyRoundCoordinator();
  const { navigateHome, isInPartyMode } = usePartyNavigation();

  const {
    successMessage,
    feedbackMessage,
    awaitingSecondCopyDecision,
    showSecondCopyDetails,
    secondCopyEligibility,
    isStartingSecondCopy,
    originalPromptText,
    isPromptRevealLoading,
    promptRevealError,
    hasRequestedPromptReveal,
  } = completionState;

  const { isPhraseValid, trimmedPhrase } = usePhraseValidation(phrase);

  const roundData = activeRound?.round_type === 'copy' ? activeRound.state as CopyState : null;
  const { isExpired } = useTimer(roundData?.expires_at || null);

  // Get dynamic penalty from config or use default
  const abandonedPenalty = roundAvailability?.abandoned_penalty || 5;

  useEffect(() => {
    if (partyState.isPartyMode) {
      setCurrentStep('copy');
    }
  }, [partyState.isPartyMode, setCurrentStep]);

  useEffect(() => {
    setShowHints(false);
    setHintError(null);
    setIsFetchingHints(false);
    autoFetchTriggeredRef.current = false;
  }, [roundData?.round_id]);

  useEffect(() => {
    if (copyRoundHints && copyRoundHints.length > 0) {
      setHintError(null);
      setShowHints(true);
    }
  }, [copyRoundHints, roundData?.round_id]);

  useEffect(() => {
    if (!player?.player_id || !roundData?.round_id) {
      setIsEarlyImpostorPlayer(false);
      return;
    }

    const progress = loadHintProgress(player.player_id);
    const hasSeenRound = progress.roundIds.includes(roundData.round_id);
    const updatedRoundIds = hasSeenRound ? progress.roundIds : [...progress.roundIds, roundData.round_id];

    if (!hasSeenRound) {
      saveHintProgress(player.player_id, { roundIds: updatedRoundIds });
    }

    setIsEarlyImpostorPlayer(updatedRoundIds.length <= AUTO_HINT_ROUND_LIMIT);
  }, [player?.player_id, roundData?.round_id]);

  const fetchOriginalPrompt = useCallback(async (promptRoundId?: string | null) => {
    if (!promptRoundId) {
      dispatchCompletion({ type: 'PROMPT_REVEAL_RESET' });
      promptRevealRequestRef.current = null;
      return;
    }

    copyRoundLogger.debug('Fetching prompt reveal information', { promptRoundId });
    dispatchCompletion({ type: 'PROMPT_REVEAL_REQUESTED' });
    promptRevealRequestRef.current = promptRoundId;

    try {
      const details = await apiClient.getRoundDetails(promptRoundId);
      if (promptRevealRequestRef.current === promptRoundId) {
        if (details.prompt_text) {
          dispatchCompletion({ type: 'PROMPT_REVEAL_SUCCESS', payload: details.prompt_text });
        } else {
          dispatchCompletion({
            type: 'PROMPT_REVEAL_ERROR',
            payload: 'The original prompt is not available yet. Check back soon!',
          });
        }
      }
    } catch (err) {
      if (promptRevealRequestRef.current === promptRoundId) {
        dispatchCompletion({ type: 'PROMPT_REVEAL_ERROR', payload: 'Unable to reveal the original prompt right now.' });
      }
      copyRoundLogger.error('Failed to fetch original prompt for reveal', err);
    }
  }, [dispatchCompletion]);

  const partyOverlay = null;

  const cancelHintRequest = useCallback(() => {
    if (hintAbortControllerRef.current) {
      hintAbortControllerRef.current.abort();
      hintAbortControllerRef.current = null;
    }
  }, []);

  const handleFetchHints = useCallback(async () => {
    if (!roundData || isFetchingHints || isExpired) {
      return;
    }

    setIsFetchingHints(true);
    setHintError(null);

    const controller = new AbortController();
    hintAbortControllerRef.current = controller;

    try {
      await fetchCopyHints(roundData.round_id, controller.signal);
      setShowHints(true);
    } catch (err) {
      if (controller.signal.aborted) {
        copyRoundLogger.debug('Hint request cancelled before completion');
        return;
      }
      setHintError(extractErrorMessage(err) || 'Unable to fetch AI hints. Please try again soon.');
    } finally {
      if (hintAbortControllerRef.current === controller) {
        hintAbortControllerRef.current = null;
      }
      setIsFetchingHints(false);
    }
  }, [fetchCopyHints, isExpired, isFetchingHints, roundData]);

  useEffect(() => {
    if (!isEarlyImpostorPlayer || !roundData || autoFetchTriggeredRef.current) {
      return;
    }

    if (copyRoundHints && copyRoundHints.length > 0) {
      setShowHints(true);
      autoFetchTriggeredRef.current = true;
      return;
    }

    autoFetchTriggeredRef.current = true;
    setShowHints(true);
    void handleFetchHints();
  }, [copyRoundHints, handleFetchHints, isEarlyImpostorPlayer, roundData]);

  useEffect(() => {
    if (!roundData) {
      copyRoundLogger.debug('Impostor round page mounted without active round');
    } else {
      copyRoundLogger.debug('Impostor round page mounted', {
        roundId: roundData.round_id,
        expiresAt: roundData.expires_at,
        status: roundData.status,
      });
    }
  }, [roundData]);

  useEffect(() => {
    return () => {
      promptRevealRequestRef.current = null;
      cancelHintRequest();
    };
  }, [cancelHintRequest]);

  // Redirect if already submitted
  useEffect(() => {
    if (roundData?.status === 'submitted') {
      if (partyState.isPartyMode) {
        navigate('/vote');
      } else {
        navigate('/dashboard');
      }
    }
  }, [partyState.isPartyMode, roundData?.status, navigate]);

  // Redirect if no active impostor round - but NOT during the submission process
  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'copy') {
      // Don't navigate if we're showing success message (submission in progress)
      if (successMessage) {
        return;
      }

      // Add a small delay to prevent race conditions during navigation
      const timeoutId = setTimeout(() => {
        // Redirect to dashboard instead of starting new rounds
        const fallbackPath = partyState.isPartyMode && partyState.sessionId
          ? `/party/game/${partyState.sessionId}`
          : '/dashboard';
        navigate(fallbackPath);
      }, 100);

      return () => clearTimeout(timeoutId);
    }
  }, [activeRound, navigate, partyState.isPartyMode, partyState.sessionId, successMessage]);

  // In party mode, DON'T automatically transition - wait for session phase change
  // useEffect(() => {
  //   if (isInPartyMode && successMessage && !awaitingSecondCopyDecision && !secondCopyEligibility) {
  //     transitionToNextRound('copy').catch(err => {
  //       copyRoundLogger.error('Failed to transition to vote round:', err);
  //     });
  //   }
  // }, [awaitingSecondCopyDecision, isInPartyMode, secondCopyEligibility, successMessage, transitionToNextRound]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!roundData || isSubmitting || !isPhraseValid) return;

    cancelHintRequest();
    setIsSubmitting(true);
    setError(null);
    setFlagResult(null);

    try {
      copyRoundLogger.debug('Submitting impostor round phrase', {
        roundId: roundData.round_id,
      });
      const response: SubmitPhraseResponse = await apiClient.submitPhrase(roundData.round_id, trimmedPhrase);

      // Update party context if present
      if (response.party_context && partyState.isPartyMode) {
        partyActions.updateFromPartyContext(response.party_context);
        copyRoundLogger.debug('Updated party context after submission', {
          yourProgress: response.party_context.your_progress,
        });
      }

      // Show success messages first to prevent navigation race condition
      const heading = getRandomMessage('copySubmitted');
      const feedback = getRandomMessage('copySubmittedFeedback');
      dispatchCompletion({ type: 'SET_SUCCESS', payload: { successMessage: heading, feedbackMessage: feedback } });
      copyRoundLogger.info('Impostor round phrase submitted successfully', {
        roundId: roundData.round_id,
        message: heading,
      });

      const promptRoundIdForReveal = roundData.prompt_round_id || response.prompt_round_id || null;
      void fetchOriginalPrompt(promptRoundIdForReveal);
      dispatchCompletion({ type: 'CLEAR_SECOND_COPY_ELIGIBILITY' });

      // Check if eligible for second copy
      if (response.eligible_for_second_copy && response.second_copy_cost && response.prompt_round_id && response.original_phrase) {
        dispatchCompletion({
          type: 'SET_SECOND_COPY_ELIGIBILITY',
          payload: {
            eligible: true,
            cost: response.second_copy_cost,
            promptRoundId: response.prompt_round_id,
            originalPhrase: response.original_phrase,
          },
        });
        copyRoundLogger.info('Player eligible for second copy', {
          cost: response.second_copy_cost,
          promptRoundId: response.prompt_round_id,
        });
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
          if (!partyState.isPartyMode) {
            copyRoundLogger.debug('Navigating back to dashboard after fake submission');
            navigate('/dashboard');
          }
        }, 3000);
      }
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to submit your phrase. The round may have expired or there may be a connection issue.';
      copyRoundLogger.error('Failed to submit impostor round phrase', err);
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
      copyRoundLogger.debug('Flagging impostor round phrase', {
        roundId: roundData.round_id,
      });
      const response = await flagCopyRound(roundData.round_id);
      setFlagResult(response);
      dispatchCompletion({ type: 'SET_SUCCESS', payload: { successMessage: 'Thanks for looking out!', feedbackMessage: null } });
      dispatchCompletion({ type: 'CLEAR_SECOND_COPY_ELIGIBILITY' });
      setShowFlagConfirm(false);
      copyRoundLogger.info('Impostor round flagged', {
        roundId: roundData.round_id,
        flagId: response.flag_id,
      });

      setTimeout(() => {
        if (isInPartyMode) {
          // In party mode, don't auto-transition after flagging - wait for session phase change
          copyRoundLogger.debug('Flagged prompt in party mode - waiting for session phase transition');
          // transitionToNextRound('copy').catch(err => {
          //   copyRoundLogger.error('Failed to transition to vote round after flagging:', err);
          // });
        } else {
          copyRoundLogger.debug('Navigating back to dashboard after flagging impostor round');
          navigate('/dashboard');
        }
      }, 1500);
    } catch (err) {
      const message = extractErrorMessage(err, 'flag-copy-round') ||
        'Unable to flag this phrase right now. Please try again.';
      copyRoundLogger.error('Failed to flag impostor round', err);
      setFlagError(message);
      setShowFlagConfirm(false);
    } finally {
      setIsFlagging(false);
    }
  };

  const handleStartSecondCopy = async () => {
    if (!secondCopyEligibility) return;

    dispatchCompletion({ type: 'START_SECOND_COPY_REQUEST' });
    setError(null);

    try {
      copyRoundLogger.info('Starting second impostor round', {
        promptRoundId: secondCopyEligibility.promptRoundId,
        cost: secondCopyEligibility.cost,
      });

      await apiClient.startCopyRound(secondCopyEligibility.promptRoundId);
      await refreshDashboard();

      copyRoundLogger.debug('Second impostor round started, staying on page');
      // Reset states to allow for the new round
      dispatchCompletion({ type: 'RESET' });
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to start second impostor round. Please try again.';
      copyRoundLogger.error('Failed to start second impostor round', err);
      setError(message);
    } finally {
      dispatchCompletion({ type: 'START_SECOND_COPY_COMPLETE' });
    }
  };

  const handleDeclineSecondCopy = () => {
    copyRoundLogger.info('Player declined second copy option');
    dispatchCompletion({ type: 'CLEAR_SECOND_COPY_ELIGIBILITY' });
    setTimeout(() => {
      if (isInPartyMode) {
        // In party mode, don't auto-transition - wait for session phase change
        copyRoundLogger.debug('Declined second copy in party mode - waiting for session phase transition');
        // transitionToNextRound('copy').catch(err => {
        //   copyRoundLogger.error('Failed to transition to vote round after declining second copy:', err);
        // });
      } else {
        copyRoundLogger.debug('Navigating back to dashboard after declining second copy');
        navigate('/dashboard');
      }
    }, 3000);
  };

  const handleHintClick = (hintText: string) => {
    setPhrase(hintText);
    setError(null); // Clear any validation errors when using a hint
  };

  const secondCopyModal = awaitingSecondCopyDecision && secondCopyEligibility ? (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-quip-navy/60 p-4">
      <div className="w-full max-w-lg rounded-tile bg-quip-warm-ivory p-6 shadow-tile-lg text-center space-y-4">
        <div className="flex justify-center">
          <CopyRoundIcon className="w-14 h-14 text-quip-turquoise" aria-hidden="true" />
        </div>
        <h3 className="text-2xl font-display font-bold text-quip-navy">
          {successMessage || 'Copy submitted!'}
        </h3>
        {feedbackMessage && <p className="text-quip-teal">{feedbackMessage}</p>}

        <button
          type="button"
          onClick={() => dispatchCompletion({ type: 'TOGGLE_SECOND_COPY_DETAILS' })}
          className="mx-auto flex items-center justify-center gap-2 text-blue-600 font-semibold underline hover:text-blue-500 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-400 rounded-tile"
        >
          Want to submit another fake for the same quip?
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={`h-4 w-4 transition-transform ${showSecondCopyDetails ? 'rotate-180' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showSecondCopyDetails && (
          <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-4 text-left space-y-2">
            <p className="text-quip-teal">
              You can submit a second fake for <strong>"{secondCopyEligibility.originalPhrase}"</strong> for{' '}
              <CurrencyDisplay
                amount={secondCopyEligibility.cost}
                iconClassName="w-4 h-4"
                textClassName="font-semibold text-quip-turquoise"
              />
              . This gives you two chances to fool voters.
            </p>
          </div>
        )}

        {error && (
          <div className="text-sm text-red-600" role="alert">
            {error}
          </div>
        )}

        <div className="flex flex-col sm:flex-row gap-3">
          <button
            onClick={handleStartSecondCopy}
            disabled={isStartingSecondCopy}
            className="flex-1 bg-quip-teal hover:bg-quip-navy disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
          >
            {isStartingSecondCopy ? (
              'Starting...'
            ) : (
              <span className="inline-flex items-center gap-1">
                Yes (
                <span className="inline-flex items-center gap-1">
                  <CurrencyDisplay
                    amount={secondCopyEligibility.cost}
                    showIcon={true}
                    textClassName="font-semibold"
                  />
                </span>
                )
              </span>
            )}
          </button>
          <button
            onClick={handleDeclineSecondCopy}
            disabled={isStartingSecondCopy}
            className="flex-1 bg-quip-teal-light hover:bg-quip-turquoise border-2 border-quip-navy text-quip-navy font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm disabled:opacity-50"
          >
            No
          </button>
        </div>
      </div>
    </div>
  ) : null;

  // Show success state
  if (successMessage && !awaitingSecondCopyDecision) {
    return (
      <>
        {partyOverlay}
        <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
          <div className="tile-card max-w-2xl w-full p-8 text-center flip-enter">
            <div className="flex justify-center mb-4">
              <CopyRoundIcon className="w-24 h-24" aria-hidden="true" />
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
                <p>{isInPartyMode ? 'Starting the vote round...' : 'Returning to dashboard...'}</p>
              </div>
            ) : (
              <>
                {feedbackMessage && (
                  <p className="text-lg text-quip-teal mb-4">{feedbackMessage}</p>
                )}
                <p className="text-sm text-quip-teal">
                  {isInPartyMode ? 'Starting the vote round...' : 'Returning to dashboard...'}
                </p>

                {hasRequestedPromptReveal && (
                  <div className="mt-6 text-left bg-quip-warm-ivory border-2 border-quip-turquoise rounded-tile p-5">
                    <p className="text-xs uppercase tracking-widest text-quip-teal mb-2">
                      Original prompt reveal
                    </p>
                    {isPromptRevealLoading ? (
                      <p className="text-quip-teal">Revealing the original prompt...</p>
                    ) : promptRevealError ? (
                      <p className="text-quip-orange">{promptRevealError}</p>
                    ) : originalPromptText ? (
                      <p className="text-2xl font-display font-semibold text-quip-navy">{originalPromptText}</p>
                    ) : (
                      <p className="text-quip-teal">We'll reveal the prompt shortly.</p>
                    )}
                  </div>
                )}
                {isInPartyMode && isStartingNextRound && (
                  <p className="text-xs text-quip-teal mt-2">Loading the vote round now...</p>
                )}
                {nextRoundError && (
                  <div className="mt-2 text-sm text-red-600">
                    {nextRoundError}
                    <button
                      type="button"
                      onClick={() => transitionToNextRound('copy')}
                      className="ml-2 underline text-quip-orange hover:text-quip-orange-deep"
                    >
                      Retry
                    </button>
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </>
    );
  }

  if (!roundData) {
    if (secondCopyModal) {
      return (
        <div className="min-h-screen bg-quip-cream bg-pattern">
          {partyOverlay}
          {secondCopyModal}
        </div>
      );
    }

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
      <div className="min-h-screen bg-gradient-to-br from-quip-turquoise to-quip-teal flex items-center justify-center p-4 bg-pattern">
        <div className="max-w-2xl w-full tile-card p-8 slide-up-enter">
          <div className="text-center mb-8">
            <div className="flex items-center justify-center gap-2 mb-2">
              <CopyRoundIcon className="w-8 h-8" aria-hidden="true" />
              <h1 className="text-3xl font-display font-bold text-quip-navy">Impostor Round</h1>
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
              <strong>💡 Your goal:</strong> You don't know the prompt!
              <br />
              Write a phrase that <em>could have been the original</em> and might trick voters.
              <br />
              <strong>Do:</strong> stay close in meaning.
              <br />
              <strong>Don't:</strong> repeat the original or try to guess the exact prompt.
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
              <FlagIcon className="h-5 w-5 pointer-events-none" aria-hidden="true" />
            </button>
            <p className="text-sm text-quip-teal mb-2 text-center font-medium">The original answer was:</p>
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

          {/* AI Hints */}
          {roundData && (
            <div className="mb-4 rounded-tile border border-quip-turquoise/30 bg-white/80 p-4 shadow-tile-xs">
              {copyRoundHints && copyRoundHints.length > 0 ? (
                <>
                  <button
                    type="button"
                    onClick={() => setShowHints((prev) => !prev)}
                    className="flex w-full items-center justify-between rounded-tile border border-quip-turquoise/40 bg-quip-turquoise/10 px-3 py-2 font-semibold text-quip-teal transition hover:bg-quip-turquoise/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-turquoise"
                  >
                    <span>{showHints ? 'Hide AI Hints' : 'Show AI Hints'}</span>
                    <span className="text-sm text-quip-navy">{copyRoundHints.length} suggestions</span>
                  </button>
                  {showHints && (
                    <div className="mt-3 space-y-3">
                      <p className="text-xs uppercase tracking-wide text-quip-teal/80">
                        Mix and modify - make it your own!
                      </p>
                      <ul className="space-y-2">
                        {copyRoundHints.map((hint, index) => (
                          <li key={`${hint}-${index}`} className="w-full">
                            <button
                              type="button"
                              onClick={() => handleHintClick(hint)}
                              disabled={isSubmitting || isFlagging || isExpired}
                              className="w-full text-left flex items-start gap-2 rounded-tile border border-quip-turquoise/30 bg-white px-3 py-2 text-quip-navy shadow-inner transition hover:bg-quip-turquoise/10 hover:border-quip-turquoise/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-turquoise disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              <span className="font-semibold text-quip-turquoise shrink-0">Hint {index + 1}:</span>
                              <span className="break-words">{hint}</span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </>
              ) : (
                <>
                  <button
                    type="button"
                    onClick={handleFetchHints}
                    disabled={isFetchingHints || isSubmitting || isFlagging || isExpired}
                    className="w-full rounded-tile border border-quip-turquoise bg-white px-4 py-2 font-semibold text-quip-turquoise transition hover:bg-quip-turquoise hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {isFetchingHints ? 'Contacting AI...' : 'Get AI Hints'}
                  </button>
                  {hintError && <p className="mt-2 text-sm text-red-600">{hintError}</p>}
                  <p className="mt-2 text-xs text-quip-teal">
                    You will get three ideas that passed quick AI checks. Use them as inspiration and tweak them to match your style. Hints may take up to one minute to generate.
                  </p>
                </>
              )}
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
                2-5 words (4-100 characters), A-Z and spaces only, no proper nouns
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

        {secondCopyModal}
      </div>
    </>
  );
};

export default CopyRound;
