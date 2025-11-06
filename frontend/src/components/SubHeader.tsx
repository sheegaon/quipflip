import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { useQuests } from '../contexts/QuestContext';
import { TreasureChestIcon } from './TreasureChestIcon';

export const SubHeader: React.FC = () => {
  const { state, actions } = useGame();
  const { player, phrasesetSummary } = state;
  const { refreshDashboard } = actions;
  const { state: resultsState } = useResults();
  const { pendingResults, viewedResultIds } = resultsState;
  const { state: questState } = useQuests();
  const { hasClaimableQuests } = questState;
  const navigate = useNavigate();

  if (!player) {
    return null;
  }

  const inProgressPrompts = phrasesetSummary?.in_progress.prompts ?? 0;
  const inProgressCopies = phrasesetSummary?.in_progress.copies ?? 0;
  const showInProgressIndicator = inProgressPrompts + inProgressCopies > 0;
  const inProgressLabelParts: string[] = [];
  if (inProgressPrompts > 0) {
    inProgressLabelParts.push(`${inProgressPrompts} prompt${inProgressPrompts === 1 ? '' : 's'}`);
  }
  if (inProgressCopies > 0) {
    inProgressLabelParts.push(`${inProgressCopies} ${inProgressCopies === 1 ? 'copy' : 'copies'}`);
  }
  const inProgressLabel = inProgressLabelParts.length
    ? `In-progress rounds: ${inProgressLabelParts.join(' and ')}`
    : 'View your in-progress rounds';

  // Calculate unviewed results by filtering out viewed ones
  const unviewedResults = pendingResults.filter(result =>
    !result.result_viewed && !viewedResultIds.has(result.phraseset_id)
  );
  const unviewedCount = unviewedResults.length;

  // Show trophy after user has ever had finalized results
  const finalizedPrompts = phrasesetSummary?.finalized.prompts ?? 0;
  const finalizedCopies = phrasesetSummary?.finalized.copies ?? 0;
  const showResultsIndicator = (finalizedPrompts + finalizedCopies) > 0;

  const resultsLabel = unviewedCount > 0
    ? `${unviewedCount} result${unviewedCount === 1 ? '' : 's'} ready to view`
    : 'View your results';

  // Check if today is the player's first day (hide treasure chest on first day)
  const isFirstDay = React.useMemo(() => {
    if (!player?.created_at) return false;

    const createdDate = new Date(player.created_at);
    const today = new Date();

    return (
      createdDate.getUTCFullYear() === today.getUTCFullYear() &&
      createdDate.getUTCMonth() === today.getUTCMonth() &&
      createdDate.getUTCDate() === today.getUTCDate()
    );
  }, [player?.created_at]);

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

  const goToStatistics = React.useCallback(() => {
    navigate('/statistics');
  }, [navigate]);

  return (
    <div className="bg-white shadow-tile-sm">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-3">
        <div className="flex justify-between items-center">
          {/* Left: In-progress and Results indicators */}
          <div className="flex items-center gap-0.5 md:gap-3">
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
                  className="h-5 w-5 md:h-7 md:w-7"
                />
              </button>
            )}
          </div>

          {/* Center: Empty spacer for symmetry */}
          <div className="flex-1 text-center"></div>

          {/* Right: Statistics icon and Treasure Chest */}
          <div className="flex items-center gap-0.5 md:gap-4">
            {/* Statistics Icon Button */}
            <button
              onClick={goToStatistics}
              className="group"
              title="View your statistics"
              aria-label="View your statistics"
            >
              <img
                src="/icon_stats.svg"
                alt=""
                className="w-7 h-7 md:w-10 md:h-10 transition-transform group-hover:scale-110"
                aria-hidden="true"
              />
            </button>
            {/* Treasure Chest - Hidden on first day, navigates to quests page */}
            {!isFirstDay && (
              <button
                onClick={() => navigate('/quests')}
                className="relative group"
                title={(player.daily_bonus_available || hasClaimableQuests) ? "View available rewards" : "No rewards available"}
              >
                <TreasureChestIcon
                  className="w-7 h-7 md:w-10 md:h-10 transition-transform group-hover:scale-110"
                  isAvailable={player.daily_bonus_available || hasClaimableQuests}
                />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
