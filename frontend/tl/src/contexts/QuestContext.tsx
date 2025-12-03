import React, { createContext, useContext } from 'react';

interface Quest {
  id: string;
  title: string;
  description: string;
  progress: number;
  target: number;
  reward: number;
  completed: boolean;
}

interface QuestContextType {
  quests: Quest[];
  loading: boolean;
  error: string | null;
  claimReward: (questId: string) => Promise<void>;
  refreshQuests: () => Promise<void>;
}

const QuestContext = createContext<QuestContextType | undefined>(undefined);

export const QuestProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const value: QuestContextType = {
    quests: [],
    loading: false,
    error: null,
    claimReward: async () => {},
    refreshQuests: async () => {},
  };

  return <QuestContext.Provider value={value}>{children}</QuestContext.Provider>;
};

export const useQuests = () => {
  const context = useContext(QuestContext);
  if (!context) {
    throw new Error('useQuests must be used within QuestProvider');
  }
  return context;
};
