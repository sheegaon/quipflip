import React from 'react';
import type { GrossEarningsLeaderboard, GrossEarningsLeaderboardEntry } from '../../api/types.ts';

interface WeeklyLeaderboardProps {
  promptLeaderboard?: null;
  copyLeaderboard?: null;
  voterLeaderboard?: null;
  grossEarningsLeaderboard: GrossEarningsLeaderboard | null;
  loading?: boolean;
  error?: string | null;
}

const MIN_BAR_PERCENTAGE = 8;

interface LeaderboardEntryDisplayConfig {
  metricLabel: string;
  metricFormatter: (entry: GrossEarningsLeaderboardEntry) => string | React.ReactNode;
  metricAccessor: (entry: GrossEarningsLeaderboardEntry) => number;
  detailFormatter: (entry: GrossEarningsLeaderboardEntry) => string;
  emptyMessage: string;
}

interface GenericLeaderboardListProps {
  leaders: GrossEarningsLeaderboardEntry[];
  config: LeaderboardEntryDisplayConfig;
}

const GenericLeaderboardList: React.FC<GenericLeaderboardListProps> = ({ leaders, config }) => {
  if (leaders.length === 0) {
    return (
      <div className="rounded-tile border border-ccl-navy/10 bg-white p-6 text-center text-sm text-ccl-navy/70">
        {config.emptyMessage}
      </div>
    );
  }

  const maxValue = leaders.reduce((max, entry) => {
    const value = config.metricAccessor(entry);
    return value > max ? value : max;
  }, 1);

  return (
    <div className="space-y-2.5" role="list">
      {leaders.map((entry) => {
        const metricValue = config.metricAccessor(entry);
        const percent = Math.max(MIN_BAR_PERCENTAGE, Math.round((metricValue / maxValue) * 100));
        const highlightClasses = entry.is_current_player
          ? 'border-2 border-ccl-orange bg-ccl-orange/10 shadow-md'
          : 'border border-ccl-navy/10 bg-white';
        const rankLabel = entry.rank ? `#${entry.rank}` : '-';
        const formattedMetric = config.metricFormatter(entry);

        return (
          <div
            key={entry.player_id}
            className={`rounded-tile px-3 py-2 transition-colors duration-200 ${highlightClasses}`}
            role="listitem"
            aria-label={`${entry.username} ${config.metricLabel.toLowerCase()} ${formattedMetric}`}
          >
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold uppercase tracking-wide text-ccl-navy/60">{rankLabel}</span>
                <span className="font-display text-base text-ccl-navy">{entry.username}</span>
                <span className="text-xs text-ccl-navy/60">{entry.total_rounds} rounds</span>
              </div>
              <div className="text-right">
                {config.metricLabel && (
                  <span className="block text-[11px] uppercase tracking-wide text-ccl-navy/50">{config.metricLabel}</span>
                )}
                <div className="font-mono text-lg font-semibold text-ccl-teal leading-tight">{formattedMetric}</div>
              </div>
            </div>

            <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-ccl-navy/10">
              <div className="h-full bg-ccl-teal" style={{ width: `${percent}%` }} aria-hidden="true" />
            </div>
          </div>
        );
      })}
    </div>
  );
};

const GrossEarningsLeaderboardList: React.FC<{ leaders: GrossEarningsLeaderboardEntry[] }> = ({ leaders }) => {
  return (
    <GenericLeaderboardList
      leaders={leaders}
      config={{
        metricLabel: '', // Remove "Balance" label
        metricFormatter: (entry) => (
          <span className="inline-flex items-center gap-1">
            <img 
              src="/vault.png" 
              alt="Vault" 
              className="w-4 h-4" 
            />
            <span className="font-mono text-lg font-semibold text-ccl-teal">{entry.vault_balance}</span>
          </span>
        ),
        metricAccessor: (entry) => entry.vault_balance,
        detailFormatter: () => ``, // Remove unused parameter entirely
        emptyMessage: 'No vault earnings yet—play some rounds to appear on the leaderboard!',
      }}
    />
  );
};

const WeeklyLeaderboard: React.FC<WeeklyLeaderboardProps> = ({
  grossEarningsLeaderboard,
  loading = false,
  error = null,
}) => {
  if (loading) {
    return (
      <div className="w-full h-64 flex items-center justify-center" role="status" aria-live="polite">
        <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent" />
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

  const filteredLeaders = (grossEarningsLeaderboard?.leaders ?? []).filter((entry) => {
    const isBot = entry.is_bot || entry.is_ai;
    return !isBot && entry.vault_balance > 0;
  });

  return (
    <div className="space-y-4">
      <GrossEarningsLeaderboardList leaders={filteredLeaders} />
    </div>
  );
};

export default WeeklyLeaderboard;
