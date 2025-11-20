/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { PartyContext } from '../api/types';

export type PartyStep = 'prompt' | 'copy' | 'vote';

interface SessionConfig {
  prompts_per_player: number;
  copies_per_player: number;
  votes_per_player: number;
  min_players: number;
  max_players: number;
}

interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;

  // Session configuration (set once at start, doesn't change)
  sessionConfig: SessionConfig | null;

  // Player's individual progress (updated on each submission)
  yourProgress: {
    prompts_submitted: number;
    copies_submitted: number;
    votes_submitted: number;
  } | null;

  // Overall session progress (updated via API responses or WebSocket)
  sessionProgress: {
    players_ready_for_next_phase: number;
    total_players: number;
  } | null;
}

interface PartyModeActions {
  startPartyMode: (sessionId: string, initialStep?: PartyStep, config?: SessionConfig) => void;
  endPartyMode: () => void;
  setCurrentStep: (step: PartyStep) => void;

  // Update progress from API responses
  updateYourProgress: (progress: PartyModeState['yourProgress']) => void;
  updateSessionProgress: (progress: PartyModeState['sessionProgress']) => void;
  updateFromPartyContext: (context: PartyContext) => void;
}

interface PartyModeContextValue {
  state: PartyModeState;
  actions: PartyModeActions;
}

const STORAGE_KEY = 'partyModeState';

const defaultState: PartyModeState = {
  isPartyMode: false,
  sessionId: null,
  currentStep: null,
  sessionConfig: null,
  yourProgress: null,
  sessionProgress: null,
};

const PartyModeContext = createContext<PartyModeContextValue | undefined>(undefined);

const loadInitialState = (): PartyModeState => {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored) as PartyModeState;
      return parsed;
    }
  } catch (err) {
    console.warn('Failed to load party mode state from storage', err);
  }
  return defaultState;
};

const persistState = (state: PartyModeState) => {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (err) {
    console.warn('Failed to persist party mode state', err);
  }
};

export const PartyModeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [state, setState] = useState<PartyModeState>(() => loadInitialState());

  const startPartyMode = useCallback((sessionId: string, initialStep: PartyStep = 'prompt', config?: SessionConfig) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        isPartyMode: true,
        sessionId,
        currentStep: initialStep,
        sessionConfig: config || prev.sessionConfig,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const endPartyMode = useCallback(() => {
    setState(defaultState);
    persistState(defaultState);
  }, []);

  const setCurrentStep = useCallback((step: PartyStep) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        isPartyMode: true,
        currentStep: step,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const updateYourProgress = useCallback((progress: PartyModeState['yourProgress']) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        yourProgress: progress,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const updateSessionProgress = useCallback((progress: PartyModeState['sessionProgress']) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        sessionProgress: progress,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const updateFromPartyContext = useCallback((context: PartyContext) => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        yourProgress: {
          prompts_submitted: context.your_progress.prompts_submitted,
          copies_submitted: context.your_progress.copies_submitted,
          votes_submitted: context.your_progress.votes_submitted,
        },
        sessionProgress: context.session_progress,
      };
      persistState(nextState);
      return nextState;
    });
  }, []);

  const value = useMemo<PartyModeContextValue>(() => ({
    state,
    actions: {
      startPartyMode,
      endPartyMode,
      setCurrentStep,
      updateYourProgress,
      updateSessionProgress,
      updateFromPartyContext,
    },
  }), [state, startPartyMode, endPartyMode, setCurrentStep, updateYourProgress, updateSessionProgress, updateFromPartyContext]);

  return (
    <PartyModeContext.Provider value={value}>
      {children}
    </PartyModeContext.Provider>
  );
};

export const usePartyMode = (): PartyModeContextValue => {
  const context = useContext(PartyModeContext);
  if (!context) {
    throw new Error('usePartyMode must be used within a PartyModeProvider');
  }
  return context;
};

/**
 * Check if currently in party mode (convenience hook).
 */
export const useIsInPartyMode = (): boolean => {
  const { state } = usePartyMode();
  return state.isPartyMode;
};

/**
 * Get current party session ID (or null if not in party mode).
 */
export const usePartySessionId = (): string | null => {
  const { state } = usePartyMode();
  return state.sessionId;
};

/**
 * Get current party step (or null if not in party mode).
 */
export const usePartyStep = (): PartyStep | null => {
  const { state } = usePartyMode();
  return state.currentStep;
};
