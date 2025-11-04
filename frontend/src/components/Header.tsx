import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { useQuests } from '../contexts/QuestContext';
import { BalanceFlipper } from './BalanceFlipper';
import { TreasureChestIcon } from './TreasureChestIcon';

export const Header: React.FC = () => {
  const { state, actions } = useGame();
  const { player, username, phrasesetSummary } = state;
  const { logout, refreshDashboard, refreshBalance } = actions;
  const { state: resultsState, actions: resultsActions } = useResults();
  const { pendingResults, viewedResultIds } = resultsState;
  const { markResultsViewed } = resultsActions;
  const { state: questState } = useQuests();
  const { hasClaimableQuests } = questState;
  const navigate = useNavigate();
  const location = useLocation();

  // Show back arrow on certain pages
  const isAdminRoute = location.pathname === '/admin' || location.pathname.startsWith('/admin/');
  const showBackArrow = location.pathname === '/statistics' || location.pathname === '/tracking' || location.pathname === '/quests' || location.pathname === '/results' || location.pathname === '/settings' || isAdminRoute;

  // Determine where back arrow should navigate based on current page
  const getBackNavigation = React.useCallback(() => {
    if (location.pathname === '/settings') {
      return '/statistics';
    }
    if (location.pathname === '/admin') {
      return '/settings';
    }
    if (location.pathname.startsWith('/admin/')) {
      return '/admin';
    }
    return '/dashboard';
  }, [location.pathname, isAdminRoute]);

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

  const goToStatistics = React.useCallback(() => {
    navigate('/statistics');
  }, [navigate]);

  const handleLogoClick = React.useCallback(() => {
    refreshDashboard().catch((err) => {
      console.warn('Failed to refresh dashboard from header icon:', err);
    });
    refreshBalance().catch((err) => {
      console.warn('Failed to refresh balance from header icon:', err);
    });

    if (showBackArrow) {
      navigate(getBackNavigation());
    }
  }, [refreshDashboard, refreshBalance, showBackArrow, getBackNavigation, navigate]);

  const logoTitle = showBackArrow
    ? location.pathname === '/settings'
      ? 'Back to Statistics (refresh)'
      : 'Back to Dashboard (refresh)'
    : 'Refresh dashboard';

  // Check if today is the player's first day (hide treasure chest on first day)
  const isFirstDay = React.useMemo(() => {
    if (!player?.created_at) return false;

    const createdDate = new Date(player.created_at);
    const today = new Date();

    return (
      createdDate.getFullYear() === today.getFullYear() &&
      createdDate.getMonth() === today.getMonth() &&
      createdDate.getDate() === today.getDate()
    );
  }, [player?.created_at]);

  const handleResultsClick = async () => {
    // Mark all unviewed results as viewed when clicking
    const unviewedIds = unviewedResults.map(result => result.phraseset_id);
    if (unviewedIds.length > 0) {
      markResultsViewed(unviewedIds);
    }
    
    // Refresh dashboard to get latest data before navigating
    try {
      await refreshDashboard();
    } catch (err) {
      // Continue navigation even if refresh fails
      console.warn('Failed to refresh dashboard in header:', err);
    }
    
    navigate('/results');
  };

  return (
    <div className="bg-white shadow-tile-sm">
      <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-3">
        <div className="flex justify-between items-center">
          {/* Left: Logo + Back Arrow (on certain pages) */}
          <div className="flex items-center gap-0.5 md:gap-3">
            <button
              type="button"
              onClick={handleLogoClick}
              className={`flex items-center gap-0 md:gap-2 cursor-pointer transition-opacity ${showBackArrow ? 'hover:opacity-80' : 'hover:opacity-90'}`}
              title={logoTitle}
              aria-label={logoTitle}
            >
              {showBackArrow && (
                <img
                  src="/icon_back_arrow.svg"
                  alt=""
                  className="w-5 h-5 md:w-9 md:h-9"
                  aria-hidden="true"
                />
              )}
              <img src="/large_icon.png" alt="Quipflip" className="md:h-14 h-6 w-auto" />
            </button>
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

          {/* Center: Username (clickable to player page) */}
          <div className="flex-1 text-center">
            <button
              onClick={goToStatistics}
              className="inline-flex items-center gap-0.5 md:gap-1.5 text-xs md:text-2xl text-quip-turquoise font-semibold hover:text-quip-teal transition-colors group"
              title="View your statistics"
            >
              <span>{player.username || username}</span>
              <img
                src="/icon_stats.svg"
                alt=""
                className="w-4 h-4 md:h-7 md:w-7 transition-transform group-hover:scale-110"
                aria-hidden="true"
              />
            </button>
          </div>

          {/* Right: Daily Bonus + Flipcoins + Logout */}
          <div className="flex items-center gap-0.5 md:gap-4">
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
            {/* Flipcoin Balance */}
            <button
              type="button"
              onClick={goToStatistics}
              className="flex items-center gap-0.5 tutorial-balance border border-white/10 rounded-xl px-1 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-quip-teal"
              title="View your statistics"
              aria-label="View your statistics"
            >
              <img src="/flipcoin.png" alt="Flipcoin" className="w-5 h-5 md:w-8 md:h-8" />
              <BalanceFlipper
                value={player.balance}
                className="text-xl md:text-3xl font-display font-bold text-quip-turquoise"
              />
            </button>
            {/* Logout Button */}
            <button onClick={logout} className="text-quip-teal hover:text-quip-turquoise" title="Logout">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 md:h-10 w-6 md:w-10" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
