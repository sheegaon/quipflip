import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useHeaderIndicators } from '../hooks/useHeaderIndicators';
import { TreasureChestIcon } from './TreasureChestIcon';

export const SubHeader: React.FC = () => {
  const { actions } = useGame();
  const { refreshDashboard } = actions;
  const navigate = useNavigate();

  // Use custom hook to get all indicator values
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

  if (!player) {
    return null;
  }

  const handleResultsClick = async () => {
    // Refresh dashboard to get latest data before navigating
    try {
      await refreshDashboard();
    } catch (err) {
      // Continue navigation even if refresh fails
      console.warn('Failed to refresh dashboard in sub-header:', err);
    }

    // Navigate to results page (results will be marked as viewed on page load)
    navigate('/results');
  };

  const goToLeaderboard = React.useCallback(() => {
    navigate('/leaderboard');
  }, [navigate]);

  return (
    <div className="bg-white shadow-tile-sm">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
        <div className="flex justify-evenly items-center">
          {/* In-progress indicator */}
          {showInProgressIndicator && (
            <button
              type="button"
              onClick={() => navigate('/tracking')}
              className="flex items-center gap-2 rounded-full bg-quip-cream px-1 md:px-3 py-1 text-xs font-semibold text-quip-navy transition-colors hover:bg-quip-teal-light focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
              title={inProgressLabel}
              aria-label={inProgressLabel}
            >
              {inProgressPrompts > 0 && (
                <span className="flex items-center md:gap-1 gap-0.5">
                  <span>{inProgressPrompts}</span>
                  <img
                    src="/icon_prompt.svg"
                    alt="Prompt rounds in progress"
                    className="h-5 w-5 md:h-7 md:w-7"
                  />
                </span>
              )}
              {inProgressCopies > 0 && (
                <span className="flex items-center md:gap-1 gap-0.5">
                  <span>{inProgressCopies}</span>
                  <img
                    src="/icon_copy.svg"
                    alt="Copy rounds in progress"
                    className="h-5 w-5 md:h-7 md:w-7"
                  />
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
                  ? 'bg-quip-orange bg-opacity-10 text-quip-orange hover:bg-quip-orange hover:bg-opacity-20 focus-visible:ring-quip-orange'
                  : 'bg-gray-200 text-black hover:bg-gray-300 focus-visible:ring-gray-400'
              }`}
              title={resultsLabel}
              aria-label={resultsLabel}
            >
              <span>{unviewedCount}</span>
              <img
                src="/icon_results.svg"
                alt="Results ready to view"
                className={`h-5 w-5 md:h-7 md:w-7 ${unviewedCount > 0 ? 'trophy-pulse' : ''}`}
              />
            </button>
          )}

          {/* Completed rounds icon */}
          <button
            onClick={() => navigate('/completed')}
            className="group tutorial-completed-icon"
            title="View completed rounds"
            aria-label="View completed rounds"
          >
            <img
              src="/icon_completed.svg"
              alt=""
              className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
              aria-hidden="true"
            />
          </button>

          {/* Leaderboard icon */}
          <button
            onClick={goToLeaderboard}
            className="group"
            title="View the leaderboard"
            aria-label="View the leaderboard"
          >
            <img
              src="/icon_leaderboard.svg"
              alt=""
              className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
              aria-hidden="true"
            />
          </button>

          {/* Online Users icon */}
          <button
            onClick={() => navigate('/online-users')}
            className="group"
            title="View who's online"
            aria-label="View who's online"
          >
            <img
              src="/icon_online_users.svg"
              alt=""
              className="w-7 h-7 md:w-8 md:h-8 transition-transform group-hover:scale-110"
              aria-hidden="true"
            />
          </button>

          {/* Treasure chest - Hidden on first day */}
          {!isFirstDay && (
            <button
              onClick={() => navigate('/quests')}
              className="relative group"
              title={(player.daily_bonus_available || hasClaimableQuests) ? "View available rewards" : "No rewards available"}
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
