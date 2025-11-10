import { useState } from 'react';
import type { RoleLeaderboard, WeeklyLeaderboardEntry, GrossEarningsLeaderboard, GrossEarningsLeaderboardEntry } from '../../api/types';

interface WeeklyLeaderboardProps {
  promptLeaderboard: RoleLeaderboard | null;
  copyLeaderboard: RoleLeaderboard | null;
  voterLeaderboard: RoleLeaderboard | null;
  grossEarningsLeaderboard: GrossEarningsLeaderboard | null;
  loading?: boolean;
  error?: string | null;
}

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

type Role = 'prompt' | 'copy' | 'voter';
type TabType = Role | 'gross_earnings';

const roleLabels: Record<TabType, string> = {
  prompt: 'Prompt',
  copy: 'Copy',
  voter: 'Voter',
  gross_earnings: 'Gross Earnings',
};

const MIN_BAR_PERCENTAGE = 8;

interface LeaderboardEntryDisplayConfig {
  metricLabel: string;
  metricFormatter: (entry: WeeklyLeaderboardEntry | GrossEarningsLeaderboardEntry) => string;
  metricAccessor: (entry: WeeklyLeaderboardEntry | GrossEarningsLeaderboardEntry) => number;
  detailFormatter: (entry: WeeklyLeaderboardEntry | GrossEarningsLeaderboardEntry) => string;
  emptyMessage: string;
}

interface GenericLeaderboardListProps {
  leaders: (WeeklyLeaderboardEntry | GrossEarningsLeaderboardEntry)[];
  config: LeaderboardEntryDisplayConfig;
}

const GenericLeaderboardList: React.FC<GenericLeaderboardListProps> = ({ leaders, config }) => {
  if (leaders.length === 0) {
    return (
      <div className="rounded-tile border border-quip-navy/10 bg-white p-6 text-center text-sm text-quip-navy/70">
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
          ? 'border-2 border-quip-orange bg-quip-orange/10 shadow-md'
          : 'border border-quip-navy/10 bg-white';
        const rankLabel = entry.rank ? `#${entry.rank}` : '-';
        const formattedMetric = config.metricFormatter(entry);

        return (
          <div
            key={entry.player_id}
            className={`rounded-tile px-3 py-2.5 transition-colors duration-200 ${highlightClasses}`}
            role="listitem"
            aria-label={`${entry.username} ${config.metricLabel.toLowerCase()} ${formattedMetric}`}
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold uppercase tracking-wide text-quip-navy/60">{rankLabel}</span>
                <span className="font-display text-lg text-quip-navy">{entry.username}</span>
              </div>
              <div className="text-right">
                <span className="block text-xs uppercase tracking-wide text-quip-navy/50">{config.metricLabel}</span>
                <div className="font-mono text-lg font-semibold text-quip-teal">{formattedMetric}</div>
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
              <p className="mt-1.5 text-xs text-quip-navy/50">{config.detailFormatter(entry)}</p>
            )}
          </div>
        );
      })}
    </div>
  );
};

const LeaderboardList: React.FC<{ leaders: WeeklyLeaderboardEntry[] }> = ({ leaders }) => {
  return (
    <GenericLeaderboardList
      leaders={leaders}
      config={{
        metricLabel: 'Win Rate',
        metricFormatter: (entry) => `${(entry as WeeklyLeaderboardEntry).win_rate.toFixed(1)}%`,
        metricAccessor: (entry) => (entry as WeeklyLeaderboardEntry).win_rate,
        detailFormatter: (entry) => {
          const e = entry as WeeklyLeaderboardEntry;
          return `${e.total_rounds} rounds · Net ${currencyFormatter.format(e.net_earnings)}`;
        },
        emptyMessage: 'No completed rounds yet this week—play a round to appear on the leaderboard!',
      }}
    />
  );
};

const GrossEarningsLeaderboardList: React.FC<{ leaders: GrossEarningsLeaderboardEntry[] }> = ({ leaders }) => {
  return (
    <GenericLeaderboardList
      leaders={leaders}
      config={{
        metricLabel: 'Gross Earnings',
        metricFormatter: (entry) => currencyFormatter.format((entry as GrossEarningsLeaderboardEntry).gross_earnings),
        metricAccessor: (entry) => (entry as GrossEarningsLeaderboardEntry).gross_earnings,
        detailFormatter: (entry) => `${entry.total_rounds} rounds`,
        emptyMessage: 'No earnings yet—play some rounds to appear on the leaderboard!',
      }}
    />
  );
};

const WeeklyLeaderboard: React.FC<WeeklyLeaderboardProps> = ({
  promptLeaderboard,
  copyLeaderboard,
  voterLeaderboard,
  grossEarningsLeaderboard,
  loading = false,
  error = null,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('prompt');

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

  const roleLeaderboards: Record<Role, RoleLeaderboard | null> = {
    prompt: promptLeaderboard,
    copy: copyLeaderboard,
    voter: voterLeaderboard,
  };

  const currentLeaderboard = activeTab === 'gross_earnings'
    ? null
    : roleLeaderboards[activeTab as Role];

  return (
    <div className="space-y-4">
      {/* Tab Navigation */}
      <div className="flex border-b border-quip-navy/10" role="tablist">
        {(['prompt', 'copy', 'voter', 'gross_earnings'] as TabType[]).map((tab) => {
          const isActive = activeTab === tab;
          return (
            <button
              key={tab}
              role="tab"
              aria-selected={isActive}
              onClick={() => setActiveTab(tab)}
              className={`px-4 py-2 font-semibold text-sm transition-colors duration-200 border-b-2 ${
                isActive
                  ? 'border-quip-orange text-quip-orange'
                  : 'border-transparent text-quip-navy/60 hover:text-quip-navy hover:border-quip-navy/30'
              }`}
            >
              {roleLabels[tab]}
            </button>
          );
        })}
      </div>

      {/* Leaderboard Content */}
      {activeTab === 'gross_earnings' && grossEarningsLeaderboard && (
        <GrossEarningsLeaderboardList leaders={grossEarningsLeaderboard.leaders} />
      )}
      {activeTab !== 'gross_earnings' && currentLeaderboard && (
        <LeaderboardList leaders={currentLeaderboard.leaders} />
      )}
    </div>
  );
};

export default WeeklyLeaderboard;
