import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { Header } from '../components/Header';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';
import { dashboardLogger } from '../utils/logger';
import type { PendingResult } from '../api/types';
import type { BetaSurveyStatusResponse } from '../api/types';
import { hasDismissedSurvey, markSurveyDismissed, hasCompletedSurvey } from '../utils/betaSurvey';

const formatWaitingCount = (count: number): string => (count > 10 ? 'over 10' : count.toString());

export const Dashboard: React.FC = () => {
  const { state, actions } = useGame();
  const { state: resultsState, actions: resultsActions } = useResults();
  const {
    player,
    activeRound,
    pendingResults,
    phrasesetSummary,
    roundAvailability,
    error: contextError,
  } = state;
  const { refreshDashboard, clearError, abandonRound } = actions;
  const { startTutorial, skipTutorial, advanceStep } = useTutorial();
  const { viewedResultIds } = resultsState;
  const { markResultsViewed } = resultsActions;
  const navigate = useNavigate();
  const [isRoundExpired, setIsRoundExpired] = useState(false);
  const [startingRound, setStartingRound] = useState<string | null>(null);
  const [roundStartError, setRoundStartError] = useState<string | null>(null);
  const [surveyStatus, setSurveyStatus] = useState<BetaSurveyStatusResponse | null>(null);
  const [showSurveyPrompt, setShowSurveyPrompt] = useState(false);
  const [isAbandoningRound, setIsAbandoningRound] = useState(false);
  const [abandonError, setAbandonError] = useState<string | null>(null);

  // Log component mount and key state changes
  useEffect(() => {
    dashboardLogger.debug('Component mounted');
    dashboardLogger.debug('Initial state:', {
      player: player ? `${player.username}` : 'null',
      activeRound: activeRound ? `${activeRound.round_type} (${activeRound.round_id})` : 'null',
      roundAvailability: roundAvailability || 'null'
    });
  }, []);

  useEffect(() => {
    dashboardLogger.debug('Round availability changed:', roundAvailability);
  }, [roundAvailability]);

  useEffect(() => {
    if (activeRound) {
      dashboardLogger.debug('Active round changed:', {
        id: activeRound.round_id,
        type: activeRound.round_type,
        expiresAt: activeRound.expires_at
      });
    } else {
      dashboardLogger.debug('Active round cleared');
    }
  }, [activeRound]);

  useEffect(() => {
    const playerId = player?.player_id;
    dashboardLogger.debug('[Beta Survey] useEffect triggered', { playerId: playerId || 'undefined' });

    if (!playerId) {
      dashboardLogger.debug('[Beta Survey] No player ID, skipping survey check');
      setSurveyStatus(null);
      setShowSurveyPrompt(false);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();

    const fetchStatus = async () => {
      try {
        dashboardLogger.debug('[Beta Survey] Fetching survey status from API...');
        const status = await apiClient.getBetaSurveyStatus(controller.signal);
        dashboardLogger.debug('[Beta Survey] API response received', status);

        if (cancelled) {
          dashboardLogger.debug('[Beta Survey] Request was cancelled');
          return;
        }

        const dismissed = hasDismissedSurvey(playerId);
        const completedLocal = hasCompletedSurvey(playerId);
        const shouldShow = status.eligible && !status.has_submitted && !dismissed && !completedLocal;

        dashboardLogger.debug('[Beta Survey] Status resolved', {
          eligible: status.eligible,
          hasSubmitted: status.has_submitted,
          totalRounds: status.total_rounds,
          dismissed,
          completedLocal,
          shouldShow,
        });

        setSurveyStatus(status);
        setShowSurveyPrompt(shouldShow);

        if (shouldShow) {
          dashboardLogger.info('[Beta Survey] ✨ SHOWING SURVEY PROMPT ✨');
        } else {
          dashboardLogger.debug('[Beta Survey] Not showing survey prompt');
        }
      } catch (error) {
        if (cancelled) {
          dashboardLogger.debug('[Beta Survey] Request was cancelled (in catch)');
          return;
        }
        dashboardLogger.warn('[Beta Survey] Failed to fetch survey status', error);
      }
    };

    fetchStatus();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [player?.player_id]);


  const handleStartTutorial = async () => {
    dashboardLogger.debug('Starting tutorial from dashboard');
    await startTutorial();
    await advanceStep('dashboard');
  };

  const handleSkipTutorial = async () => {
    await skipTutorial();
  };

  const handleSurveyStart = useCallback(() => {
    setShowSurveyPrompt(false);
    navigate('/survey/beta');
  }, [navigate]);

  const handleSurveyDismiss = useCallback(() => {
    if (player?.player_id) {
      markSurveyDismissed(player.player_id);
    }
    setShowSurveyPrompt(false);
  }, [player?.player_id]);

  const activeRoundRoute = useMemo(() => {
    return activeRound?.round_type ? `/${activeRound.round_type}` : null;
  }, [activeRound]);

  const activeRoundLabel = useMemo(() => {
    if (!activeRound?.round_type) return '';
    return `${activeRound.round_type.charAt(0).toUpperCase()}${activeRound.round_type.slice(1)}`;
  }, [activeRound]);

  const canAbandonRound = useMemo(() => {
    return activeRound?.round_type === 'prompt' || activeRound?.round_type === 'copy';
  }, [activeRound]);

  // Refresh when page becomes visible (with debouncing)
  const lastVisibilityRefreshRef = useRef<number>(0);
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        const now = Date.now();
        // Debounce: only refresh if more than 5 seconds since last refresh
        if (now - lastVisibilityRefreshRef.current > 5000) {
          lastVisibilityRefreshRef.current = now;
          refreshDashboard();
        }
      }
    };

    document.addEventListener('visibilitychange', handleVisibilityChange);

    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  }, [refreshDashboard]);

  useEffect(() => {
    if (!activeRound?.round_id) {
      setIsRoundExpired(false);
      setAbandonError(null);
      setIsAbandoningRound(false);
      return;
    }

    if (!activeRound.expires_at) {
      setIsRoundExpired(false);
      setAbandonError(null);
      return;
    }

    const expiresAt = new Date(activeRound.expires_at).getTime();
    const now = Date.now();
    const isExpired = expiresAt <= now;

    dashboardLogger.debug('Round expiration check:', {
      roundId: activeRound.round_id,
      expiresAt: activeRound.expires_at,
      expiresAtMs: expiresAt,
      nowMs: now,
      isExpired,
      timeDiff: expiresAt - now
    });

    setIsRoundExpired(isExpired);
    if (!isExpired) {
      setAbandonError(null);
    }
  }, [activeRound]);

  const handleContinueRound = useCallback(() => {
    if (activeRoundRoute) {
      navigate(activeRoundRoute);
    }
  }, [activeRoundRoute, navigate]);

  const handleRoundExpired = useCallback(async () => {
    dashboardLogger.debug('Round expired, setting flag and triggering refresh');
    setIsRoundExpired(true);

    try {
      // Refresh dashboard to clear expired round and get latest state
      await refreshDashboard();
      dashboardLogger.debug('Dashboard refreshed successfully after round expiration');
    } catch (err) {
      dashboardLogger.error('Failed to refresh dashboard after expiration:', err);
      // Even if refresh fails, ensure the expired state is set
      setIsRoundExpired(true);
    }
  }, [refreshDashboard]);

  const handleAbandonRound = useCallback(async () => {
    if (!activeRound?.round_id || !canAbandonRound || isAbandoningRound) {
      return;
    }

    dashboardLogger.debug('Abandon round requested from dashboard', {
      roundId: activeRound.round_id,
      roundType: activeRound.round_type,
    });

    try {
      setIsAbandoningRound(true);
      setAbandonError(null);
      const response = await abandonRound(activeRound.round_id);
      dashboardLogger.info('Round abandoned via dashboard', {
        roundId: response.round_id,
        refundAmount: response.refund_amount,
        penaltyKept: response.penalty_kept,
      });
    } catch (err) {
      dashboardLogger.error('Failed to abandon round from dashboard', err);
      const errorMsg = extractErrorMessage(err, 'abandon-round') ||
        'Unable to abandon the round. Please try again.';
      setAbandonError(errorMsg);
    } finally {
      setIsAbandoningRound(false);
    }
  }, [abandonRound, activeRound, canAbandonRound, isAbandoningRound]);

  const handleStartPrompt = async () => {
    if (startingRound) {
      dashboardLogger.debug('Ignoring prompt button click - already starting round:', startingRound);
      return;
    }

    dashboardLogger.info('Starting prompt round...');
    dashboardLogger.debug('Player state before start:', {
      balance: player?.balance,
      outstandingPrompts: player?.outstanding_prompts,
      canPrompt: roundAvailability?.can_prompt
    });

    setStartingRound('prompt');
    setRoundStartError(null);
    try {
      dashboardLogger.debug('Calling actions.startPromptRound()...');
      await actions.startPromptRound();
      dashboardLogger.info('✅ Prompt round started successfully, navigating to /prompt');
      navigate('/prompt');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start prompt round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start prompt round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Prompt round start process completed');
    }
  };

  const handleStartCopy = async () => {
    if (startingRound) {
      dashboardLogger.debug('Ignoring copy button click - already starting round:', startingRound);
      return;
    }

    dashboardLogger.info('Starting copy round...');
    dashboardLogger.debug('Player state before start:', {
      balance: player?.balance,
      canCopy: roundAvailability?.can_copy,
      promptsWaiting: roundAvailability?.prompts_waiting,
      copyCost: roundAvailability?.copy_cost
    });

    setStartingRound('copy');
    setRoundStartError(null);
    try {
      dashboardLogger.debug('Calling actions.startCopyRound()...');
      await actions.startCopyRound();
      dashboardLogger.info('✅ Copy round started successfully, navigating to /copy');
      navigate('/copy');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start copy round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start copy round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Copy round start process completed');
    }
  };

  const handleStartVote = async () => {
    if (startingRound) {
      dashboardLogger.debug('Ignoring vote button click - already starting round:', startingRound);
      return;
    }

    dashboardLogger.info('Starting vote round...');
    dashboardLogger.debug('Player state before start:', {
      balance: player?.balance,
      canVote: roundAvailability?.can_vote,
      phrasesetsWaiting: roundAvailability?.phrasesets_waiting
    });

    setStartingRound('vote');
    setRoundStartError(null);
    try {
      dashboardLogger.debug('Calling actions.startVoteRound()...');
      await actions.startVoteRound();
      dashboardLogger.info('✅ Vote round started successfully, navigating to /vote');
      navigate('/vote');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start vote round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start vote round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Vote round start process completed');
    }
  };

  const handleViewResults = () => {
    // Mark all current pending results as viewed
    const allCurrentIds = pendingResults.map(r => r.phraseset_id);
    markResultsViewed(allCurrentIds);
    navigate('/results');
  };

  // Hide certain dashboard elements during tutorial to reduce overwhelm
  const unviewedPromptCount = phrasesetSummary?.finalized.unclaimed_prompts ?? 0;
  const unviewedCopyCount = phrasesetSummary?.finalized.unclaimed_copies ?? 0;
  const totalUnviewedCount = unviewedPromptCount + unviewedCopyCount;
  const totalUnviewedAmount = phrasesetSummary?.total_unclaimed_amount ?? 0;

  // Filter pending results to only show unviewed ones
  const unviewedPendingResults = pendingResults.filter((result: PendingResult) =>
    !result.result_viewed && !viewedResultIds.has(result.phraseset_id)
  );

  // Show notification if there are unviewed pending results OR unclaimed finalized results
  const shouldShowResultsNotification = unviewedPendingResults.length > 0 || totalUnviewedCount > 0;

  if (!player) {
    return (
      <div className="min-h-screen bg-gray-100 flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <TutorialWelcome onStart={handleStartTutorial} onSkip={handleSkipTutorial} />

      <div className="max-w-4xl mx-auto px-4 py-8">
        {/* Active Round Notification */}
        {activeRound?.round_id && !isRoundExpired && (
          <div className="tile-card bg-quip-orange bg-opacity-10 border-2 border-quip-orange p-4 mb-6 slide-up-enter relative">
            {canAbandonRound && (
              <button
                type="button"
                onClick={handleAbandonRound}
                disabled={isAbandoningRound}
                className={`absolute -top-3 -right-3 flex h-8 w-8 items-center justify-center rounded-full border-2 border-red-500 text-lg font-semibold text-red-500 shadow-sm transition-colors duration-150 ${isAbandoningRound ? 'bg-red-100 cursor-not-allowed opacity-70' : 'bg-white hover:bg-red-500 hover:text-white'}`}
                title="Abandon round (refund minus penalty)"
                aria-label="Abandon round"
              >
                <span aria-hidden="true">×</span>
              </button>
            )}
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex-1">
                <p className="font-display font-semibold text-quip-orange-deep">
                  Active {activeRoundLabel || 'Current'} Round in Progress
                </p>
                <div className="mt-2 flex flex-col gap-2 text-sm text-quip-teal sm:flex-row sm:items-center">
                  <span>Time remaining:</span>
                  <Timer
                    expiresAt={activeRound.expires_at}
                    onExpired={handleRoundExpired}
                    compact
                  />
                </div>
                {abandonError && (
                  <p className="mt-3 text-sm text-red-600">{abandonError}</p>
                )}
              </div>
              <button
                onClick={handleContinueRound}
                className="w-full sm:w-auto bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-2 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                Continue Round
              </button>
            </div>
          </div>
        )}

        {/* Consolidated Results Notification */}
        {shouldShowResultsNotification && (
          <div className="tile-card bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise p-4 mb-6 slide-up-enter">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="flex-1">
                <p className="font-display font-semibold text-quip-turquoise">
                  {totalUnviewedCount > 0 ? 'Quip-tastic! New Results Ready!' : 'Results Ready!'}
                </p>
                <div className="text-sm text-quip-teal space-y-1">
                  {unviewedPendingResults.length > 0 && (
                    <p>
                      {unviewedPendingResults.length} quipset{unviewedPendingResults.length > 1 ? 's' : ''} finalized
                      {totalUnviewedCount === 0 && ' - view your results'}
                    </p>
                  )}
                  {totalUnviewedCount > 0 && (
                    <p>
                      {unviewedPromptCount} prompt{unviewedPromptCount === 1 ? '' : 's'} • {unviewedCopyCount} cop{unviewedCopyCount === 1 ? 'y' : 'ies'} • <CurrencyDisplay amount={totalUnviewedAmount} iconClassName="w-3 h-3" textClassName="text-sm" /> earned
                    </p>
                  )}
                </div>
              </div>
              <button
                onClick={handleViewResults}
                className="w-full sm:w-auto bg-quip-turquoise hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                View Results
              </button>
            </div>
          </div>
        )}

        {/* Round Selection */}
        <div className="tutorial-dashboard tile-card p-6 shuffle-enter">
          <h2 className="text-xl font-display font-bold mb-4 text-quip-navy">Start a Round</h2>

          {/* Error Messages */}
          {(roundStartError || contextError) && (
            <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile">
              <div className="flex justify-between items-start">
                <span>{roundStartError || contextError}</span>
                <button
                  onClick={() => {
                    setRoundStartError(null);
                    clearError();
                  }}
                  className="ml-2 text-red-900 hover:text-red-700"
                  aria-label="Dismiss error"
                >
                  ✕
                </button>
              </div>
            </div>
          )}

          <div className="space-y-4">

            {/* Prompt Round */}
            <div className="tutorial-prompt-round border-2 border-quip-navy rounded-tile p-4 bg-quip-navy bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <img src="/icon_prompt.svg" alt="" className="w-8 h-8" />
                  <h3 className="font-display font-semibold text-lg text-quip-navy">Prompt Round</h3>
                </div>
                <span className="text-quip-orange-deep font-bold flex items-center gap-1">
                  <CurrencyDisplay amount={roundAvailability?.prompt_cost || 100} iconClassName="w-4 h-4" textClassName="font-bold" />
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-3">
                Submit a phrase for a creative prompt
              </p>
              <button
                onClick={handleStartPrompt}
                disabled={!roundAvailability?.can_prompt || startingRound === 'prompt'}
                className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'prompt' ? 'Starting Round...' :
                 roundAvailability?.can_prompt ? 'Start Prompt Round' :
                 activeRound?.round_type === 'prompt' ? 'Active Round - Use Continue Above' :
                 activeRound?.round_id ? 'Complete Current Round First' :
                 player.balance < (roundAvailability?.prompt_cost || 100) ? 'Insufficient Balance' :
                 player.outstanding_prompts >= 10 ? 'Too Many Outstanding Prompts' :
                 'Not Available'}
              </button>
            </div>

            {/* Copy Round */}
            <div className="tutorial-copy-round border-2 border-quip-turquoise rounded-tile p-4 bg-quip-turquoise bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <img src="/icon_copy.svg" alt="" className="w-8 h-8" />
                  <h3 className="font-display font-semibold text-lg text-quip-turquoise">Copy Round</h3>
                </div>
                <span className="flex items-center gap-2 text-quip-orange-deep font-bold">
                  {roundAvailability?.copy_discount_active && roundAvailability?.prompts_waiting > 0 && (
                    <img
                      src="/badge_copy-discount.svg"
                      alt="Copy discount active"
                      className="h-7"
                    />
                  )}
                  <span className="flex items-center gap-1">
                    <CurrencyDisplay amount={roundAvailability?.copy_cost || 100} iconClassName="w-4 h-4" textClassName="font-bold" />
                  </span>
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-1">
                Submit a similar phrase without seeing the prompt
              </p>
              {roundAvailability && roundAvailability.prompts_waiting > 0 && (
                <p className="text-xs text-quip-turquoise mb-3 font-semibold">
                  {formatWaitingCount(roundAvailability.prompts_waiting)} prompt
                  {roundAvailability.prompts_waiting > 1 ? 's' : ''} waiting
                </p>
              )}
              <button
                onClick={handleStartCopy}
                disabled={!roundAvailability?.can_copy || startingRound === 'copy'}
                className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'copy' ? 'Starting Round...' :
                 roundAvailability?.can_copy ? 'Start Copy Round' :
                 roundAvailability?.prompts_waiting === 0 ? 'No Prompts Available' :
                 player.balance < (roundAvailability?.copy_cost || 100) ? 'Insufficient Balance' :
                 'Start Copy Round'}
              </button>
            </div>

            {/* Vote Round */}
            <div className="tutorial-vote-round border-2 border-quip-orange rounded-tile p-4 bg-quip-orange bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <img src="/icon_vote.svg" alt="" className="w-8 h-8" />
                  <h3 className="font-display font-semibold text-lg text-quip-orange-deep">Vote Round</h3>
                </div>
                <span className="text-quip-orange-deep font-bold flex items-center gap-1">
                  <CurrencyDisplay amount={roundAvailability?.vote_cost || 10} iconClassName="w-4 h-4" textClassName="font-bold" />
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-1">
                Identify the original phrase from three options
              </p>
              {roundAvailability && roundAvailability.phrasesets_waiting > 0 && (
                <p className="text-xs text-quip-orange-deep mb-3 font-semibold">
                  {formatWaitingCount(roundAvailability.phrasesets_waiting)} quip set
                  {roundAvailability.phrasesets_waiting > 1 ? 's' : ''} waiting
                </p>
              )}
              <button
                onClick={handleStartVote}
                disabled={!roundAvailability?.can_vote || startingRound === 'vote'}
                className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'vote' ? 'Starting Round...' :
                 roundAvailability?.can_vote ? 'Start Vote Round' :
                 roundAvailability?.phrasesets_waiting === 0 ? 'No Quip Sets Available' :
                 player.balance < (roundAvailability?.vote_cost || 10) ? 'Insufficient Balance' :
                 'Not Available'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Beta Survey Modal */}
      {showSurveyPrompt && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="tile-card w-full max-w-lg space-y-4 p-6">
            <h2 className="text-2xl font-display font-bold text-quip-navy">
              Share your beta feedback
            </h2>
            <p className="text-quip-navy">
              We&apos;d love to hear how Quipflip feels after ten rounds. Take a short survey to help us tune the beta experience.
            </p>
            {surveyStatus && (
              <p className="text-sm text-quip-teal">
                You&apos;ve completed <span className="font-semibold">{surveyStatus.total_rounds}</span> rounds so far — perfect!
              </p>
            )}
            <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
              <button
                type="button"
                onClick={handleSurveyDismiss}
                className="rounded-tile border border-quip-navy/20 px-5 py-2 font-semibold text-quip-navy transition hover:border-quip-teal hover:text-quip-teal"
              >
                Maybe later
              </button>
              <button
                type="button"
                onClick={handleSurveyStart}
                className="rounded-tile bg-quip-navy px-6 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-quip-teal"
              >
                Take the survey
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
