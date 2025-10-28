import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useSmartPolling, PollConfigs } from '../utils/smartPolling';
import { getActionErrorMessage } from '../utils/errorMessages';
import { gameContextLogger } from '../utils/logger';
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
    gameContextLogger.debug('Initializing session...');
    const initializeSession = async () => {
      const storedUsername = apiClient.getStoredUsername();
      gameContextLogger.debug('Stored username:', storedUsername);
      if (storedUsername) {
        setUsername(storedUsername);
      }
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Access token check result:', { hasToken: !!token });
      setIsAuthenticated(Boolean(token));
    };
    initializeSession();
  }, []);

  // Monitor authentication state changes
  useEffect(() => {
    gameContextLogger.debug('Authentication state changed:', { isAuthenticated, username });
  }, [isAuthenticated, username]);

  // Create stable actions object using useCallback for all methods
  const startSession = useCallback((nextUsername: string, tokens: AuthTokenResponse) => {
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
  }, []);

  const logout = useCallback(async () => {
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
  }, [stopPoll]);

  const refreshDashboard = useCallback(async (signal?: AbortSignal) => {
      gameContextLogger.debug('refreshDashboard called');
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for dashboard refresh:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('No valid token, skipping dashboard refresh');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('Making dashboard API call...');
        const data = await apiClient.getDashboardData(signal);
        gameContextLogger.debug('✅ Dashboard data received successfully');
        gameContextLogger.debug('Current round from API:', {
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
        
        // Handle active round properly - if it's submitted, expired, or abandoned, clear it
        if (data.current_round) {
          const roundState = data.current_round.state;
          const roundStatus = roundState?.status;

          // Only show active rounds; clear completed/expired/abandoned rounds
          if (roundStatus === 'active') {
            gameContextLogger.debug('Setting active round:', data.current_round);
            setActiveRound(data.current_round);
          } else {
            gameContextLogger.debug(`Round status is ${roundStatus}, clearing active round`);
            setActiveRound(null);
          }
        } else {
          gameContextLogger.debug('No current round from API, clearing active round');
          setActiveRound(null);
        }
        
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;

        gameContextLogger.error('Dashboard refresh failed:', err);
        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        // Handle auth errors
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          gameContextLogger.warn('Auth error detected, logging out');
          logout();
        }
      }
  }, [isAuthenticated, username]);

  const refreshBalance = useCallback(async (signal?: AbortSignal) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

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
          logout();
        }
      }
  }, [isAuthenticated, username]);

  const claimBonus = useCallback(async () => {
      console.log('🎯 GameContext claimBonus called');
      
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      console.log('🔍 Token check for claim bonus:', { hasToken: !!token });
      
      if (!token) {
        console.log('❌ No valid token, aborting claim bonus');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        console.log('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        console.log('🔄 Setting loading to true');
        setLoading(true);
        console.log('📞 Calling apiClient.claimDailyBonus()...');
        await apiClient.claimDailyBonus();
        console.log('✅ API call successful');
        
        // Trigger immediate dashboard refresh
        console.log('🔄 Triggering dashboard refresh');
        triggerPoll('dashboard');
        
        setError(null);
        console.log('✅ Claim bonus completed successfully');
      } catch (err) {
        console.error('❌ Claim bonus API call failed:', err);
        const message = getActionErrorMessage('claim-bonus', err);
        console.log('📝 Error message:', message);
        setError(message);

        // Handle auth errors
        if (message.toLowerCase().includes('session') || message.toLowerCase().includes('login')) {
          console.log('🚪 Auth error detected, logging out');
          logout();
        }

        throw err;
      } finally {
        console.log('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, logout]);

  const clearError = useCallback(() => {
      setError(null);
  }, []);

  const navigateAfterDelay = useCallback((path: string, delay: number = 1500) => {
      setTimeout(() => navigate(path), delay);
  }, [navigate]);

  const startPromptRound = useCallback(async () => {
      gameContextLogger.info('startPromptRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for prompt round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting prompt round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting prompt round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        outstandingPrompts: player?.outstanding_prompts
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startPromptRound()...');
        const response = await apiClient.startPromptRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
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
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        // Trigger immediate dashboard refresh to update availability
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Prompt round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start prompt round:', err);
        const errorMessage = getActionErrorMessage('start-prompt', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, player?.outstanding_prompts, triggerPoll]);

  const startCopyRound = useCallback(async () => {
      gameContextLogger.info('startCopyRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for copy round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting copy round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting copy round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        promptsWaiting: roundAvailability?.prompts_waiting,
        copyCost: roundAvailability?.copy_cost
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startCopyRound()...');
        const response = await apiClient.startCopyRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
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
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Copy round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start copy round:', err);
        const errorMessage = getActionErrorMessage('start-copy', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, triggerPoll]);

  const startVoteRound = useCallback(async () => {
      gameContextLogger.info('startVoteRound called');

      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('Token check for vote round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('No valid token, aborting vote round start');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      gameContextLogger.debug('Starting vote round API call...');
      gameContextLogger.debug('Current round availability:', roundAvailability);
      gameContextLogger.debug('Current player state:', {
        balance: player?.balance,
        phrasesetsWaiting: roundAvailability?.phrasesets_waiting
      });

      try {
        setLoading(true);
        setError(null);
        gameContextLogger.debug('Calling apiClient.startVoteRound()...');
        const response = await apiClient.startVoteRound();
        gameContextLogger.info('✅ API call successful, response:', response);
        
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
        
        gameContextLogger.debug('Setting active round:', newActiveRound);
        setActiveRound(newActiveRound);
        
        gameContextLogger.debug('Triggering dashboard refresh...');
        triggerPoll('dashboard');

        gameContextLogger.info('✅ Vote round started successfully');
      } catch (err) {
        gameContextLogger.error('Failed to start vote round:', err);
        const errorMessage = getActionErrorMessage('start-vote', err);
        gameContextLogger.debug('Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        setLoading(false);
      }
  }, [isAuthenticated, roundAvailability, player?.balance, triggerPoll]);

  const getPhrasesetResults = useCallback(async (phrasesetId: string) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return null;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getPhrasesetResults(phrasesetId);
        return data;
      } catch (err) {
        // Handle specific API errors more gracefully
        const errorStr = String(err);
        
        // If it's a "not found" error for copy rounds, return null instead of throwing
        if (errorStr.includes('Copy round') && errorStr.includes('not found')) {
          gameContextLogger.warn(`Phraseset ${phrasesetId} not ready for results viewing:`, errorStr);
          return null;
        }
        
        // If it's a 404 or phraseset not found, return null
        if (errorStr.includes('404') || errorStr.includes('not found') || errorStr.includes('Phraseset not found')) {
          gameContextLogger.warn(`Phraseset ${phrasesetId} not found:`, errorStr);
          return null;
        }
        
        // For other errors, still throw but with better logging
        gameContextLogger.error(`Error fetching results for phraseset ${phrasesetId}:`, err);
        const errorMessage = getActionErrorMessage('load-results', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated]);

  const getPlayerPhrasesets = useCallback(async (params: any) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return { phrasesets: [], total: 0, has_more: false };
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getPlayerPhrasesets(params);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-tracking', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated]);

  const getPhrasesetDetails = useCallback(async (phrasesetId: string) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return null;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getPhrasesetDetails(phrasesetId);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-details', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated]);

  const claimPhrasesetPrize = useCallback(async (phrasesetId: string) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

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
  }, [isAuthenticated, triggerPoll]);

  const getStatistics = useCallback(async (signal?: AbortSignal) => {
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      if (!token) {
        setIsAuthenticated(false);
        return null;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getStatistics(signal);
        return data;
      } catch (err) {
        const errorMessage = getActionErrorMessage('load-statistics', err);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated]);

  // Set up smart polling when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      stopPoll('dashboard');
      stopPoll('balance');
      return;
    }

    // Start dashboard polling with smart intervals
    startPoll(PollConfigs.DASHBOARD, async () => {
      await refreshDashboard();
    });

    // Start balance polling with longer intervals
    startPoll(PollConfigs.BALANCE_REFRESH, async () => {
      await refreshBalance();
    });

    // Cleanup function
    return () => {
      stopPoll('dashboard');
      stopPoll('balance');
    };
  }, [isAuthenticated, startPoll, stopPoll, refreshDashboard, refreshBalance]);

  // Initial dashboard load - only once when authenticated changes
  const hasInitialLoadRef = useRef(false);
  useEffect(() => {
    if (!isAuthenticated) {
      hasInitialLoadRef.current = false;
      return;
    }

    // Prevent duplicate loads in React StrictMode
    if (hasInitialLoadRef.current) return;
    hasInitialLoadRef.current = true;

    const controller = new AbortController();
    refreshDashboard(controller.signal);

    return () => controller.abort();
  }, [isAuthenticated, refreshDashboard]);

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

  const actions: GameActions = {
    startSession,
    logout,
    refreshDashboard,
    refreshBalance,
    claimBonus,
    clearError,
    navigateAfterDelay,
    startPromptRound,
    startCopyRound,
    startVoteRound,
    getPhrasesetResults,
    getPlayerPhrasesets,
    getPhrasesetDetails,
    claimPhrasesetPrize,
    getStatistics,
  };

  const value: GameContextType = {
    state,
    actions,
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
