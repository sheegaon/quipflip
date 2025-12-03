import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useHeaderIndicators } from '../hooks/useHeaderIndicators';
import { useTutorial } from '../contexts/TutorialContext';
import { TreasureChestIcon } from '@crowdcraft/components/icons/TreasureChestIcon';
import { CopyRoundIcon } from '@crowdcraft/components/icons/RoundIcons';
import { LeaderboardIcon, LobbyIcon, TrackingIcon } from '@crowdcraft/components/icons/NavigationIcons';
import { QuestionMarkIcon, ResultsIcon, ReviewIcon } from '@crowdcraft/components/icons/EngagementIcons';

export const SubHeader: React.FC = () => {
  const { actions } = useGame();
  const { refreshDashboard } = actions;
  const navigate = useNavigate();
  const location = useLocation();
  const {
    state: { status: tutorialStatus },
  } = useTutorial();

  const {
    player,
    inProgressPrompts,
    inProgressCopies,
    showInProgressIndicator,
    inProgressLabel,
    unviewedCount,
    showResultsIndicator,
    resultsLabel,
    isFirstDay,
    hasClaimableQuests,
  } = useHeaderIndicators();

  // Refresh dashboard data when returning to dashboard
  React.useEffect(() => {
    if (location.pathname === '/dashboard') {
      const refreshSubHeaderData = async () => {
        try {
          await refreshDashboard();
        } catch (err) {
          console.debug('Failed to refresh dashboard on SubHeader mount:', err);
        }
      };

      refreshSubHeaderData();
    }
  }, [location.pathname, refreshDashboard]);

  const handleResultsClick = async () => {
    try {
      await refreshDashboard();
    } catch (err) {
      console.warn('Failed to refresh dashboard in sub-header:', err);
    }

    navigate('/game/results');
  };

  if (!player) {
    return null;
  }

  const showQuestionMarkIcon = player.is_guest || !tutorialStatus?.completed || isFirstDay;

  return (
    <div className="bg-ccl-warm-ivory shadow-tile-sm relative z-40">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
        <div className="flex justify-evenly items-center">
          {/* In-progress indicator */}
          {showInProgressIndicator && (
            <button
              type="button"
              onClick={() => navigate('/game/history')}
              className="flex items-center gap-2 rounded-full bg-ccl-cream px-1 md:px-3 py-1 text-xs font-semibold text-ccl-navy transition-colors hover:bg-ccl-teal-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
              title={inProgressLabel}
              aria-label={inProgressLabel}
            >
              {inProgressPrompts > 0 && (
                <span className="flex items-center md:gap-1 gap-0.5">
                  <span>{inProgressPrompts}</span>
                  <TrackingIcon className="h-5 w-5 md:h-7 md:w-7" />
                </span>
              )}
              {inProgressCopies > 0 && (
                <span className="flex items-center md:gap-1 gap-0.5">
                  <span>{inProgressCopies}</span>
                  <CopyRoundIcon className="h-5 w-5 md:h-7 md:w-7" aria-hidden="true" />
                </span>
              )}
            </button>
          )}

          {/* Results indicator */}
          {showResultsIndicator && (
            <button
              type="button"
              onClick={handleResultsClick}
              className={`flex items-center gap-1 rounded-full px-1 md:px-3 py-1 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 ${
                unviewedCount > 0
                  ? 'bg-ccl-orange bg-opacity-10 text-ccl-orange hover:bg-ccl-orange hover:bg-opacity-20 focus-visible:ring-ccl-orange'
                  : 'bg-gray-200 text-black hover:bg-gray-300 focus-visible:ring-gray-400'
              }`}
              title={resultsLabel}
              aria-label={resultsLabel}
            >
              <span>{unviewedCount}</span>
              <ResultsIcon
                className={`h-5 w-5 md:h-7 md:w-7 ${unviewedCount > 0 ? 'trophy-pulse' : ''}`}
                variant={unviewedCount > 0 ? 'orange' : 'teal'}
              />
            </button>
          )}

          {/* Completed rounds icon - Hidden on first day */}
          {!isFirstDay && (
            <button
              onClick={() => navigate('/completed')}
              className="group tutorial-completed-icon"
              title="View completed rounds"
              aria-label="View completed rounds"
            >
              <ReviewIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
            </button>
          )}

          {/* Leaderboard icon - Hidden on first day */}
          {!isFirstDay && (
            <button
              onClick={() => navigate('/leaderboard')}
              className="group"
              title="View the leaderboard"
              aria-label="View the leaderboard"
            >
              <LeaderboardIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
            </button>
          )}

          {/* Online Users icon */}
          <button
            onClick={() => navigate('/online-users')}
            className="group"
            title="View who's online"
            aria-label="View who's online"
          >
            <LobbyIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
          </button>

          {/* Tutorial icon - Only shown if tutorial not completed */}
          {showQuestionMarkIcon && (
            <button
              onClick={() => navigate('/dashboard?startTutorial=true')}
              className="group"
              title="Start or resume tutorial"
              aria-label="Start or resume tutorial"
            >
              <QuestionMarkIcon className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110" />
            </button>
          )}

          {/* Treasure chest - Hidden on first day */}
          {!isFirstDay && (
            <button
              onClick={() => navigate('/quests')}
              className="relative group"
              title={player.daily_bonus_available || hasClaimableQuests ? 'View available rewards' : 'No rewards available'}
            >
              <TreasureChestIcon
                className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
                isAvailable={player.daily_bonus_available || hasClaimableQuests}
              />
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

export default SubHeader;
