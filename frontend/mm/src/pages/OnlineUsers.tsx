/**
 * "Who's Online" page component.
 *
 * Shows which users are currently active based on API calls made in the last 30 minutes.
 * Uses WebSocket connection for real-time updates (refreshes every 5 seconds).
 *
 * This is distinct from phraseset activity tracking, which shows historical phraseset
 * review events on the Phrasesets page.
 */
import { useGame } from '../contexts/GameContext';
import { useNotifications } from '../contexts/NotificationContext';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

// Calculate account age in days (rounded up)
const getAccountAgeDays = (createdAt: string): number => {
  const now = new Date();
  const created = new Date(createdAt);
  const diffMs = now.getTime() - created.getTime();
  const diffDays = diffMs / (1000 * 60 * 60 * 24);
  // Round up, but ensure brand new accounts show at least 1
  return Math.max(1, Math.ceil(diffDays));
};

// Get user initials from username (up to 2 letters)
const getUserInitials = (username: string): string => {
  const parts = username.trim().split(/\s+/);
  if (parts.length >= 2) {
    return (parts[0].charAt(0) + parts[1].charAt(0)).toUpperCase();
  }
  return username.charAt(0).toUpperCase();
};

const OnlineUsers: React.FC = () => {
  const { state } = useGame();
  const {
    onlineUsers,
    totalCount,
    loadingOnlineUsers,
    onlineUsersError,
    onlineUsersConnected,
    pingStatus,
    handlePingUser,
  } = useNotifications();
  const currentUsername = state.player?.username;

  // Get action color based on action category (centralized from backend)
  const getActionColor = (category: string): string => {
    const categoryColorMap: Record<string, string> = {
      'round_prompt': 'bg-ccl-orange',
      'round_copy': 'bg-quip-coral',
      'round_vote': 'bg-ccl-teal',
      'round_navigation': 'bg-indigo-500',
      'round_other': 'bg-ccl-navy',
      'stats': 'bg-blue-500',
      'review': 'bg-green-500',
      'navigation': 'bg-yellow-500',
      'quests': 'bg-pink-500',
      'quest_rewards': 'bg-lime-600',
      'practice': 'bg-emerald-600',
      'economy': 'bg-amber-600',
      'tutorial': 'bg-sky-600',
      'account': 'bg-slate-600',
      'notifications': 'bg-cyan-600',
      'feedback': 'bg-rose-500',
      'auth': 'bg-purple-500',
      'other': 'bg-gray-400',
    };
    return categoryColorMap[category] || 'bg-gray-400';
  };

  if (loadingOnlineUsers) {
    return (
      <div className="container mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
          <p className="mt-4 text-ccl-navy font-display">Connecting to online users...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8">
      {/* Header */}
      <div className="tile-card p-6 mb-6">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div className="flex-1">
            <h1 className="text-3xl font-display font-bold text-ccl-navy">Online Users</h1>
            <p className="text-ccl-teal mt-1">
              See who's currently playing ({totalCount} {totalCount === 1 ? 'user' : 'users'} online)
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Connection status indicator */}
            <div className="flex items-center gap-2">
              <div
                className={`w-2 h-2 rounded-full ${onlineUsersConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}
              ></div>
              <span className="text-sm text-ccl-navy">
                {onlineUsersConnected ? 'Live' : 'Reconnecting...'}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Error message */}
      {onlineUsersError && (
        <div className="tile-card p-4 mb-6 bg-red-50 border border-red-200">
          <p className="text-red-600">{onlineUsersError}</p>
        </div>
      )}

      {/* Users list */}
      <div className="tile-card p-6">
        {onlineUsers.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-ccl-navy font-display text-lg">No users online right now</p>
            <p className="text-ccl-teal mt-2">Be the first to make a move!</p>
          </div>
        ) : (
          <div className="space-y-3">
            {onlineUsers.map((user) => {
              const accountAgeDays = getAccountAgeDays(user.created_at);
              const status = pingStatus[user.username] ?? 'idle';
              const isSelf = currentUsername === user.username;
              return (
                <div
                  key={user.username}
                  className="flex items-center justify-between p-4 bg-ccl-cream rounded-lg border border-ccl-orange/20 hover:border-ccl-orange/40 transition-colors"
                >
                  <div className="flex items-center gap-4 flex-1">
                    {/* User avatar placeholder */}
                    <div className="w-10 h-10 rounded-full bg-ccl-navy flex items-center justify-center text-white font-bold text-sm">
                      {getUserInitials(user.username)}
                    </div>

                    {/* User info */}
                    <div className="flex-1">
                      <p className="font-bold text-ccl-navy">{user.username}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <span className={`inline-block px-2 py-0.5 rounded text-xs font-semibold text-white ${getActionColor(user.last_action_category)}`}>
                          {user.last_action}
                        </span>
                        <span className="text-sm text-ccl-teal">{user.time_ago}</span>
                      </div>
                      <div className="flex items-center gap-3 mt-2">
                        <div className="flex items-center gap-1">
                          <CurrencyDisplay amount={user.wallet} iconClassName="w-3 h-3" textClassName="text-sm text-ccl-navy" />
                        </div>
                        <span className="text-sm text-gray-500">•</span>
                        <span className="text-sm text-gray-600">{accountAgeDays} {accountAgeDays === 1 ? 'day' : 'days'} old</span>
                      </div>
                    </div>
                  </div>

                  {/* Online indicator */}
                  <div className="flex items-center gap-3">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
                      <span className="text-xs text-gray-500 hidden sm:inline">Online</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handlePingUser(user.username)}
                        disabled={isSelf || status === 'sending' || status === 'sent'}
                        className="text-sm bg-ccl-turquoise text-white px-3 py-2 rounded-lg hover:bg-ccl-teal transition-colors disabled:bg-gray-300 disabled:text-gray-600 disabled:cursor-not-allowed"
                      >
                        {status === 'sending'
                          ? 'Pinging...'
                          : status === 'sent'
                            ? 'Pinged!'
                            : 'Ping'}
                      </button>
                      {isSelf && (
                        <span className="text-xs text-gray-500">You</span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
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
    </div>
  );
};

export default OnlineUsers;
