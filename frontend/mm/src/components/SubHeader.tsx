import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useHeaderIndicators } from '../hooks/useHeaderIndicators';
import { useTutorial } from '../contexts/TutorialContext';
import { SubHeader as SharedSubHeader } from '@crowdcraft';

export const SubHeader: React.FC = () => {
  const { actions } = useGame();
  const { refreshDashboard } = actions;
  const navigate = useNavigate();
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

  const showQuestionMarkIcon = player.is_guest || tutorialStatus?.completed === false || isFirstDay;

  return (
    <SharedSubHeader
      showInProgressIndicator={showInProgressIndicator}
      inProgressPrompts={inProgressPrompts}
      inProgressCopies={inProgressCopies}
      inProgressLabel={inProgressLabel}
      showResultsIndicator={showResultsIndicator}
      resultsLabel={resultsLabel}
      unviewedCount={unviewedCount}
      isFirstDay={isFirstDay}
      hasClaimableQuests={hasClaimableQuests}
      playerHasDailyBonus={player.daily_bonus_available}
      showQuestionMark={showQuestionMarkIcon}
      onTrackingClick={() => navigate('/game/history')}
      onResultsClick={handleResultsClick}
      onLeaderboardClick={() => navigate('/leaderboard')}
      onOnlineUsersClick={() => navigate('/online-users')}
      onTutorialClick={() => navigate('/dashboard?startTutorial=true')}
      onQuestsClick={() => navigate('/quests')}
    />
  );
};
