import React from 'react';
import { useGame } from '../contexts/GameContext';
import { useResults } from '../contexts/ResultsContext';
import { useQuests } from '@crowdcraft/contexts/QuestContext';

/**
 * Custom hook that calculates visibility and labels for header/sub-header indicators
 * including in-progress rounds, results, and quest status.
 */
export const useHeaderIndicators = () => {
  const { state } = useGame();
  const { player, phrasesetSummary } = state;
  const { state: resultsState } = useResults();
  const { pendingResults, viewedResultIds } = resultsState;
  const { state: questState } = useQuests();
  const { hasClaimableQuests } = questState;

  // In-progress rounds indicators
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

  // Results indicators
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

  return {
    // In-progress indicators
    inProgressPrompts,
    inProgressCopies,
    showInProgressIndicator,
    inProgressLabel,

    // Results indicators
    unviewedCount,
    showResultsIndicator,
    resultsLabel,

    // Quest indicators
    isFirstDay,
    hasClaimableQuests,

    // Player data
    player,
  };
};
