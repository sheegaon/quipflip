import React from 'react';
import { useGame } from './GameContext';
import type { ClaimQuestRewardResponse, Quest } from '../api/types';

type QuestContextValue = {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  hasClaimableQuests: boolean;
  loading: boolean;
  error: string | null;
  refreshQuests: () => Promise<void>;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
  clearError: () => void;
};

export const QuestProvider: React.FC<React.PropsWithChildren> = ({ children }) => {
  // The GameContext now owns all quest state, so the provider simply renders children.
  return <>{children}</>;
};

export const useQuests = (): QuestContextValue => {
  const { state, actions } = useGame();
  const {
    quests,
    activeQuests,
    claimableQuests,
    questsLoading,
    questsError,
    hasClaimableQuests,
  } = state;
  const { refreshQuests, claimQuest, clearQuestError } = actions;

  return {
    quests,
    activeQuests,
    claimableQuests,
    hasClaimableQuests,
    loading: questsLoading,
    error: questsError,
    refreshQuests,
    claimQuest,
    clearError: clearQuestError,
  };
};
