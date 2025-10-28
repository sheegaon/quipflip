import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import apiClient from '../api/client';
import { getActionErrorMessage } from '../utils/errorMessages';
import { gameContextLogger } from '../utils/logger';
import type { Quest, ClaimQuestRewardResponse } from '../api/types';

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
    gameContextLogger.debug('🎯 QuestContext refreshQuests called');
    
    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for quest refresh');
      setQuestState((prev) => ({
        ...prev,
        loading: false,
        error: 'Authentication required. Please log in again.',
      }));
      return;
    }

    gameContextLogger.debug('🔄 Setting quest loading state to true');
    setQuestState((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    try {
      gameContextLogger.debug('📞 Making parallel quest API calls...');
      const [allQuestsResponse, activeQuestsResponse, claimableQuestsResponse] = await Promise.all([
        apiClient.getQuests(),
        apiClient.getActiveQuests(),
        apiClient.getClaimableQuests(),
      ]);

      gameContextLogger.debug('✅ Quest API calls successful:', {
        totalQuests: allQuestsResponse.quests.length,
        activeQuests: activeQuestsResponse.length,
        claimableQuests: claimableQuestsResponse.length
      });

      setQuestState({
        quests: allQuestsResponse.quests,
        activeQuests: activeQuestsResponse,
        claimableQuests: claimableQuestsResponse,
        loading: false,
        error: null,
        lastUpdated: Date.now(),
        hasClaimableQuests: claimableQuestsResponse.length > 0,
      });

      gameContextLogger.debug('✅ Quest state updated successfully');
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
  }, []);

  const clearQuestError = useCallback(() => {
    gameContextLogger.debug('🧹 Clearing quest error');
    setQuestState((prev) => ({
      ...prev,
      error: null,
    }));
  }, []);

  const claimQuest = useCallback(async (questId: string): Promise<ClaimQuestRewardResponse> => {
    gameContextLogger.debug('🎯 QuestContext claimQuest called:', { questId });

    const token = await apiClient.ensureAccessToken();
    if (!token) {
      gameContextLogger.warn('❌ No valid token for quest claim');
      setQuestState((prev) => ({
        ...prev,
        error: 'Authentication required. Please log in again.',
      }));
      throw new Error('Authentication required');
    }

    gameContextLogger.debug('🔄 Setting quest loading state for claim');
    setQuestState((prev) => ({
      ...prev,
      loading: true,
      error: null,
    }));

    try {
      gameContextLogger.debug('📞 Calling apiClient.claimQuestReward...');
      const response = await apiClient.claimQuestReward(questId);
      gameContextLogger.debug('✅ Quest claim successful:', response);

      gameContextLogger.debug('🔄 Refreshing quests after claim...');
      await refreshQuests();
      
      gameContextLogger.debug('🔄 Triggering dashboard refresh after quest claim');
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
      gameContextLogger.debug('🔄 Setting quest loading to false');
      setQuestState((prev) => ({
        ...prev,
        loading: false,
      }));
    }
  }, [refreshQuests, onDashboardTrigger]);

  // Auto-load quests when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      gameContextLogger.debug('🚪 User not authenticated, clearing quest state');
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

    gameContextLogger.debug('🔄 User authenticated, loading quests...');
    refreshQuests().catch((err) => {
      gameContextLogger.error('❌ Failed to auto-load quests:', err);
    });
  }, [isAuthenticated, refreshQuests]);

  // Update hasClaimableQuests when claimableQuests changes
  useEffect(() => {
    setQuestState(prev => ({
      ...prev,
      hasClaimableQuests: prev.claimableQuests.length > 0
    }));
  }, [questState.claimableQuests]);

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
