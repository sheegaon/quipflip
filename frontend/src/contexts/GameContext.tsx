import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import type {
  Player,
  ActiveRound,
  PendingResult,
  RoundAvailability,
  PhrasesetDashboardSummary,
  UnclaimedResult,
  AuthTokenResponse,
} from '../api/types';

interface GameState {
  isAuthenticated: boolean;
  username: string | null;
  player: Player | null;
  activeRound: ActiveRound | null;
  pendingResults: PendingResult[];
  phrasesetSummary: PhrasesetDashboardSummary | null;
  unclaimedResults: UnclaimedResult[];
  roundAvailability: RoundAvailability | null;
  loading: boolean;
  error: string | null;
}

interface GameActions {
  startSession: (username: string, tokens: AuthTokenResponse) => void;
  logout: () => Promise<void>;
  refreshDashboard: () => Promise<void>;
  refreshBalance: () => Promise<void>;
  claimBonus: () => Promise<void>;
  clearError: () => void;
  navigateAfterDelay: (path: string, delay?: number) => void;
}

interface GameContextType {
  state: GameState;
  actions: GameActions;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // State
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [username, setUsername] = useState<string | null>(null);
  const [player, setPlayer] = useState<Player | null>(null);
  const [activeRound, setActiveRound] = useState<ActiveRound | null>(null);
  const [pendingResults, setPendingResults] = useState<PendingResult[]>([]);
  const [phrasesetSummary, setPhrasesetSummary] = useState<PhrasesetDashboardSummary | null>(null);
  const [unclaimedResults, setUnclaimedResults] = useState<UnclaimedResult[]>([]);
  const [roundAvailability, setRoundAvailability] = useState<RoundAvailability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Navigation ref (will be set by navigation wrapper)
  const navigateRef = useRef<((path: string) => void) | null>(null);

  // Initialize session on mount
  useEffect(() => {
    const initializeSession = async () => {
      const storedUsername = apiClient.getStoredUsername();
      if (storedUsername) {
        setUsername(storedUsername);
      }
      const token = await apiClient.ensureAccessToken();
      setIsAuthenticated(Boolean(token));
    };
    initializeSession();
  }, []);

  // Create stable actions object using ref
  const actionsRef = useRef<GameActions>({
    startSession: (nextUsername: string, tokens: AuthTokenResponse) => {
      apiClient.setSession(nextUsername, tokens);
      setUsername(nextUsername);
      setIsAuthenticated(true);
    },

    logout: async () => {
      try {
        await apiClient.logout();
      } catch (err) {
        console.warn('Failed to logout cleanly', err);
      } finally {
        apiClient.clearSession();
        setIsAuthenticated(false);
        setUsername(null);
        setPlayer(null);
        setActiveRound(null);
        setPendingResults([]);
        setPhrasesetSummary(null);
        setUnclaimedResults([]);
        setRoundAvailability(null);
      }
    },

    refreshDashboard: async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;

      try {
        const data = await apiClient.getDashboardData(signal);

        // Update all dashboard state at once
        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }
        setActiveRound(data.current_round);
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to load dashboard data. Please refresh the page.');

        // Handle auth errors
        if (errorMessage) {
          const normalized = errorMessage.toLowerCase();
          if (
            normalized.includes('unauthorized') ||
            normalized.includes('token') ||
            normalized.includes('credentials')
          ) {
            actionsRef.current.logout();
          }
        }
      }
    },

    refreshBalance: async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;

