import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Quest, ClaimQuestRewardResponse } from '../api/types';
import apiClient from '../api/client';

interface QuestContextType {
  quests: Quest[];
  activeQuests: Quest[];
  claimableQuests: Quest[];
  hasClaimableQuests: boolean;
  loading: boolean;
  error: string | null;
  refreshQuests: () => Promise<void>;
  claimQuest: (questId: string) => Promise<ClaimQuestRewardResponse>;
  clearError: () => void;
}

const QuestContext = createContext<QuestContextType | undefined>(undefined);

export const useQuests = () => {
  const context = useContext(QuestContext);
  if (!context) {
    throw new Error('useQuests must be used within a QuestProvider');
  }
  return context;
};

interface QuestProviderProps {
  children: ReactNode;
}

export const QuestProvider: React.FC<QuestProviderProps> = ({ children }) => {
  const [quests, setQuests] = useState<Quest[]>([]);
  const [activeQuests, setActiveQuests] = useState<Quest[]>([]);
  const [claimableQuests, setClaimableQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasClaimableQuests = claimableQuests.length > 0;

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const refreshQuests = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Fetch all quest lists in parallel
      const [allQuestsResponse, activeQuestsResponse, claimableQuestsResponse] = await Promise.all([
        apiClient.getQuests(),
        apiClient.getActiveQuests(),
        apiClient.getClaimableQuests()
      ]);

      setQuests(allQuestsResponse.quests);
      setActiveQuests(activeQuestsResponse);
      setClaimableQuests(claimableQuestsResponse);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load quests';
      setError(errorMessage);
      console.error('Error refreshing quests:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  const claimQuest = useCallback(async (questId: string): Promise<ClaimQuestRewardResponse> => {
    setLoading(true);
    setError(null);

    try {
      const response = await apiClient.claimQuestReward(questId);

      // Refresh quests after successful claim to update UI
      await refreshQuests();

      return response;
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to claim quest reward';
      setError(errorMessage);
      console.error('Error claiming quest:', err);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [refreshQuests]);

  const value: QuestContextType = {
    quests,
    activeQuests,
    claimableQuests,
    hasClaimableQuests,
    loading,
    error,
    refreshQuests,
    claimQuest,
    clearError,
  };

  return (
    <QuestContext.Provider value={value}>
      {children}
    </QuestContext.Provider>
  );
};
