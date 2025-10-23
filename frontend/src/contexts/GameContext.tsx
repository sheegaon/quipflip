import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useSmartPolling, PollConfigs } from '../utils/smartPolling';
import { getActionErrorMessage } from '../utils/errorMessages';
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
  refreshDashboard: (signal?: AbortSignal) => Promise<void>;
  refreshBalance: (signal?: AbortSignal) => Promise<void>;
  claimBonus: () => Promise<void>;
  clearError: () => void;
  navigateAfterDelay: (path: string, delay?: number) => void;
  startPromptRound: () => Promise<void>;
  startCopyRound: () => Promise<void>;
  startVoteRound: () => Promise<void>;
  getPhrasesetResults: (phrasesetId: string) => Promise<any>;
  getPlayerPhrasesets: (params: any) => Promise<any>;
  getPhrasesetDetails: (phrasesetId: string) => Promise<any>;
  claimPhrasesetPrize: (phrasesetId: string) => Promise<void>;
  getStatistics: (signal?: AbortSignal) => Promise<any>;
}

interface GameContextType {
  state: GameState;
  actions: GameActions;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Navigation hook - use directly since we're inside Router
  const navigate = useNavigate();
  
  // Smart polling hook
  const { startPoll, stopPoll, triggerPoll } = useSmartPolling();
  
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
      
      // Immediately load dashboard data after successful login
      setTimeout(async () => {
        try {
          const data = await apiClient.getDashboardData();
          setPlayer(data.player);
          setActiveRound(data.current_round);
          setPendingResults(data.pending_results);
          setPhrasesetSummary(data.phraseset_summary);
          setUnclaimedResults(data.unclaimed_results);
          setRoundAvailability(data.round_availability);
          setError(null);
        } catch (err) {
          console.error('Failed to load dashboard after login:', err);
          const errorMessage = getActionErrorMessage('load-dashboard', err);
          setError(errorMessage);
        }
      }, 100);
    },

    logout: async () => {
      try {
        await apiClient.logout();
      } catch (err) {
        console.warn('Failed to logout cleanly', err);
      } finally {
        // Stop all polling
        stopPoll('dashboard');
        stopPoll('balance');
        
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
      // Use the current state value, not the closure value
      const currentIsAuthenticated = isAuthenticated;
      if (!currentIsAuthenticated) return;

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

        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        // Handle auth errors
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          actionsRef.current.logout();
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

        const errorMessage = getActionErrorMessage('refresh-balance', err);
        
        // Only show balance refresh errors if they're auth-related
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          setError(errorMessage);
          actionsRef.current.logout();
        }
      }
    },

    claimBonus: async () => {
      if (!isAuthenticated) return;

      try {
        setLoading(true);
        await apiClient.claimDailyBonus();
        
        // Trigger immediate dashboard refresh
        triggerPoll('dashboard');
        
        setError(null);
      } catch (err) {
        const message = getActionErrorMessage('claim-bonus', err);
        setError(message);

        // Handle auth errors
        if (message.toLowerCase().includes('session') || message.toLowerCase().includes('login')) {
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
      setTimeout(() => navigate(path), delay);
    },

    startPromptRound: async () => {
      if (!isAuthenticated) return;

      try {
        setError(null);
        const response = await apiClient.startPromptRound();
        setActiveRound({
          round_type: 'prompt',
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            prompt_text: response.prompt_text,
            expires_at: response.expires_at,
            cost: response.cost,
            status: 'active',
          },
        });
        
        // Trigger immediate dashboard refresh to update availability
        triggerPoll('dashboard');
      } catch (err) {
        const errorMessage = getActionErrorMessage('start-prompt', err);
        setError(errorMessage);
        throw err;
      }
    },

    startCopyRound: async () => {
      if (!isAuthenticated) return;

      try {
        setError(null);
        const response = await apiClient.startCopyRound();
        setActiveRound({
          round_type: 'copy',
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            original_phrase: response.original_phrase,
            expires_at: response.expires_at,
            cost: response.cost,
            discount_active: response.discount_active,
            status: 'active',
          },
        });
        
        triggerPoll('dashboard');
      } catch (err) {
        const errorMessage = getActionErrorMessage('start-copy', err);
        setError(errorMessage);
        throw err;
      }
    },

    startVoteRound: async () => {
      if (!isAuthenticated) return;

      try {
        setError(null);
        const response = await apiClient.startVoteRound();
        setActiveRound({
          round_type: 'vote',
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            phraseset_id: response.phraseset_id,
            prompt_text: response.prompt_text,
            phrases: response.phrases,
            expires_at: response.expires_at,
            status: 'active',
          },
        });
        
        triggerPoll('dashboard');
      } catch (err) {
        const errorMessage = getActionErrorMessage('start-vote', err);
        setError(errorMessage);
        throw err;
      }
    },

    getPhrasesetResults: async (phrasesetId: string) => {
      if (!isAuthenticated) return null;

      try {
        const data = await apiClient.getPhrasesetResults(phrasesetId);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-results', err);
        setError(errorMessage);
        throw err;
      }
    },

    getPlayerPhrasesets: async (params: any) => {
      if (!isAuthenticated) return { phrasesets: [], total: 0, has_more: false };

      try {
        const data = await apiClient.getPlayerPhrasesets(params);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-tracking', err);
        setError(errorMessage);
        throw err;
      }
    },

    getPhrasesetDetails: async (phrasesetId: string) => {
      if (!isAuthenticated) return null;

      try {
        const data = await apiClient.getPhrasesetDetails(phrasesetId);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-details', err);
        setError(errorMessage);
        throw err;
      }
    },

    claimPhrasesetPrize: async (phrasesetId: string) => {
      if (!isAuthenticated) return;

      try {
        await apiClient.claimPhrasesetPrize(phrasesetId);
        
        // Trigger immediate dashboard refresh to update balance
        triggerPoll('dashboard');
        
        setError(null);
      } catch (err) {
        const errorMessage = getActionErrorMessage('claim-prize', err);
        setError(errorMessage);
        throw err;
      }
    },

    getStatistics: async (signal?: AbortSignal) => {
      if (!isAuthenticated) return null;

      try {
        const data = await apiClient.getStatistics(signal);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-statistics', err);
        setError(errorMessage);
        throw err;
      }
    },
  });

  // Set up smart polling when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      stopPoll('dashboard');
      stopPoll('balance');
      return;
    }

    // Start dashboard polling with smart intervals
    startPoll(PollConfigs.DASHBOARD, async () => {
      await actionsRef.current.refreshDashboard();
    });

    // Start balance polling with longer intervals
    startPoll(PollConfigs.BALANCE_REFRESH, async () => {
      await actionsRef.current.refreshBalance();
    });

    // Cleanup function
    return () => {
      stopPoll('dashboard');
      stopPoll('balance');
    };
  }, [isAuthenticated, startPoll, stopPoll]);

  // Initial dashboard load
  useEffect(() => {
    if (!isAuthenticated) return;

    const controller = new AbortController();
    actionsRef.current.refreshDashboard(controller.signal);

    return () => controller.abort();
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

// Main hook - returns structured API
export const useGame = (): GameContextType => {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
};
