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
  FlagCopyRoundResponse,
  AbandonRoundResponse,
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
  claimPhrasesetPrize: (phrasesetId: string) => Promise<void>;
  flagCopyRound: (roundId: string) => Promise<FlagCopyRoundResponse>;
  abandonRound: (roundId: string) => Promise<AbandonRoundResponse>;
}

interface GameContextType {
  state: GameState;
  actions: GameActions;
}

const GameContext = createContext<GameContextType | undefined>(undefined);

export const GameProvider: React.FC<{ 
  children: React.ReactNode;
  onPendingResultsChange?: (results: PendingResult[]) => void;
  onDashboardTrigger?: () => void;
}> = ({ children, onPendingResultsChange, onDashboardTrigger }) => {
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

  // Notify other contexts when pending results change
  useEffect(() => {
    if (onPendingResultsChange) {
      onPendingResultsChange(pendingResults);
    }
  }, [pendingResults, onPendingResultsChange]);

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

  // Monitor authentication state changes
  useEffect(() => {
    if (isAuthenticated && username) {
      gameContextLogger.debug('User authenticated', { username });
    }
  }, [isAuthenticated, username]);

  // Create stable actions object using useCallback for all methods
  const startSession = useCallback((nextUsername: string, tokens: AuthTokenResponse) => {
      gameContextLogger.debug('🎯 GameContext startSession called:', { username: nextUsername });
      
      apiClient.setSession(nextUsername, tokens);
      setUsername(nextUsername);
      setIsAuthenticated(true);
      
      // Remove the delayed dashboard load - let the initial dashboard load effect handle it
      gameContextLogger.debug('✅ Session started, authentication state will trigger dashboard load');
  }, []);

  const logout = useCallback(async () => {
      gameContextLogger.debug('🚪 GameContext logout called');
      
      try {
        await apiClient.logout();
      } catch (err) {
        gameContextLogger.warn('⚠️ Failed to logout cleanly:', err);
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
        setLoading(false);
        setError(null);
      }
  }, [stopPoll]);

  const refreshDashboard = useCallback(async (signal?: AbortSignal) => {
      // Check token directly instead of relying on state
      const token = await apiClient.ensureAccessToken();
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, skipping dashboard refresh');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        setIsAuthenticated(true);
      }

      try {
        const data = await apiClient.getDashboardData(signal);
        gameContextLogger.debug('✅ Dashboard data received successfully:', {
          playerBalance: data.player?.balance,
          currentRound: data.current_round ? {
            id: data.current_round.round_id,
            type: data.current_round.round_type,
            status: data.current_round.state?.status
          } : 'null',
          pendingResultsCount: data.pending_results?.length || 0,
          unclaimedResultsCount: data.unclaimed_results?.length || 0
        });

        // Update all dashboard state at once
        setPlayer(data.player);
        if (data.player.username && data.player.username !== username) {
          gameContextLogger.debug('👤 Username mismatch, updating session:', {
            stored: username,
            received: data.player.username
          });
          apiClient.setSession(data.player.username);
          setUsername(data.player.username);
        }

        // Handle active round properly - if it's submitted, expired, or abandoned, clear it
        if (data.current_round) {
          const roundState = data.current_round.state;
          const roundStatus = roundState?.status;

          // Only show active rounds; clear completed/expired/abandoned rounds
          if (roundStatus === 'active') {
            gameContextLogger.debug('✅ Setting active round:', {
              roundId: data.current_round.round_id,
              roundType: data.current_round.round_type,
              status: roundStatus
            });
            setActiveRound(data.current_round);
          } else {
            gameContextLogger.debug(`🚫 Round status is ${roundStatus}, clearing active round`);
            setActiveRound(null);
          }
        } else {
          gameContextLogger.debug('⭕ No current round from API, clearing active round');
          setActiveRound(null);
        }
        
        setPendingResults(data.pending_results);
        setPhrasesetSummary(data.phraseset_summary);
        setUnclaimedResults(data.unclaimed_results);
        setRoundAvailability(data.round_availability);
        setError(null);
        
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') {
          return;
        }

        gameContextLogger.error('❌ Dashboard refresh failed:', err);
        const errorMessage = getActionErrorMessage('load-dashboard', err);
        setError(errorMessage);

        // Handle auth errors
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          gameContextLogger.warn('🚪 Auth error detected, logging out');
          logout();
        }
      }
  }, [isAuthenticated, username, logout]);

  const refreshBalance = useCallback(async (signal?: AbortSignal) => {
      gameContextLogger.debug('💰 GameContext refreshBalance called');
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for balance refresh:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token for balance refresh');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('📞 Calling apiClient.getBalance...');
        const data = await apiClient.getBalance(signal);
        gameContextLogger.debug('✅ Balance data received:', {
          balance: data.balance,
          username: data.username
        });
        
        setPlayer(data);
        if (data.username && data.username !== username) {
          gameContextLogger.debug('👤 Username mismatch in balance, updating session:', {
            stored: username,
            received: data.username
          });
          apiClient.setSession(data.username);
          setUsername(data.username);
        }
        setError(null);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') {
          gameContextLogger.debug('⏹️ Balance refresh canceled');
          return;
        }

        gameContextLogger.error('❌ Balance refresh failed:', err);
        const errorMessage = getActionErrorMessage('refresh-balance', err);
        
        // Only show balance refresh errors if they're auth-related
        if (errorMessage.toLowerCase().includes('session') || errorMessage.toLowerCase().includes('login')) {
          setError(errorMessage);
          logout();
        }
      }
  }, [isAuthenticated, username, logout]);

  const claimBonus = useCallback(async () => {
      gameContextLogger.debug('🎯 GameContext claimBonus called');
      
      // Check token directly instead of relying on stale state
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for claim bonus:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting claim bonus');
        setIsAuthenticated(false);
        return;
      }

      // Ensure authentication state is correct
      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('🔄 Setting loading to true');
        setLoading(true);
        gameContextLogger.debug('📞 Calling apiClient.claimDailyBonus()...');
        await apiClient.claimDailyBonus();
        gameContextLogger.debug('✅ Claim bonus API call successful');
        
        // Trigger immediate dashboard refresh
        gameContextLogger.debug('🔄 Triggering dashboard refresh after bonus claim');
        triggerPoll('dashboard');
        
        if (onDashboardTrigger) {
          gameContextLogger.debug('🔄 Calling external dashboard trigger');
          onDashboardTrigger();
        }
        
        setError(null);
        gameContextLogger.debug('✅ Claim bonus completed successfully');
      } catch (err) {
        gameContextLogger.error('❌ Claim bonus failed:', err);
        const message = getActionErrorMessage('claim-bonus', err);
        gameContextLogger.debug('📝 Setting error message:', message);
        setError(message);

        // Handle auth errors
        if (message.toLowerCase().includes('session') || message.toLowerCase().includes('login')) {
          gameContextLogger.warn('🚪 Auth error in claim bonus, logging out');
          logout();
        }

        throw err;
      } finally {
        gameContextLogger.debug('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, logout, onDashboardTrigger]);

  const clearError = useCallback(() => {
      gameContextLogger.debug('🧹 Clearing game context error');
      setError(null);
  }, []);

  const navigateAfterDelay = useCallback((path: string, delay: number = 1500) => {
      gameContextLogger.debug('🧭 Navigating after delay:', { path, delay });
      setTimeout(() => {
        gameContextLogger.debug('🧭 Executing delayed navigation to:', path);
        navigate(path);
      }, delay);
  }, [navigate]);

  const startPromptRound = useCallback(async () => {
      gameContextLogger.debug('🎯 GameContext startPromptRound called');
      
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for start prompt round:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting start prompt round');
        setIsAuthenticated(false);
        return;
      }

      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('🔄 Setting loading to true');
        setLoading(true);
        setError(null);
        gameContextLogger.debug('📞 Calling apiClient.startPromptRound()...');
        const response = await apiClient.startPromptRound();
        gameContextLogger.debug('✅ Start prompt round API call successful:', {
          roundId: response.round_id,
          expiresAt: response.expires_at,
          promptText: response.prompt_text,
          cost: response.cost
        });
        
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
        
        setActiveRound(newActiveRound);
        gameContextLogger.debug('🔄 Triggering dashboard refresh after starting prompt round');
        triggerPoll('dashboard');
        
        if (onDashboardTrigger) {
          gameContextLogger.debug('🔄 Calling external dashboard trigger');
          onDashboardTrigger();
        }
        
        gameContextLogger.debug('✅ Start prompt round completed successfully');
      } catch (err) {
        gameContextLogger.error('❌ Start prompt round failed:', err);
        const errorMessage = getActionErrorMessage('start-prompt', err);
        gameContextLogger.debug('📝 Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        gameContextLogger.debug('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, onDashboardTrigger]);

  const startCopyRound = useCallback(async () => {
      gameContextLogger.debug('🎯 GameContext startCopyRound called');

      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for start copy round:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting start copy round');
        setIsAuthenticated(false);
        return;
      }

      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('🔄 Setting loading to true');
        setLoading(true);
        setError(null);
        gameContextLogger.debug('📞 Calling apiClient.startCopyRound()...');
        const response = await apiClient.startCopyRound();
        gameContextLogger.debug('✅ Start copy round API call successful:', {
          roundId: response.round_id,
          expiresAt: response.expires_at,
          originalPhrase: response.original_phrase,
          cost: response.cost,
          discountActive: response.discount_active
        });
        
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
        
        setActiveRound(newActiveRound);
        gameContextLogger.debug('🔄 Triggering dashboard refresh after starting copy round');
        triggerPoll('dashboard');
        
        if (onDashboardTrigger) {
          gameContextLogger.debug('🔄 Calling external dashboard trigger');
          onDashboardTrigger();
        }
        
        gameContextLogger.debug('✅ Start copy round completed successfully');
      } catch (err) {
        gameContextLogger.error('❌ Start copy round failed:', err);
        const errorMessage = getActionErrorMessage('start-copy', err);
        gameContextLogger.debug('📝 Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        gameContextLogger.debug('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, onDashboardTrigger]);

  const flagCopyRound = useCallback(async (roundId: string): Promise<FlagCopyRoundResponse> => {
      gameContextLogger.debug('🚩 GameContext flagCopyRound called', { roundId });

      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for flag copy round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting flag copy round');
        setIsAuthenticated(false);
        throw new Error('missing_token');
      }

      try {
        gameContextLogger.debug('📞 Calling apiClient.flagCopyRound()...', { roundId });
        const response = await apiClient.flagCopyRound(roundId);
        gameContextLogger.info('✅ Copy round flagged successfully', { roundId, flagId: response.flag_id });
        await refreshDashboard();
        return response;
      } catch (err) {
        gameContextLogger.error('❌ Failed to flag copy round:', err);
        throw err;
      }
  }, [refreshDashboard]);

  const abandonRound = useCallback(async (roundId: string): Promise<AbandonRoundResponse> => {
      gameContextLogger.debug('🛑 GameContext abandonRound called', { roundId });

      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for abandon round:', { hasToken: !!token });

      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting abandon round');
        setIsAuthenticated(false);
        throw new Error('missing_token');
      }

      try {
        gameContextLogger.debug('📞 Calling apiClient.abandonRound()...', { roundId });
        const response = await apiClient.abandonRound(roundId);
        gameContextLogger.info('✅ Round abandoned successfully', {
          roundId,
          refundAmount: response.refund_amount,
          penaltyKept: response.penalty_kept,
        });
        await refreshDashboard();
        return response;
      } catch (err) {
        gameContextLogger.error('❌ Failed to abandon round:', err);
        throw err;
      }
  }, [refreshDashboard]);

  const startVoteRound = useCallback(async () => {
      gameContextLogger.debug('🎯 GameContext startVoteRound called');
      
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for start vote round:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting start vote round');
        setIsAuthenticated(false);
        return;
      }

      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('🔄 Setting loading to true');
        setLoading(true);
        setError(null);
        gameContextLogger.debug('📞 Calling apiClient.startVoteRound()...');
        const response = await apiClient.startVoteRound();
        gameContextLogger.debug('✅ Start vote round API call successful:', {
          roundId: response.round_id,
          expiresAt: response.expires_at,
          phrasesetId: response.phraseset_id,
          promptText: response.prompt_text,
          phrases: response.phrases
        });
        
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
        
        setActiveRound(newActiveRound);
        gameContextLogger.debug('🔄 Triggering dashboard refresh after starting vote round');
        triggerPoll('dashboard');
        
        if (onDashboardTrigger) {
          gameContextLogger.debug('🔄 Calling external dashboard trigger');
          onDashboardTrigger();
        }
        
        gameContextLogger.debug('✅ Start vote round completed successfully');
      } catch (err) {
        gameContextLogger.error('❌ Start vote round failed:', err);
        const errorMessage = getActionErrorMessage('start-vote', err);
        gameContextLogger.debug('📝 Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      } finally {
        gameContextLogger.debug('🔄 Setting loading to false');
        setLoading(false);
      }
  }, [isAuthenticated, triggerPoll, onDashboardTrigger]);

  const claimPhrasesetPrize = useCallback(async (phrasesetId: string) => {
      gameContextLogger.debug('🎯 GameContext claimPhrasesetPrize called:', { phrasesetId });
      
      const token = await apiClient.ensureAccessToken();
      gameContextLogger.debug('🔑 Token check for claim phraseset prize:', { hasToken: !!token });
      
      if (!token) {
        gameContextLogger.warn('❌ No valid token, aborting claim phraseset prize');
        setIsAuthenticated(false);
        return;
      }

      if (!isAuthenticated) {
        gameContextLogger.debug('🔄 Setting authenticated to true after token check');
        setIsAuthenticated(true);
      }

      try {
        gameContextLogger.debug('📞 Calling apiClient.claimPhrasesetPrize...');
        await apiClient.claimPhrasesetPrize(phrasesetId);
        gameContextLogger.debug('✅ Claim phraseset prize API call successful');
        
        gameContextLogger.debug('🔄 Triggering dashboard refresh after claiming phraseset prize');
        triggerPoll('dashboard');
        
        if (onDashboardTrigger) {
          gameContextLogger.debug('🔄 Calling external dashboard trigger');
          onDashboardTrigger();
        }
        
        setError(null);
        gameContextLogger.debug('✅ Claim phraseset prize completed successfully');
      } catch (err) {
        gameContextLogger.error('❌ Claim phraseset prize failed:', err);
        const errorMessage = getActionErrorMessage('claim-prize', err);
        gameContextLogger.debug('📝 Setting error message:', errorMessage);
        setError(errorMessage);
        throw err;
      }
  }, [isAuthenticated, triggerPoll, onDashboardTrigger]);

  // Set up smart polling when authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      gameContextLogger.debug('🛑 Stopping all polling due to unauthenticated state');
      stopPoll('dashboard');
      stopPoll('balance');
      return;
    }

    gameContextLogger.debug('🔄 Starting smart polling for dashboard and balance');
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
      gameContextLogger.debug('🛑 Cleaning up polling on unmount');
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

    gameContextLogger.debug('🚀 Performing initial dashboard load');
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
    flagCopyRound,
    abandonRound,
    startVoteRound,
    claimPhrasesetPrize,
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
