import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { Timer } from '../components/Timer';
import { Header } from '../components/Header';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import { ModeToggle } from '../components/ModeToggle';
import { UpgradeGuestAccount } from '../components/UpgradeGuestAccount';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';
import BetaSurveyModal from '../components/BetaSurveyModal';
import { dashboardLogger } from '../utils/logger';
import { TrackingIcon, PartyIcon } from '../components/icons/NavigationIcons';
import { CopyRoundIcon, VoteRoundIcon } from '../components/icons/RoundIcons';
import { hasDismissedSurvey, hasCompletedSurvey } from '../utils/betaSurvey';

const formatWaitingCount = (count: number): string => (count > 10 ? 'over 10' : count.toString());
export const Dashboard: React.FC = () => {
  const { state, actions } = useGame();

  // Load mode from localStorage, defaulting to 'live'
  const [mode, setMode] = useState<'live' | 'practice'>(() => {
    const savedMode = localStorage.getItem('quipflip_game_mode');
    dashboardLogger.debug('Loading mode from localStorage:', { savedMode });
    const initialMode = (savedMode === 'practice' || savedMode === 'live') ? savedMode : 'live';
    dashboardLogger.debug('Initial mode set to:', { initialMode });
    return initialMode;
  });
  const {
    player,
    activeRound,
    roundAvailability,
    error: contextError,
    isAuthenticated,
  } = state;
  const { refreshDashboard, clearError, abandonRound } = actions;
  const { startTutorial, skipTutorial } = useTutorial();
  const navigate = useNavigate();
  const location = useLocation();
  const [isRoundExpired, setIsRoundExpired] = useState(false);
  const [startingRound, setStartingRound] = useState<string | null>(null);
  const [roundStartError, setRoundStartError] = useState<string | null>(null);
  const [showSurveyPrompt, setShowSurveyPrompt] = useState(false);
  const [isAbandoningRound, setIsAbandoningRound] = useState(false);
  const [abandonError, setAbandonError] = useState<string | null>(null);
  const [showTutorialWelcome, setShowTutorialWelcome] = useState(false);
  const roundExpiryTimeoutRef = useRef<number | null>(null);

  // Log component mount and key state changes
  useEffect(() => {
    dashboardLogger.debug('Component mounted');
  }, []);

  // Persist mode to localStorage whenever it changes
  useEffect(() => {
    localStorage.setItem('quipflip_game_mode', mode);
    dashboardLogger.debug('Game mode changed and saved to localStorage:', { mode });
    // Verify it was saved correctly
    const verification = localStorage.getItem('quipflip_game_mode');
    dashboardLogger.debug('Verification - value in localStorage:', { verification });
  }, [mode]);

  // Refresh dashboard when navigating back to it
  const previousPathRef = useRef<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    const currentPath = location.pathname;
    const previousPath = previousPathRef.current;

    // Refresh when navigating TO /dashboard FROM another page
    // Skip refresh when coming from /results since Results page already refreshes the dashboard
    const shouldRefresh =
      currentPath === '/dashboard' &&
      previousPath !== null &&
      previousPath !== '/dashboard' &&
      previousPath !== '/results' &&
      isAuthenticated;

    if (shouldRefresh) {
      dashboardLogger.debug('Navigated back to dashboard, refreshing...', { from: previousPath });
      refreshDashboard(controller.signal).catch((err) => {
        if (controller.signal.aborted) {
          dashboardLogger.debug('Dashboard refresh aborted on navigation back');
          return;
        }
        dashboardLogger.warn('Failed to refresh dashboard on navigation back:', err);
      });
    } else if (currentPath === '/dashboard' && previousPath === '/results') {
      dashboardLogger.debug('Navigated back from results page, skipping refresh (results page already refreshed)');
    }

    // Update the previous path
    previousPathRef.current = currentPath;

    return () => {
      controller.abort();
    };
  }, [location.pathname, isAuthenticated, refreshDashboard]);

  useEffect(() => {
    if (activeRound) {
      dashboardLogger.debug('Active round changed:', {
        id: activeRound.round_id,
        type: activeRound.round_type,
        expiresAt: activeRound.expires_at
      });
    }
  }, [activeRound]);

  // Check if survey should be shown
  useEffect(() => {
    const playerId = player?.player_id;

    if (!playerId || !isAuthenticated) {
      setShowSurveyPrompt(false);
      return;
    }

    const controller = new AbortController();

    const checkSurveyEligibility = async () => {
      try {
        const status = await apiClient.getBetaSurveyStatus(controller.signal);

        const dismissed = hasDismissedSurvey(playerId);
        const completedLocal = hasCompletedSurvey(playerId);
        const shouldShow = status.eligible && !status.has_submitted && !dismissed && !completedLocal;

        setShowSurveyPrompt(shouldShow);
      } catch (error: unknown) {
        if (controller.signal.aborted) {
          return;
        }
        // Silently handle errors for survey check
      }
    };

    checkSurveyEligibility();

    return () => {
      controller.abort();
    };
  }, [player?.player_id, isAuthenticated]);

  const handleStartTutorial = async () => {
    dashboardLogger.debug('Starting tutorial from dashboard');
    setShowTutorialWelcome(false);
    await startTutorial();
  };

  const handleSkipTutorial = async () => {
    setShowTutorialWelcome(false);
    await skipTutorial();
  };

  // Check for startTutorial query parameter
  useEffect(() => {
    const searchParams = new URLSearchParams(location.search);
    if (searchParams.get('startTutorial') === 'true') {
      dashboardLogger.debug('Showing tutorial welcome from query parameter');
      setShowTutorialWelcome(true);
      // Clear the query parameter
      searchParams.delete('startTutorial');
      const newSearch = searchParams.toString();
      navigate(`/dashboard${newSearch ? `?${newSearch}` : ''}`, { replace: true });
    }
  }, [location.search, navigate]);

  const activeRoundRoute = useMemo(() => {
    return activeRound?.round_type ? `/${activeRound.round_type}` : null;
  }, [activeRound]);

  const activeRoundLabel = useMemo(() => {
    if (!activeRound?.round_type) return '';
    return `${activeRound.round_type.charAt(0).toUpperCase()}${activeRound.round_type.slice(1)}`;
  }, [activeRound]);

  const canAbandonRound = useMemo(() => {
    return Boolean(activeRound?.round_type);
  }, [activeRound?.round_type]);

  const refreshDashboardAfterCountdown = useCallback(
    async (source: string) => {
      if (!isAuthenticated) {
        dashboardLogger.debug('Skipping dashboard refresh after countdown (unauthenticated)', { source });
        roundExpiryTimeoutRef.current = null;
        return;
      }

      dashboardLogger.debug('Countdown expired, refreshing dashboard', { source });
      try {
        await refreshDashboard();
        dashboardLogger.debug('Dashboard refreshed successfully after countdown', { source });
      } catch (err) {
        dashboardLogger.error('Failed to refresh dashboard after countdown expiration', { source, error: err });
      } finally {
        roundExpiryTimeoutRef.current = null;
      }
    },
    [isAuthenticated, refreshDashboard]
  );

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

  const handleRoundExpired = useCallback(() => {
    if (!isAuthenticated) {
      dashboardLogger.debug('Round expired but user is unauthenticated; skipping refresh scheduling');
      return;
    }

    dashboardLogger.debug('Round expired, setting flag and scheduling refresh in 6 seconds');
    setIsRoundExpired(true);

    if (roundExpiryTimeoutRef.current) {
      clearTimeout(roundExpiryTimeoutRef.current);
    }

    const roundTypeLabel = activeRound?.round_type ?? 'unknown';
    roundExpiryTimeoutRef.current = window.setTimeout(() => {
      dashboardLogger.debug('Executing delayed refresh after round expiration');
      void refreshDashboardAfterCountdown(`round:${roundTypeLabel}`);
    }, 6000);
  }, [activeRound?.round_type, isAuthenticated, refreshDashboardAfterCountdown]);

  useEffect(() => {
    if (!isAuthenticated && roundExpiryTimeoutRef.current) {
      clearTimeout(roundExpiryTimeoutRef.current);
      roundExpiryTimeoutRef.current = null;
    }
  }, [isAuthenticated]);

  useEffect(() => {
    if (!activeRound && roundExpiryTimeoutRef.current) {
      clearTimeout(roundExpiryTimeoutRef.current);
      roundExpiryTimeoutRef.current = null;
    }
  }, [activeRound]);

  useEffect(() => {
    return () => {
      if (roundExpiryTimeoutRef.current) {
        clearTimeout(roundExpiryTimeoutRef.current);
        roundExpiryTimeoutRef.current = null;
      }
    };
  }, []);

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
      // No additional refresh needed - abandonRound action already calls refreshDashboard()
      // which updates both dashboard state and balance immediately
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

    dashboardLogger.info(`Starting quip round in ${mode} mode...`);
    dashboardLogger.debug('Player state before start:', {
      wallet: player?.wallet,
      outstandingPrompts: player?.outstanding_prompts,
      canPrompt: roundAvailability?.can_prompt,
      mode
    });

    setStartingRound('prompt');
    setRoundStartError(null);
    try {
      if (mode === 'practice') {
        dashboardLogger.debug('Practice mode: navigating directly to practice prompt review');
        navigate('/practice/prompt');
      } else {
        dashboardLogger.debug('Calling actions.startPromptRound()...');
        await actions.startPromptRound();
        dashboardLogger.info('✅ Quip round started successfully, navigating to /prompt');
        navigate('/prompt');
      }
    } catch (err) {
      dashboardLogger.error('❌ Failed to start quip round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start quip round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Quip round start process completed');
    }
  };

  const handleStartCopy = async () => {
    if (startingRound) {
      dashboardLogger.debug('Ignoring copy button click - already starting round:', startingRound);
      return;
    }

    dashboardLogger.info(`Starting impostor round in ${mode} mode...`);
    dashboardLogger.debug('Player state before start:', {
      wallet: player?.wallet,
      canCopy: roundAvailability?.can_copy,
      promptsWaiting: roundAvailability?.prompts_waiting,
      copyCost: roundAvailability?.copy_cost,
      mode
    });

    setStartingRound('copy');
    setRoundStartError(null);
    try {
      if (mode === 'practice') {
        dashboardLogger.debug('Practice mode: navigating directly to practice copy review');
        navigate('/practice/copy');
      } else {
        dashboardLogger.debug('Calling actions.startCopyRound()...');
        await actions.startCopyRound();
        dashboardLogger.info('✅ Impostor round started successfully, navigating to /copy');
        navigate('/copy');
      }
    } catch (err) {
      dashboardLogger.error('❌ Failed to start impostor round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start impostor round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Impostor round start process completed');
    }
  };

  const handleStartVote = async () => {
    if (startingRound) {
      dashboardLogger.debug('Ignoring vote button click - already starting round:', startingRound);
      return;
    }

    dashboardLogger.info(`Starting vote round in ${mode} mode...`);
    dashboardLogger.debug('Player state before start:', {
      wallet: player?.wallet,
      canVote: roundAvailability?.can_vote,
      phrasesetsWaiting: roundAvailability?.phrasesets_waiting,
      mode
    });

    setStartingRound('vote');
    setRoundStartError(null);
    try {
      if (mode === 'practice') {
        dashboardLogger.debug('Practice mode: navigating directly to practice vote review');
        navigate('/practice/vote');
      } else {
        dashboardLogger.debug('Calling actions.startVoteRound()...');
        await actions.startVoteRound();
        dashboardLogger.info('✅ Vote round started successfully, navigating to /vote');
        navigate('/vote');
      }
    } catch (err) {
      dashboardLogger.error('❌ Failed to start vote round:', err);
      const errorMsg = extractErrorMessage(err) || 'Unable to start vote round. Please try again.';
      setRoundStartError(errorMsg);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Vote round start process completed');
    }
  };

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
      {showTutorialWelcome && <TutorialWelcome onStart={handleStartTutorial} onSkip={handleSkipTutorial} />}

      <div className="max-w-4xl mx-auto md:px-4 px-3 md:pt-6 pt-2 md:pb-5 pb-20">
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

        {/* Upgrade Guest Account */}
        {player.is_guest && <UpgradeGuestAccount className="mb-0 md:mb-2" />}

        {/* Party Mode */}
        <div className="tile-card md:p-4 p-2 mt-1 mb-1 shuffle-enter bg-quip-orange bg-opacity-10 border-2 border-quip-orange">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div>
              <h2 className="text-xl md:text-2xl font-display font-bold text-quip-navy mb-2 flex items-center gap-2">
                <PartyIcon className="h-7 w-7" />
                Party Mode
              </h2>
              <p className="text-quip-teal">Play with 6-9 players in a coordinated multiplayer match!</p>
            </div>
            <button
              onClick={() => navigate('/party')}
              className="w-full md:w-auto bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-3 px-8 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Enter Party Mode
            </button>
          </div>
        </div>

        {/* Round Selection */}
        <div className="tutorial-dashboard tile-card md:p-6 p-3 shuffle-enter">
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

            {/* Quip Round */}
            <div className="tutorial-prompt-round border-2 border-quip-navy rounded-tile p-4 bg-quip-navy bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <TrackingIcon className="w-8 h-8" />
                  <h3 className="font-display font-semibold text-lg text-quip-navy">Quip Round</h3>
                </div>
                <span className="text-quip-orange-deep font-bold flex items-center gap-1">
                  <CurrencyDisplay amount={mode === 'practice' ? 0 : (roundAvailability?.prompt_cost || 100)} iconClassName="w-4 h-4" textClassName="font-bold" />
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-3">
                Write an original phrase for a creative prompt
              </p>
              <button
                onClick={handleStartPrompt}
                disabled={mode === 'live' && (!roundAvailability?.can_prompt || startingRound === 'prompt')}
                className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'prompt' ? 'Starting Round...' :
                 mode === 'practice' ? 'Practice Quip' :
                 roundAvailability?.can_prompt ? 'Quip!' :
                 activeRound?.round_type === 'prompt' ? 'Active Round - Use Continue Above' :
                 activeRound?.round_id ? 'Complete Current Round First' :
                 (player?.wallet ?? 0) < (roundAvailability?.prompt_cost || 100) ? 'Insufficient Balance' :
                 (player?.outstanding_prompts ?? 0) >= 10 ? 'Too Many Outstanding Prompts' :
                 'Not Available'}
              </button>
            </div>

            {/* Impostor Round */}
            <div className="tutorial-copy-round border-2 border-quip-turquoise rounded-tile p-4 bg-quip-turquoise bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <CopyRoundIcon className="w-8 h-8" aria-hidden="true" />
                  <h3 className="font-display font-semibold text-lg text-quip-turquoise">Impostor Round</h3>
                </div>
                <span className="flex items-center gap-2 text-quip-orange-deep font-bold">
                  {mode === 'live' && roundAvailability?.copy_discount_active && roundAvailability?.prompts_waiting > 0 && (
                    <img
                      src="/badge_copy-discount.svg"
                      alt="Copy discount active"
                      className="h-7"
                    />
                  )}
                  <span className="flex items-center gap-1">
                    <CurrencyDisplay amount={mode === 'practice' ? 0 : (roundAvailability?.copy_cost || 100)} iconClassName="w-4 h-4" textClassName="font-bold" />
                  </span>
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-1">
                Write a phrase that <em>could have been the original</em> and might trick voters.
              </p>
              {mode === 'live' && roundAvailability && roundAvailability.prompts_waiting > 0 && (
                <p className="text-xs text-quip-turquoise mb-3 font-semibold">
                  {formatWaitingCount(roundAvailability.prompts_waiting)} quip
                  {roundAvailability.prompts_waiting > 1 ? 's' : ''} waiting
                </p>
              )}
              <button
                onClick={handleStartCopy}
                disabled={mode === 'live' && (!roundAvailability?.can_copy || startingRound === 'copy')}
                className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'copy' ? 'Starting Round...' :
                 mode === 'practice' ? 'Practice Faking It' :
                 roundAvailability?.can_copy ? 'Fake It!' :
                 activeRound?.round_type === 'copy' ? 'Active Round - Use Continue Above' :
                 activeRound?.round_id ? 'Complete Current Round First' :
                 roundAvailability?.prompts_waiting === 0 ? 'No Quips Available' :
                 (player?.wallet ?? 0) < (roundAvailability?.copy_cost || 100) ? 'Insufficient Balance' :
                 'Not Available'}
              </button>
            </div>

            {/* Vote Round */}
            <div className="tutorial-vote-round border-2 border-quip-orange rounded-tile p-4 bg-quip-orange bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <VoteRoundIcon className="w-8 h-8" aria-hidden="true" />
                  <h3 className="font-display font-semibold text-lg text-quip-orange-deep">Vote Round</h3>
                </div>
                <span className="text-quip-orange-deep font-bold flex items-center gap-1">
                  <CurrencyDisplay amount={mode === 'practice' ? 0 : (roundAvailability?.vote_cost || 10)} iconClassName="w-4 h-4" textClassName="font-bold" />
                </span>
              </div>
              <p className="text-sm text-quip-teal mb-1">
                Spot the original phrase from three options
              </p>
              {mode === 'live' && roundAvailability && roundAvailability.phrasesets_waiting > 0 && (
                <p className="text-xs text-quip-orange-deep mb-3 font-semibold">
                  {formatWaitingCount(roundAvailability.phrasesets_waiting)} quip set
                  {roundAvailability.phrasesets_waiting > 1 ? 's' : ''} waiting
                </p>
              )}
              <button
                onClick={handleStartVote}
                disabled={mode === 'live' && (!roundAvailability?.can_vote || startingRound === 'vote')}
                className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {startingRound === 'vote' ? 'Starting Round...' :
                 mode === 'practice' ? 'Practice Guessing' :
                 roundAvailability?.can_vote ? 'Guess the Original!' :
                 activeRound?.round_type === 'vote' ? 'Active Round - Use Continue Above' :
                 activeRound?.round_id ? 'Complete Current Round First' :
                 roundAvailability?.phrasesets_waiting === 0 ? 'No Quip Sets Available' :
                 (player?.wallet ?? 0) < (roundAvailability?.vote_cost || 10) ? 'Insufficient Balance' :
                 'Not Available'}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mode Toggle */}
      <ModeToggle mode={mode} onChange={setMode} />

      {/* Beta Survey Modal */}
      <BetaSurveyModal 
        isVisible={showSurveyPrompt}
        onDismiss={() => setShowSurveyPrompt(false)}
      />
    </div>
  );
};

export default Dashboard;
