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

// Debug logging helper
const log = (component: string, message: string, data?: any) => {
  if (import.meta.env.DEV) {
    console.log(`[${component}] ${message}`, data || '');
  }
};

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
    log('GameContext', 'Initializing session...');
    const initializeSession = async () => {
      const storedUsername = apiClient.getStoredUsername();
      log('GameContext', 'Stored username:', storedUsername);
      if (storedUsername) {
        setUsername(storedUsername);
      }
      const token = await apiClient.ensureAccessToken();
      log('GameContext', 'Access token check result:', { hasToken: !!token });
      setIsAuthenticated(Boolean(token));
    };
    initializeSession();
  }, []);

  // Monitor authentication state changes
  useEffect(() => {
    log('GameContext', 'Authentication state changed:', { isAuthenticated, username });
  }, [isAuthenticated, username]);

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
      log('GameContext', 'refreshDashboard called');
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      log('GameContext', 'Token check for dashboard refresh:', { hasToken: !!token });
      
      if (!token) {
        log('GameContext', '❌ No valid token, skipping dashboard refresh');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        log('GameContext', 'Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        log('GameContext', 'Making dashboard API call...');
        const data = await apiClient.getDashboardData(signal);
        log('GameContext', '✅ Dashboard data received successfully');
        log('GameContext', 'Current round from API:', {
          currentRound: data.current_round ? {
            id: data.current_round.round_id,
            type: data.current_round.round_type,
            status: data.current_round.state?.status
          } : 'null'
        });

        // Update all dashboard state at once
        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }
        
        // Handle active round properly - if it's submitted or expired, clear it
        if (data.current_round) {
          const roundState = data.current_round.state;
          if (roundState?.status === 'submitted' || roundState?.status === 'expired') {
            log('GameContext', 'Round is completed, clearing active round');
            setActiveRound(null);
          } else {
            log('GameContext', 'Setting active round:', data.current_round);
            setActiveRound(data.current_round);
          }
        } else {
          log('GameContext', 'No current round from API, clearing active round');
          setActiveRound(null);
        }
        
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        log('GameContext', '❌ Dashboard refresh failed:', err);
        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        // Handle auth errors
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          log('GameContext', 'Auth error detected, logging out');
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
      log('GameContext', 'startPromptRound called');
      
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      log('GameContext', 'Token check for prompt round:', { hasToken: !!token });
      
      if (!token) {
        log('GameContext', '❌ No valid token, aborting prompt round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        log('GameContext', 'Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      log('GameContext', 'Starting prompt round API call...');
      log('GameContext', 'Current round availability:', roundAvailability);
      log('GameContext', 'Current player state:', { 
        balance: player?.balance, 
        outstandingPrompts: player?.outstanding_prompts 
      });

      try {
        setError(null);
        log('GameContext', 'Calling apiClient.startPromptRound()...');
        const response = await apiClient.startPromptRound();
        log('GameContext', '✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'prompt' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            prompt_text: response.prompt_text,
            expires_at: response.expires_at,
            cost: response.cost,
            status: 'active' as const,
          },
        };
        
        log('GameContext', 'Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        // Trigger immediate dashboard refresh to update availability
        log('GameContext', 'Triggering dashboard refresh...');
        triggerPoll('dashboard');
        
        log('GameContext', '✅ Prompt round started successfully');
      } catch (err) {
        log('GameContext', '❌ Failed to start prompt round:', err);
        const errorMessage = getActionErrorMessage('start-prompt', err);
        log('GameContext', 'Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      }
    },

    startCopyRound: async () => {
      log('GameContext', 'startCopyRound called');
      
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      log('GameContext', 'Token check for copy round:', { hasToken: !!token });
      
      if (!token) {
        log('GameContext', '❌ No valid token, aborting copy round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        log('GameContext', 'Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      log('GameContext', 'Starting copy round API call...');
      log('GameContext', 'Current round availability:', roundAvailability);
      log('GameContext', 'Current player state:', { 
        balance: player?.balance,
        promptsWaiting: roundAvailability?.prompts_waiting,
        copyCost: roundAvailability?.copy_cost
      });

      try {
        setError(null);
        log('GameContext', 'Calling apiClient.startCopyRound()...');
        const response = await apiClient.startCopyRound();
        log('GameContext', '✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'copy' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            original_phrase: response.original_phrase,
            expires_at: response.expires_at,
            cost: response.cost,
            discount_active: response.discount_active,
            status: 'active' as const,
          },
        };
        
        log('GameContext', 'Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        log('GameContext', 'Triggering dashboard refresh...');
        triggerPoll('dashboard');
        
        log('GameContext', '✅ Copy round started successfully');
      } catch (err) {
        log('GameContext', '❌ Failed to start copy round:', err);
        const errorMessage = getActionErrorMessage('start-copy', err);
        log('GameContext', 'Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      }
    },

    startVoteRound: async () => {
      log('GameContext', 'startVoteRound called');
      
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      log('GameContext', 'Token check for vote round:', { hasToken: !!token });
      
      if (!token) {
        log('GameContext', '❌ No valid token, aborting vote round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        log('GameContext', 'Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      log('GameContext', 'Starting vote round API call...');
      log('GameContext', 'Current round availability:', roundAvailability);
      log('GameContext', 'Current player state:', { 
        balance: player?.balance,
        phrasesetsWaiting: roundAvailability?.phrasesets_waiting
      });

      try {
        setError(null);
        log('GameContext', 'Calling apiClient.startVoteRound()...');
        const response = await apiClient.startVoteRound();
        log('GameContext', '✅ API call successful, response:', response);
        
        const newActiveRound = {
          round_type: 'vote' as const,
          round_id: response.round_id,
          expires_at: response.expires_at,
          state: {
            round_id: response.round_id,
            phraseset_id: response.phraseset_id,
            prompt_text: response.prompt_text,
            phrases: response.phrases,
            expires_at: response.expires_at,
            status: 'active' as const,
          },
        };
        
        log('GameContext', 'Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        log('GameContext', 'Triggering dashboard refresh...');
        triggerPoll('dashboard');
        
        log('GameContext', '✅ Vote round started successfully');
      } catch (err) {
        log('GameContext', '❌ Failed to start vote round:', err);
        const errorMessage = getActionErrorMessage('start-vote', err);
        log('GameContext', 'Setting error message:', errorMessage);
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
