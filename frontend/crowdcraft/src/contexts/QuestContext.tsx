/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '@/api/client';
import { getActionErrorMessage } from '@crowdcraft/utils/errorMessages.ts';
import { gameContextLogger } from '@crowdcraft/utils/logger.ts';
import type { Quest, ClaimQuestRewardResponse } from '@crowdcraft/api/types.ts';

interface QuestState {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  loading: boolean;
  error: string | null;
  lastUpdated: number | null;
  hasClaimableQuests: boolean;
}

interface QuestActions {
  refreshQuests: () => Promise<void>;
  clearQuestError: () => void;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
}

interface QuestContextType {
  state: QuestState;
  actions: QuestActions;
}

const QuestContext = createContext<QuestContextType | undefined>(undefined);

export const QuestProvider: React.FC<{
  children: React.ReactNode;
  isAuthenticated: boolean;
  onDashboardTrigger: () => void;
}> = ({ children, isAuthenticated, onDashboardTrigger }) => {
  const [questState, setQuestState] = useState<QuestState>({
    quests: [],
    activeQuests: [],
    claimableQuests: [],
    loading: false,
    error: null,
    lastUpdated: null,
    hasClaimableQuests: false,
  });

  const clearQuestError = useCallback(() => {
    setQuestState(prev => ({ ...prev, error: null }));
  }, []);

  const refreshQuests = useCallback(async () => {
    if (!isAuthenticated) {
      gameContextLogger.debug('Skipping quest refresh: not authenticated');
      setQuestState(prev => ({ ...prev, loading: false, error: null }));
      return;
    }

    setQuestState(prev => ({ ...prev, loading: true, error: null }));

    try {
      gameContextLogger.debug('📋 Fetching quests');
      const data = await apiClient.getQuests();

      const activeQuests = data.quests.filter((quest: Quest) => quest.status === 'active');
      const claimableQuests = data.quests.filter((quest: Quest) => quest.status === 'completed');

      setQuestState(prev => ({
        ...prev,
        quests: data.quests,
        activeQuests,
        claimableQuests,
        hasClaimableQuests: claimableQuests.length > 0,
        loading: false,
        lastUpdated: Date.now(),
      }));
    } catch (err) {
      const message = getActionErrorMessage('load-quests', err);
      gameContextLogger.error('Failed to load quests', err);
      setQuestState(prev => ({
        ...prev,
        loading: false,
        error: message,
      }));
    }
  }, [isAuthenticated]);

  const claimQuest = useCallback(async (questId: string) => {
    setQuestState(prev => ({ ...prev, loading: true }));

    try {
      gameContextLogger.debug('🎯 Claiming quest reward', { questId });
      const response = await apiClient.claimQuestReward(questId);
      await refreshQuests();
      onDashboardTrigger();
      return response;
    } catch (err) {
      const message = getActionErrorMessage('claim-quest', err);
      gameContextLogger.error('Failed to claim quest reward', err);
      setQuestState(prev => ({
        ...prev,
        loading: false,
        error: message,
      }));
      throw err;
    }
  }, [refreshQuests, onDashboardTrigger]);

  useEffect(() => {
    refreshQuests();
  }, [refreshQuests]);

  useEffect(() => {
    if (!isAuthenticated) {
      gameContextLogger.debug('Clearing quest data on logout');
      setQuestState({
        quests: [],
        activeQuests: [],
        claimableQuests: [],
        loading: false,
        error: null,
        lastUpdated: null,
        hasClaimableQuests: false,
      });
    }
  }, [isAuthenticated]);

  const value: QuestContextType = {
    state: questState,
    actions: {
      refreshQuests,
      clearQuestError,
      claimQuest,
    },
  };

  return <QuestContext.Provider value={value}>{children}</QuestContext.Provider>;
};

export const useQuest = (): QuestContextType => {
  const context = useContext(QuestContext);
  if (!context) {
    throw new Error('useQuest must be used within a QuestProvider');
  }
  return context;
};

export const useQuests = () => useQuest();
