import { useGame } from '../contexts/GameContext';

/**
 * Custom hook that returns header indicator data for ThinkLink.
 * TL has a simpler structure than MM, so this just returns player data.
 */
export const useHeaderIndicators = () => {
  const { state } = useGame();
  const { player } = state;

  return {
    // Player data
    player,

    // TL doesn't have the same complex indicators as MM
    // but we provide a consistent interface for Header compatibility
    showInProgressIndicator: false,
    inProgressLabel: 'Play',
    showResultsIndicator: false,
    resultsLabel: 'Results',
    isFirstDay: false,
    hasClaimableQuests: false,
    unviewedCount: 0,
  };
};
