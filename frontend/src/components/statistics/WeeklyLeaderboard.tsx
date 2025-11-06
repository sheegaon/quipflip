import { useState } from 'react';
import type { RoleLeaderboard, WeeklyLeaderboardEntry } from '../../api/types';

interface WeeklyLeaderboardProps {
  promptLeaderboard: RoleLeaderboard | null;
  copyLeaderboard: RoleLeaderboard | null;
  voterLeaderboard: RoleLeaderboard | null;
  loading?: boolean;
  error?: string | null;
}

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

type Role = 'prompt' | 'copy' | 'voter';

const roleLabels: Record<Role, string> = {
  prompt: 'Prompt',
  copy: 'Copy',
  voter: 'Voter',
};

const LeaderboardList: React.FC<{ leaders: WeeklyLeaderboardEntry[] }> = ({ leaders }) => {
  if (leaders.length === 0) {
    return (
      <div className="rounded-tile border border-quip-navy/10 bg-white p-6 text-center text-sm text-quip-navy/70">
        No completed rounds yet this week—play a round to appear on the leaderboard!
      </div>
    );
  }

  const maxWinRate = leaders.reduce((max, entry) => {
    return entry.win_rate > max ? entry.win_rate : max;
  }, 1);

  return (
    <div className="space-y-2.5" role="list">
      {leaders.map((entry) => {
        const percent = Math.max(8, Math.round((entry.win_rate / maxWinRate) * 100));
        const highlightClasses = entry.is_current_player
          ? 'border-2 border-quip-orange bg-quip-orange/10 shadow-md'
          : 'border border-quip-navy/10 bg-white';
        const rankLabel = entry.rank ? `#${entry.rank}` : '-';

        return (
          <div
            key={entry.player_id}
            className={`rounded-tile px-3 py-2.5 transition-colors duration-200 ${highlightClasses}`}
            role="listitem"
            aria-label={`${entry.username} win rate ${entry.win_rate.toFixed(1)}%`}
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold uppercase tracking-wide text-quip-navy/60">{rankLabel}</span>
                <span className="font-display text-lg text-quip-navy">{entry.username}</span>
              </div>
              <div className="text-right">
                <span className="block text-xs uppercase tracking-wide text-quip-navy/50">Win Rate</span>
                <div className="font-mono text-lg font-semibold text-quip-teal">
                  {entry.win_rate.toFixed(1)}%
                </div>
              </div>
            </div>

            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-quip-navy/10">
              <div className="h-full bg-quip-teal" style={{ width: `${percent}%` }} aria-hidden="true" />
            </div>

            {entry.is_current_player ? (
              <p className="mt-1.5 text-xs font-semibold uppercase tracking-wide text-quip-orange">
                You&apos;re here! Keep climbing the leaderboard.
              </p>
            ) : (
              <p className="mt-1.5 text-xs text-quip-navy/50">
                {entry.total_rounds} rounds · Net {currencyFormatter.format(entry.net_earnings)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
};

const WeeklyLeaderboard: React.FC<WeeklyLeaderboardProps> = ({
  promptLeaderboard,
  copyLeaderboard,
  voterLeaderboard,
  loading = false,
  error = null,
}) => {
  const [activeTab, setActiveTab] = useState<Role>('prompt');

  if (loading) {
    return (
      <div className="w-full h-64 flex items-center justify-center" role="status" aria-live="polite">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent" />
        <span className="sr-only">Loading weekly leaderboard…</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-tile border border-red-300 bg-red-50 p-4 text-sm text-red-700">
        <p className="font-semibold">Unable to load weekly leaderboard</p>
        <p>{error}</p>
      </div>
    );
  }

  const leaderboards: Record<Role, RoleLeaderboard | null> = {
    prompt: promptLeaderboard,
    copy: copyLeaderboard,
    voter: voterLeaderboard,
  };

  const currentLeaderboard = leaderboards[activeTab];

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex border-b border-quip-navy/10">
        {(['prompt', 'copy', 'voter'] as Role[]).map((role) => {
          const isActive = activeTab === role;
          return (
            <button
              key={role}
              onClick={() => setActiveTab(role)}
              className={`px-4 py-2 font-semibold text-sm transition-colors duration-200 border-b-2 ${
                isActive
                  ? 'border-quip-orange text-quip-orange'
                  : 'border-transparent text-quip-navy/60 hover:text-quip-navy hover:border-quip-navy/30'
              }`}
            >
              {roleLabels[role]}
            </button>
          );
        })}
      </div>

      {/* Leaderboard Content */}
      {currentLeaderboard && <LeaderboardList leaders={currentLeaderboard.leaders} />}
    </div>
  );
};

export default WeeklyLeaderboard;