      try {
        const data = await apiClient.getBalance(signal);
        setPlayer(data);
        if (data.username && data.username !== username) {
          apiClient.setSession(data.username);
          setUsername(data.username);
        }
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to update your balance. Please refresh the page.');

        // Handle auth errors
        if (errorMessage) {
          const normalized = errorMessage.toLowerCase();
          if (
            normalized.includes('unauthorized') ||
            normalized.includes('token') ||
            normalized.includes('credentials')
          ) {
            actionsRef.current.logout();
          }
        }
      }
    },

    claimBonus: async () => {
      if (!isAuthenticated) return;

      try {
        setLoading(true);
        await apiClient.claimDailyBonus();
        await actionsRef.current.refreshDashboard();
        setError(null);
      } catch (err) {
        const message = extractErrorMessage(err) || 'Unable to claim your daily bonus right now. You may have already claimed it today, or there may be a temporary issue.';
        setError(message);

        // Handle auth errors
        const normalized = message.toLowerCase();
        if (
          normalized.includes('unauthorized') ||
          normalized.includes('token') ||
          normalized.includes('credentials')
        ) {
          actionsRef.current.logout();
        }

        throw err;
      } finally {
        setLoading(false);
      }
    },

    clearError: () => {
      setError(null);
    },

    navigateAfterDelay: (path: string, delay: number = 1500) => {
      if (navigateRef.current) {
        setTimeout(() => navigateRef.current?.(path), delay);
      }
    },
  });

  // Update actions ref closures when dependencies change
  useEffect(() => {
    actionsRef.current.refreshDashboard = async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;

      try {
        const data = await apiClient.getDashboardData(signal);

        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }
        setActiveRound(data.current_round);
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to load dashboard data. Please refresh the page.');

        if (errorMessage) {
          const normalized = errorMessage.toLowerCase();
          if (
            normalized.includes('unauthorized') ||
            normalized.includes('token') ||
            normalized.includes('credentials')
          ) {
            actionsRef.current.logout();
          }
        }
      }
    };

    actionsRef.current.refreshBalance = async (signal?: AbortSignal) => {
      if (!isAuthenticated) return;

      try {
        const data = await apiClient.getBalance(signal);
        setPlayer(data);
        if (data.username && data.username !== username) {
          apiClient.setSession(data.username);
          setUsername(data.username);
        }
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        const errorMessage = extractErrorMessage(err);
        setError(errorMessage || 'Unable to update your balance. Please refresh the page.');

        if (errorMessage) {
          const normalized = errorMessage.toLowerCase();
          if (
            normalized.includes('unauthorized') ||
            normalized.includes('token') ||
            normalized.includes('credentials')
          ) {
            actionsRef.current.logout();
          }
        }
      }
    };

    actionsRef.current.claimBonus = async () => {
      if (!isAuthenticated) return;

      try {
        setLoading(true);
        await apiClient.claimDailyBonus();
        await actionsRef.current.refreshDashboard();
        setError(null);
      } catch (err) {
        const message = extractErrorMessage(err) || 'Unable to claim your daily bonus right now. You may have already claimed it today, or there may be a temporary issue.';
        setError(message);

        const normalized = message.toLowerCase();
        if (
          normalized.includes('unauthorized') ||
          normalized.includes('token') ||
          normalized.includes('credentials')
        ) {
          actionsRef.current.logout();
        }

        throw err;
      } finally {
        setLoading(false);
      }
    };
  }, [isAuthenticated, username]);

  // Initial dashboard load
  useEffect(() => {
    if (!isAuthenticated) return;

    const controller = new AbortController();
    actionsRef.current.refreshDashboard(controller.signal);

    return () => controller.abort();
  }, [isAuthenticated]);

  // Dashboard polling interval
  useEffect(() => {
    if (!isAuthenticated) return;

    const dashboardInterval = setInterval(() => {
      actionsRef.current.refreshDashboard();
    }, 60_000);

    return () => {
      clearInterval(dashboardInterval);
    };
  }, [isAuthenticated]);

  const state: GameState = {
    isAuthenticated,
    username,
    player,
    activeRound,
    pendingResults,
    phrasesetSummary,
    unclaimedResults,
    roundAvailability,
    loading,
    error,
  };

  const value: GameContextType = {
    state,
    actions: actionsRef.current,
  };

  return <GameContext.Provider value={value}>{children}</GameContext.Provider>;
};

// Navigation wrapper component to inject navigate function
export const GameProviderWithNavigation: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const navigate = useNavigate();
  const contextValue = useContext(GameContext);

  useEffect(() => {
    if (contextValue) {
      const actionsRef = (contextValue.actions as any).__navigateRef;
      if (actionsRef) {
        actionsRef.current = navigate;
      }
    }
  }, [navigate, contextValue]);

  return <>{children}</>;
};

export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};

// Legacy compatibility exports (to be removed after migration)
export const useLegacyGame = () => {
  const { state, actions } = useGame();
  return {
    ...state,
    ...actions,
  };
};
