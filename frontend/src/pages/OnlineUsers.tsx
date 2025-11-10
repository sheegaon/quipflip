import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';

interface OnlineUser {
  username: string;
  last_action: string;
  last_activity: string;
  time_ago: string;
}

const OnlineUsers: React.FC = () => {
  const navigate = useNavigate();
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to WebSocket
    const connectWebSocket = () => {
      try {
        const host = window.location.hostname;
        const port = import.meta.env.VITE_API_PORT || '8000';

        // Use backend URL from environment or construct it
        const backendUrl = import.meta.env.VITE_API_URL || `http://${host}:${port}`;
        const wsUrl = backendUrl
          .replace('http://', 'ws://')
          .replace('https://', 'wss://') + '/online-users/online/ws';

        // Create WebSocket connection
        // Note: Browser automatically sends cookies with WebSocket handshake for same-origin connections
        // Backend validates authentication via HTTP-only cookies
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
          setError('Connection error. Retrying...');
          setConnected(false);
        };

        ws.onclose = (event) => {
          setConnected(false);

          // Check for authentication failure (code 1008 = policy violation)
          if (event.code === 1008) {
            setError('Authentication failed. Please log in again.');
            setLoading(false);
            // Don't attempt to reconnect on auth failure
            // User needs to refresh/re-authenticate
            return;
          }

          // For other close reasons, attempt to reconnect after 3 seconds
          setTimeout(() => {
            if (wsRef.current === ws) {
              connectWebSocket();
            }
          }, 3000);
        };

        wsRef.current = ws;
      } catch (err) {
        setError('Failed to connect to server');
        setLoading(false);
      }
    };

    connectWebSocket();

    // Cleanup on unmount
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  // Get action color based on action type
  const getActionColor = (action: string): string => {
    const colorMap: Record<string, string> = {
      'Prompt Round': 'bg-quip-orange',
      'Copy Round': 'bg-quip-coral',
      'Vote Round': 'bg-quip-teal',
      'Leaderboard': 'bg-blue-500',
      'Statistics': 'bg-purple-500',
      'Round Review': 'bg-green-500',
      'Dashboard': 'bg-yellow-500',
      'Completed Rounds': 'bg-gray-500',
      'Quests': 'bg-pink-500',
      'Phraseset Review': 'bg-indigo-500',
    };
    return colorMap[action] || 'bg-gray-400';
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
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold text-white ${getActionColor(user.last_action)}`}>
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
