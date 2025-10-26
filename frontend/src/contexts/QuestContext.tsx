import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import { Quest, ClaimQuestRewardResponse } from '../api/types';
import apiClient from '../api/client';
import { useGame } from './GameContext';

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
  const { state } = useGame();
  const { isAuthenticated } = state;

  const [quests, setQuests] = useState<Quest[]>([]);
  const [activeQuests, setActiveQuests] = useState<Quest[]>([]);
  const [claimableQuests, setClaimableQuests] = useState<Quest[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const hasClaimableQuests = claimableQuests.length > 0;
  const hasInitialLoadRef = useRef(false);

  const clearError = useCallback(() => {
    setError(null);
  }, []);

  const refreshQuests = useCallback(async () => {
    console.log('🎯 QuestContext: refreshQuests() called');
    setLoading(true);
    setError(null);

    try {
      console.log('🎯 QuestContext: Fetching quest data from API...');
      // Fetch all quest lists in parallel
      const [allQuestsResponse, activeQuestsResponse, claimableQuestsResponse] = await Promise.all([
        apiClient.getQuests(),
        apiClient.getActiveQuests(),
        apiClient.getClaimableQuests()
      ]);

      console.log('🎯 QuestContext: API responses received:', {
        totalQuests: allQuestsResponse.quests.length,
        activeQuests: activeQuestsResponse.length,
        claimableQuests: claimableQuestsResponse.length,
        counts: {
          active: allQuestsResponse.active_count,
          completed: allQuestsResponse.completed_count,
          claimed: allQuestsResponse.claimed_count,
        }
      });

      setQuests(allQuestsResponse.quests);
      setActiveQuests(activeQuestsResponse);
      setClaimableQuests(claimableQuestsResponse);

      console.log('🎯 QuestContext: Quest state updated successfully');
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to load quests';
      setError(errorMessage);
      console.error('❌ QuestContext: Error refreshing quests:', err);
      console.error('❌ QuestContext: Error details:', errorMessage);
    } finally {
      setLoading(false);
      console.log('🎯 QuestContext: refreshQuests() completed');
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

  // Auto-refresh quests when user becomes authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      hasInitialLoadRef.current = false;
      return;
    }

    // Prevent duplicate loads in React StrictMode
    if (hasInitialLoadRef.current) return;
    hasInitialLoadRef.current = true;

    console.log('🎯 QuestContext: User authenticated, auto-loading quests');
    refreshQuests();
  }, [isAuthenticated, refreshQuests]);

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
