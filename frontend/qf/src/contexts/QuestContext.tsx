/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '@crowdcraft/api/client.ts';
import { getActionErrorMessage } from '../utils/errorMessages';
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

  const refreshQuests = useCallback(async () => {
    // Note: Don't check isAuthenticated here - it causes stale closure issues
    // The auto-load effect already guards against unauthenticated calls
    setQuestState((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    try {
      const [allQuestsResponse, activeQuestsResponse, claimableQuestsResponse] = await Promise.all([
        apiClient.getQuests(),
        apiClient.getActiveQuests(),
        apiClient.getClaimableQuests(),
      ]);

      setQuestState({
        quests: allQuestsResponse.quests,
        activeQuests: activeQuestsResponse,
        claimableQuests: claimableQuestsResponse,
        loading: false,
        error: null,
        lastUpdated: Date.now(),
        hasClaimableQuests: claimableQuestsResponse.length > 0,
      });
    } catch (err) {
      gameContextLogger.error('❌ Quest refresh failed:', err);
      const errorMessage = getActionErrorMessage('load-quests', err);
      setQuestState((prev) => ({
        ...prev,
        loading: false,
        error: errorMessage,
      }));
      throw err;
    }
  }, []); // Note: Empty deps - function is stable, guards are in the effect

  const clearQuestError = useCallback(() => {
    setQuestState((prev) => ({
      ...prev,
      error: null,
    }));
  }, []);

  const claimQuest = useCallback(async (questId: string): Promise<ClaimQuestRewardResponse> => {
    setQuestState((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    try {
      const response = await apiClient.claimQuestReward(questId);
      gameContextLogger.info('✅ Quest claimed successfully:', { questId, reward: response.reward_amount });

      await refreshQuests();
      onDashboardTrigger();
      
      return response;
    } catch (err) {
      gameContextLogger.error('❌ Quest claim failed:', err);
      const errorMessage = getActionErrorMessage('claim-quest', err);
      setQuestState((prev) => ({
        ...prev,
        error: errorMessage,
      }));
      throw err;
    } finally {
      setQuestState((prev) => ({
        ...prev,
        loading: false,
      }));
    }
  }, [refreshQuests, onDashboardTrigger]);

  // Auto-load quests when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      setQuestState({
        quests: [],
        activeQuests: [],
        claimableQuests: [],
        loading: false,
        error: null,
        lastUpdated: null,
        hasClaimableQuests: false,
      });
      return;
    }

    refreshQuests().catch((err) => {
      gameContextLogger.error('❌ Failed to auto-load quests:', err);
    });
  }, [isAuthenticated, refreshQuests]);

  const actions: QuestActions = {
    refreshQuests,
    clearQuestError,
    claimQuest,
  };

  const value: QuestContextType = {
    state: questState,
    actions,
  };

  return <QuestContext.Provider value={value}>{children}</QuestContext.Provider>;
};

export const useQuests = (): QuestContextType => {
  const context = useContext(QuestContext);
  if (!context) {
    throw new Error('useQuests must be used within a QuestProvider');
  }
  return context;
};
