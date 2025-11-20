/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';

export type PartyStep = 'prompt' | 'copy' | 'vote';

interface PartyModeState {
  isPartyMode: boolean;
  sessionId: string | null;
  currentStep: PartyStep | null;
}

interface PartyModeActions {
  startPartyMode: (sessionId: string, initialStep?: PartyStep) => void;
  endPartyMode: () => void;
  setCurrentStep: (step: PartyStep) => void;
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

  const startPartyMode = useCallback((sessionId: string, initialStep: PartyStep = 'prompt') => {
    setState((prev) => {
      const nextState: PartyModeState = {
        ...prev,
        isPartyMode: true,
        sessionId,
        currentStep: initialStep,
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

  const value = useMemo<PartyModeContextValue>(() => ({
    state,
    actions: {
      startPartyMode,
      endPartyMode,
      setCurrentStep,
    },
  }), [state, startPartyMode, endPartyMode, setCurrentStep]);

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
