import React, { createContext, useContext, useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient from '../api/client';
import { useSmartPolling, PollConfigs } from '../utils/smartPolling';
import { getActionErrorMessage } from '../utils/errorMessages';
import { gameContextLogger } from '../utils/logger';
import { detectUserSession, associateVisitorWithPlayer } from '../services/sessionDetection';
import { SessionState } from '../types/session';
import { GUEST_CREDENTIALS_KEY } from '../utils/storageKeys';
import type {
  Player,
  ActiveRound,
  PendingResult,
  RoundAvailability,
  PhrasesetDashboardSummary,
  UnclaimedResult,
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
  copyRoundHints: string[] | null;
  loading: boolean;
  error: string | null;
  sessionState: SessionState;
  visitorId: string | null;
}

interface GameActions {
  startSession: (username: string) => void;
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
  fetchCopyHints: (roundId: string) => Promise<string[]>;
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
  const [copyRoundHints, setCopyRoundHints] = useState<string[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sessionState, setSessionState] = useState<SessionState>(SessionState.CHECKING);
  const [visitorId, setVisitorId] = useState<string | null>(null);

  const copyHintsRoundRef = useRef<string | null>(null);

  // Notify other contexts when pending results change
  useEffect(() => {
    if (onPendingResultsChange) {
      onPendingResultsChange(pendingResults);
    }
  }, [pendingResults, onPendingResultsChange]);

  // Initialize session on mount using session detection
  // NOTE: In development, React StrictMode will call this effect twice,
  // leading to duplicate session detection calls. This is intentional React behavior.
  // We use AbortController to cancel the first call when the component remounts.
  useEffect(() => {
    const controller = new AbortController();
    let isMounted = true;

    const initializeSession = async () => {
      gameContextLogger.debug('🔍 Starting session detection on app load');

      try {
        const result = await detectUserSession(controller.signal);

        if (!isMounted) return;

        gameContextLogger.debug('✅ Session detection complete:', {
          state: result.state,
          isAuthenticated: result.isAuthenticated,
          username: result.username,
          visitorId: result.visitorId,
        });

        // Update state based on detection result
        setSessionState(result.state);
        setVisitorId(result.visitorId);
        setIsAuthenticated(result.isAuthenticated);

        if (result.isAuthenticated && result.username) {
          setUsername(result.username);
          if (result.player) {
            setPlayer(result.player);
          }
        } else if (result.state === SessionState.NEW) {
          // Only auto-create guest account for truly NEW visitors
          // Returning visitors with expired cookies should see the landing page
          gameContextLogger.debug('🎭 New visitor detected, creating guest account');

          try {
            const guestResponse = await apiClient.createGuest();

            if (!isMounted) return;

            gameContextLogger.info('✅ Guest account created:', { username: guestResponse.username });

            // Store guest credentials temporarily for display
            localStorage.setItem(GUEST_CREDENTIALS_KEY, JSON.stringify({
              email: guestResponse.email,
              password: guestResponse.password,
              timestamp: Date.now()
            }));

            // Set session with guest account
            apiClient.setSession(guestResponse.username);
            setUsername(guestResponse.username);
            setIsAuthenticated(true);
            setSessionState(SessionState.RETURNING_USER);

            // Associate visitor with guest account
            if (result.visitorId) {
              associateVisitorWithPlayer(result.visitorId, guestResponse.username);
            }

            // Fetch player data
            const playerData = await apiClient.getBalance(controller.signal);
            if (isMounted) {
              setPlayer(playerData);
            }
          } catch (guestErr) {
            if (controller.signal.aborted) return;

            gameContextLogger.error('❌ Failed to create guest account:', guestErr);

            // Fallback to unauthenticated state
            if (isMounted) {
              setUsername(null);
              setPlayer(null);
              setIsAuthenticated(false);
            }
          }
} else if (result.state === SessionState.RETURNING_VISITOR) {
          // Returning visitor with no valid session - don't auto-create guest
          gameContextLogger.debug('👋 Returning visitor without valid session, showing landing page');
        }
      } catch (err) {
        if (controller.signal.aborted) {
          return;
        }

        gameContextLogger.error('❌ Session detection failed:', err);

        // Fallback to safe state
        if (isMounted) {
          setSessionState(SessionState.NEW);
          setIsAuthenticated(false);
          setUsername(null);
          setPlayer(null);
        }
      }
    };

    initializeSession();

    return () => {
      isMounted = false;
      controller.abort();
    };
  }, []);

  // Monitor authentication state changes
  useEffect(() => {
    if (isAuthenticated && username) {
      gameContextLogger.debug('User authenticated', { username });
    }
  }, [isAuthenticated, username]);

  useEffect(() => {
    if (!activeRound || activeRound.round_type !== 'copy') {
      copyHintsRoundRef.current = null;
      if (copyRoundHints !== null) {
        setCopyRoundHints(null);
      }
      return;
    }

    if (copyHintsRoundRef.current && copyHintsRoundRef.current !== activeRound.round_id && copyRoundHints !== null) {
      copyHintsRoundRef.current = null;
      setCopyRoundHints(null);
    }
  }, [activeRound?.round_id, activeRound?.round_type]);

  // Create stable actions object using useCallback for all methods
  const startSession = useCallback((nextUsername: string) => {
      gameContextLogger.debug('🎯 GameContext startSession called:', { username: nextUsername });

      apiClient.setSession(nextUsername);
      setUsername(nextUsername);
      setIsAuthenticated(true);
      setSessionState(SessionState.RETURNING_USER);

      // Associate visitor ID with newly created/logged in account
      if (visitorId) {
        associateVisitorWithPlayer(visitorId, nextUsername);
      }

      // Session started, authentication state will trigger dashboard load
      gameContextLogger.debug('✅ Session started, authentication state will trigger dashboard load');
  }, [visitorId]);

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
        setCopyRoundHints(null);
        copyHintsRoundRef.current = null;
        setLoading(false);
        setError(null);

        // After logout, user is a returning visitor (visitor ID persists)
        setSessionState(visitorId ? SessionState.RETURNING_VISITOR : SessionState.NEW);
      }
  }, [stopPoll, visitorId]);

  const refreshDashboard = useCallback(async (signal?: AbortSignal) => {
      const storedUsername = apiClient.getStoredUsername();
      if (!storedUsername) {
        gameContextLogger.debug('⏭️ Skipping dashboard refresh: no active session detected');
        return;
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

        // De-duplicate pending results using a composite unique key
        // For each result, create a unique key based on phraseset_id + round_id
        const getResultKey = (result: PendingResult) => {
          if (result.role === 'prompt' && result.prompt_round_id) {
            return `${result.phraseset_id}-prompt-${result.prompt_round_id}`;
          } else if (result.role === 'copy' && result.copy_round_id) {
            return `${result.phraseset_id}-copy-${result.copy_round_id}`;
          }
          // Fallback for results without round IDs (shouldn't happen with new schema)
          return `${result.phraseset_id}-${result.role}`;
        };

        const deduplicatedResults = data.pending_results.filter((result, index, self) =>
          index === self.findIndex((r) => getResultKey(r) === getResultKey(result))
        );

        if (deduplicatedResults.length !== data.pending_results.length) {
          gameContextLogger.debug('🔄 Removed duplicate pending results:', {
            original: data.pending_results.length,
            deduplicated: deduplicatedResults.length
          });
        }

        setPendingResults(deduplicatedResults);
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
  }, [username, logout]);

  const refreshBalance = useCallback(async (signal?: AbortSignal) => {
      const storedUsername = apiClient.getStoredUsername();
      if (!storedUsername) {
        gameContextLogger.debug('⏭️ Skipping balance refresh: no active session detected');
        return;
      }

      gameContextLogger.debug('💰 GameContext refreshBalance called');

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
      
      // Check token directly instead of relying on stale state      // Ensure authentication state is correct
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
      gameContextLogger.debug('🎯 GameContext startPromptRound called');      if (!isAuthenticated) {
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
        setCopyRoundHints(null);
        copyHintsRoundRef.current = null;
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
      gameContextLogger.debug('🎯 GameContext startCopyRound called');      if (!isAuthenticated) {
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
        setCopyRoundHints(null);
        copyHintsRoundRef.current = null;
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

  const fetchCopyHints = useCallback(async (roundId: string): Promise<string[]> => {
      if (!roundId) {
        return [];
      }

      if (copyHintsRoundRef.current === roundId && copyRoundHints) {
        gameContextLogger.debug('?? Returning cached copy hints', { roundId });
        return copyRoundHints;
      }

      gameContextLogger.debug('?? Fetching AI copy hints for round', { roundId });

      try {
        const response = await apiClient.getCopyHints(roundId);
        copyHintsRoundRef.current = roundId;
        setCopyRoundHints(response.hints);
        setError(null);
        gameContextLogger.debug('? Copy hints fetched successfully', { count: response.hints?.length ?? 0 });
        return response.hints;
      } catch (err) {
        gameContextLogger.error('? Fetch copy hints failed:', err);
        const errorMessage = getActionErrorMessage('fetch-copy-hints', err);
        setError(errorMessage);
        throw err;
      }
  }, [copyRoundHints, setError]);

  const flagCopyRound = useCallback(async (roundId: string): Promise<FlagCopyRoundResponse> => {
      gameContextLogger.debug('🚩 GameContext flagCopyRound called', { roundId });      try {
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
      gameContextLogger.debug('🛑 GameContext abandonRound called', { roundId });      try {
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
      gameContextLogger.debug('🎯 GameContext startVoteRound called');      if (!isAuthenticated) {
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
        setCopyRoundHints(null);
        copyHintsRoundRef.current = null;
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
      gameContextLogger.debug('🎯 GameContext claimPhrasesetPrize called:', { phrasesetId });      if (!isAuthenticated) {
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

  // Handle bfcache restoration (mobile browsers)
  useEffect(() => {
    const controller = new AbortController();

    const handleBfcacheRestore = () => {
      gameContextLogger.debug('🔄 Bfcache restore detected, resetting initial load guard');
      hasInitialLoadRef.current = false;

      // Trigger immediate dashboard refresh
      if (isAuthenticated) {
        gameContextLogger.debug('🚀 Performing dashboard refresh after bfcache restore');
        refreshDashboard(controller.signal).catch((err) => {
          if (controller.signal.aborted) return;
          gameContextLogger.error('❌ Failed to refresh dashboard after bfcache restore:', err);
        });
      }
    };

    window.addEventListener('bfcache-restore', handleBfcacheRestore);

    return () => {
      controller.abort();
      window.removeEventListener('bfcache-restore', handleBfcacheRestore);
    };
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
    copyRoundHints,
    loading,
    error,
    sessionState,
    visitorId,
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
    fetchCopyHints,
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

