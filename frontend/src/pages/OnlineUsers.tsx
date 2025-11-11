/**
 * "Who's Online" page component.
 *
 * Shows which users are currently active based on API calls made in the last 30 minutes.
 * Uses WebSocket connection for real-time updates (refreshes every 5 seconds).
 *
 * This is distinct from phraseset activity tracking, which shows historical phraseset
 * review events on the Phrasesets page.
 */
import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import type { OnlineUser } from '../api/types';

const OnlineUsers: React.FC = () => {
  const navigate = useNavigate();
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    let wsAttempted = false;
    let pollingInterval: ReturnType<typeof setInterval> | null = null;

    // Try WebSocket first, fall back to polling if it fails
    const connectWebSocket = async () => {
      if (wsAttempted) return; // Prevent multiple attempts
      wsAttempted = true;

      try {
        // Step 1: Fetch short-lived WebSocket token via REST API (through Vercel proxy)
        // This endpoint validates HttpOnly cookies and returns a token we can use for WebSocket
        const tokenResponse = await fetch('/api/auth/ws-token', {
          credentials: 'include', // Include HttpOnly cookies
        });

        if (!tokenResponse.ok) {
          throw new Error('Failed to get WebSocket token');
        }

        const { token } = await tokenResponse.json();

        // Step 2: Construct WebSocket URL for direct connection to Heroku
        const apiUrl = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8000`;
        let wsUrl: string;

        if (apiUrl.startsWith('/')) {
          // Production: use direct Heroku connection (cannot proxy WebSocket through Vercel)
          wsUrl = 'wss://quipflip-c196034288cd.herokuapp.com/users/online/ws';
        } else {
          // Development: connect directly to local backend
          wsUrl = apiUrl
            .replace('http://', 'ws://')
            .replace('https://', 'wss://') + '/users/online/ws';
        }

        // Step 3: Add short-lived token as query parameter
        wsUrl += `?token=${encodeURIComponent(token)}`;

        // Create WebSocket connection
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          setConnected(true);
          setError(null);
          setLoading(false);
        };

        ws.onmessage = (event) => {
          try {
            const data: {
              type: string;
              users: OnlineUser[];
              total_count: number;
              timestamp: string;
            } = JSON.parse(event.data);

            if (data.type === 'online_users_update') {
              setOnlineUsers(data.users);
              setTotalCount(data.total_count);
            }
          } catch (err) {
            // Silently ignore malformed messages
          }
        };

        ws.onerror = () => {
          setConnected(false);
          // Fall back to polling if WebSocket fails
          startPolling();
        };

        ws.onclose = (event) => {
          setConnected(false);

          // Check for authentication failure (code 1008 = policy violation)
          if (event.code === 1008) {
            setError('Authentication failed. Please log in again.');
            setLoading(false);
            return;
          }

          // Fall back to polling if WebSocket closes unexpectedly
          if (!pollingInterval) {
            startPolling();
          }
        };

        wsRef.current = ws;
      } catch (err) {
        setConnected(false);
        startPolling();
      }
    };

    // Fallback polling mechanism for when WebSocket fails
    const startPolling = () => {
      if (pollingInterval) return; // Already polling

      setError('Using polling mode (WebSocket unavailable)');
      setLoading(false);

      // Fetch initial data
      fetchOnlineUsers();

      // Set up polling every 10 seconds (more conservative than WebSocket)
      pollingInterval = setInterval(fetchOnlineUsers, 10000);
    };

    const fetchOnlineUsers = async () => {
      try {
        const response = await fetch('/api/users/online', {
          credentials: 'include', // Include cookies for authentication
        });

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data: { users: OnlineUser[]; total_count: number } = await response.json();
        setOnlineUsers(data.users);
        setTotalCount(data.total_count);
        
        // Clear any connection errors if polling is working
        if (error && error.includes('WebSocket unavailable')) {
          setError(null);
        }
      } catch (err) {
        console.error('Failed to fetch online users:', err);
        if (!error) {
          setError('Failed to load online users');
        }
      }
    };

    // Start with WebSocket attempt
    connectWebSocket();

    // Cleanup on unmount
    return () => {
      // Clear polling interval
      if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
      }

      // Clear any pending reconnect timer
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }

      // Close WebSocket connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Get action color based on action category (centralized from backend)
  const getActionColor = (category: string): string => {
    const categoryColorMap: Record<string, string> = {
      'round_prompt': 'bg-quip-orange',
      'round_copy': 'bg-quip-coral', 
      'round_vote': 'bg-quip-teal',
      'round_other': 'bg-quip-navy',
      'stats': 'bg-blue-500',
      'review': 'bg-green-500',
      'navigation': 'bg-yellow-500',
      'quests': 'bg-pink-500',
      'auth': 'bg-purple-500',
      'other': 'bg-gray-400',
    };
    return categoryColorMap[category] || 'bg-gray-400';
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
            <p className="mt-4 text-quip-navy font-display">Connecting to online users...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-display font-bold text-quip-navy">Online Users</h1>
              <p className="text-quip-teal mt-1">
                See who's currently playing ({totalCount} {totalCount === 1 ? 'user' : 'users'} online)
              </p>
            </div>
            <div className="flex items-center gap-2">
              {/* Connection status indicator */}
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}></div>
                <span className="text-sm text-quip-navy">
                  {connected ? 'Live' : 'Reconnecting...'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Error message */}
        {error && (
          <div className="tile-card p-4 mb-6 bg-red-50 border border-red-200">
            <p className="text-red-600">{error}</p>
          </div>
        )}

        {/* Users list */}
        <div className="tile-card p-6">
          {onlineUsers.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-quip-navy font-display text-lg">No users online right now</p>
              <p className="text-quip-teal mt-2">Be the first to make a move!</p>
            </div>
          ) : (
            <div className="space-y-3">
              {onlineUsers.map((user) => (
                <div
                  key={user.username}
                  className="flex items-center justify-between p-4 bg-quip-cream rounded-lg border border-quip-orange/20 hover:border-quip-orange/40 transition-colors"
                >
                  <div className="flex items-center gap-4 flex-1">
                    {/* User avatar placeholder */}
                    <div className="w-10 h-10 rounded-full bg-quip-navy flex items-center justify-center text-white font-bold">
                      {user.username.charAt(0).toUpperCase()}
                    </div>

                    {/* User info */}
                    <div className="flex-1">
                      <p className="font-bold text-quip-navy">{user.username}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold text-white ${getActionColor(user.last_action_category)}`}>
                          {user.last_action}
                        </span>
                        <span className="text-sm text-quip-teal">{user.time_ago}</span>
                      </div>
                    </div>
                  </div>

                  {/* Online indicator */}
                  <div className="flex items-center gap-2">
                    <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                    <span className="text-xs text-gray-500 hidden sm:inline">Online</span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Info note */}
        <div className="mt-6 tile-card p-4 bg-blue-50 border border-blue-200">
          <p className="text-sm text-blue-900">
            <strong>Note:</strong> Users are shown as online if they've made an API call in the last 30 minutes.
            This page updates automatically every 5 seconds.
          </p>
        </div>

        {/* Back button */}
        <div className="mt-6 text-center">
          <button
            onClick={() => navigate('/dashboard')}
            className="bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-6 rounded-tile transition-all hover:shadow-tile-sm"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default OnlineUsers;
