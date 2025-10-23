import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import { Timer } from '../components/Timer';
import { Header } from '../components/Header';
import TutorialWelcome from '../components/Tutorial/TutorialWelcome';
import { dashboardLogger } from '../utils/logger';

const formatWaitingCount = (count: number): string => (count > 10 ? 'over 10' : count.toString());

export const Dashboard: React.FC = () => {
  const { state, actions } = useGame();
  const { player, activeRound, phrasesetSummary, roundAvailability } = state;
  const { refreshDashboard } = actions;
  const { startTutorial, skipTutorial, advanceStep } = useTutorial();
  const navigate = useNavigate();
  const [isRoundExpired, setIsRoundExpired] = useState(false);
  const [startingRound, setStartingRound] = useState<string | null>(null);

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

  const handleStartTutorial = async () => {
    await startTutorial();
    await advanceStep('dashboard');
  };

  const handleSkipTutorial = async () => {
    await skipTutorial();
  };

  const activeRoundRoute = useMemo(() => {
    return activeRound?.round_type ? `/${activeRound.round_type}` : null;
  }, [activeRound?.round_type]);

  const activeRoundLabel = useMemo(() => {
    if (!activeRound?.round_type) return '';
    return `${activeRound.round_type.charAt(0).toUpperCase()}${activeRound.round_type.slice(1)}`;
  }, [activeRound?.round_type]);

  // Refresh when page becomes visible
  useEffect(() => {
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        refreshDashboard();
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
      return;
    }

    if (!activeRound.expires_at) {
      setIsRoundExpired(false);
      return;
    }

    const expiresAt = new Date(activeRound.expires_at).getTime();
    const now = Date.now();
    setIsRoundExpired(expiresAt <= now);
  }, [activeRound?.round_id, activeRound?.expires_at]);

  const handleContinueRound = useCallback(() => {
    if (activeRoundRoute) {
      navigate(activeRoundRoute);
    }
  }, [activeRoundRoute, navigate]);

  const handleRoundExpired = useCallback(() => {
    setIsRoundExpired(true);
    // Background polling will refresh data automatically
  }, []);

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
    try {
      dashboardLogger.debug('Calling actions.startPromptRound()...');
      await actions.startPromptRound();
      dashboardLogger.info('✅ Prompt round started successfully, navigating to /prompt');
      navigate('/prompt');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start prompt round:', err);
      console.error('Failed to start prompt round:', err);
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
    try {
      dashboardLogger.debug('Calling actions.startCopyRound()...');
      await actions.startCopyRound();
      dashboardLogger.info('✅ Copy round started successfully, navigating to /copy');
      navigate('/copy');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start copy round:', err);
      console.error('Failed to start copy round:', err);
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
    try {
      dashboardLogger.debug('Calling actions.startVoteRound()...');
      await actions.startVoteRound();
      dashboardLogger.info('✅ Vote round started successfully, navigating to /vote');
      navigate('/vote');
    } catch (err) {
      dashboardLogger.error('❌ Failed to start vote round:', err);
      console.error('Failed to start vote round:', err);
    } finally {
      setStartingRound(null);
      dashboardLogger.debug('Vote round start process completed');
    }
  };

  const handleClaimResults = () => {
    navigate('/tracking');
  };

  // Hide certain dashboard elements during tutorial to reduce overwhelm
  const unclaimedPromptCount = phrasesetSummary?.finalized.unclaimed_prompts ?? 0;
  const unclaimedCopyCount = phrasesetSummary?.finalized.unclaimed_copies ?? 0;
  const totalUnclaimedCount = unclaimedPromptCount + unclaimedCopyCount;
  const totalUnclaimedAmount = phrasesetSummary?.total_unclaimed_amount ?? 0;

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
          <div className="tile-card bg-quip-orange bg-opacity-10 border-2 border-quip-orange p-4 mb-6 slide-up-enter">
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

        {totalUnclaimedCount > 0 && (
          <div className="tile-card bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise p-4 mb-6 slide-up-enter">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="font-display font-semibold text-quip-turquoise">Quip-tastic! Prizes Ready to Claim</p>
                <p className="text-sm text-quip-teal">
                  {unclaimedPromptCount} prompt{unclaimedPromptCount === 1 ? '' : 's'} • {unclaimedCopyCount} cop{unclaimedCopyCount === 1 ? 'y' : 'ies'} • ${totalUnclaimedAmount} total
                </p>
              </div>
              <button
                onClick={handleClaimResults}
                className="w-full sm:w-auto bg-quip-turquoise hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                Claim Prizes
              </button>
            </div>
          </div>
        )}

        {/* Round Selection */}
        <div className="tutorial-dashboard tile-card p-6 shuffle-enter">
          <h2 className="text-xl font-display font-bold mb-4 text-quip-navy">Start a Round</h2>

          <div className="space-y-4">

            {/* Prompt Round */}
            <div className="tutorial-prompt-round border-2 border-quip-navy rounded-tile p-4 bg-quip-navy bg-opacity-5 hover:bg-opacity-10 transition-all">
              <div className="flex justify-between items-center mb-2">
                <div className="flex items-center gap-2">
                  <img src="/icon_prompt.svg" alt="" className="w-8 h-8" />
                  <h3 className="font-display font-semibold text-lg text-quip-navy">Prompt Round</h3>
                </div>
                <span className="text-quip-orange-deep font-bold">-$100</span>
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
                 player.balance < 100 ? 'Insufficient Balance' :
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
                  {roundAvailability?.copy_discount_active && (
                    <img
                      src="/badge_copy-discount.svg"
                      alt="Copy discount active"
                      className="h-7"
                    />
                  )}
                  -${roundAvailability?.copy_cost || 100}
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
                <span className="text-quip-orange-deep font-bold">-$1</span>
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
                 player.balance < 1 ? 'Insufficient Balance' :
                 'Not Available'}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
