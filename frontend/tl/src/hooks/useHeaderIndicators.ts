import React from 'react';
import { useGame } from '../contexts/GameContext';
import { useQuests } from '@crowdcraft/contexts/QuestContext';

/**
 * Custom hook that calculates visibility and labels for header/sub-header indicators
 * for ThinkLink: active round status, unclaimed results, and quest availability.
 *
 * ThinkLink differences from Quipflip:
 * - No phrasesets; uses single active round at a time
 * - Tracks strikes (0-3) in active round
 * - Results are viewed/unclaimed individually
 * - No pending rounds concept (only active or finished)
 */
export const useHeaderIndicators = () => {
  const { state } = useGame();
  const { player, activeRound, unclaimedResults } = state;
  const { state: questState } = useQuests();
  const { hasClaimableQuests } = questState;

  // Active round indicator (ThinkLink tracks one active round at a time)
  const showActiveRoundIndicator = activeRound !== null;
  const strikesDisplay = activeRound ? `${activeRound.strikes}/3 strikes` : '';
  const activeRoundLabel = activeRound
    ? `Active round: ${strikesDisplay}`
    : 'No active round';

  // Unclaimed results indicators
  const unclaimedCount = unclaimedResults?.length ?? 0;
  const showResultsIndicator = unclaimedCount > 0;

  const resultsLabel = unclaimedCount > 0
    ? `${unclaimedCount} result${unclaimedCount === 1 ? '' : 's'} ready to view`
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

  return {
    // Active round indicators (ThinkLink-specific)
    showActiveRoundIndicator,
    activeRoundLabel,
    strikesDisplay,
    activeRound,

    // Results indicators
    unclaimedCount,
    showResultsIndicator,
    resultsLabel,

    // Quest indicators
    isFirstDay,
    hasClaimableQuests,

    // Player data
    player,
  };
};
