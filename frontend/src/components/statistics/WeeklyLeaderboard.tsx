import type { WeeklyLeaderboardEntry } from '../../api/types';

interface WeeklyLeaderboardProps {
  leaders: WeeklyLeaderboardEntry[] | null;
  loading?: boolean;
  error?: string | null;
}

const currencyFormatter = new Intl.NumberFormat('en-US', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
});

const WeeklyLeaderboard: React.FC<WeeklyLeaderboardProps> = ({ leaders, loading = false, error = null }) => {
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

  if (!leaders || leaders.length === 0) {
    return (
      <div className="rounded-tile border border-quip-navy/10 bg-white p-6 text-center text-sm text-quip-navy/70">
        No completed rounds yet this week—play a round to appear on the leaderboard!
      </div>
    );
  }

  const maxMagnitude = leaders.reduce((max, entry) => {
    const magnitude = Math.abs(entry.net_cost);
    return magnitude > max ? magnitude : max;
  }, 1);

  return (
    <div className="space-y-3" role="list">
      {leaders.map((entry) => {
        const percent = Math.max(8, Math.round((Math.abs(entry.net_cost) / maxMagnitude) * 100));
        const highlightClasses = entry.is_current_player
          ? 'border-2 border-quip-orange bg-quip-orange/10 shadow-md'
          : 'border border-quip-navy/10 bg-white';
        const valueColor = entry.net_cost <= 0 ? 'text-quip-teal' : 'text-quip-orange';
        const barColor = entry.net_cost <= 0 ? 'bg-quip-teal' : 'bg-quip-orange';
        const rankLabel = entry.rank ? `#${entry.rank}` : '—';

        return (
          <div
            key={entry.player_id}
            className={`rounded-tile p-4 transition-colors duration-200 ${highlightClasses}`}
            role="listitem"
            aria-label={`${entry.username} net cost ${currencyFormatter.format(entry.net_cost)}`}
          >
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <span className="text-sm font-semibold uppercase tracking-wide text-quip-navy/60">{rankLabel}</span>
                <span className="font-display text-lg text-quip-navy">{entry.username}</span>
              </div>
              <div className="text-right">
                <span className="block text-xs uppercase tracking-wide text-quip-navy/50">Net Cost</span>
                <div className={`font-mono text-lg font-semibold ${valueColor}`}>
                  {currencyFormatter.format(entry.net_cost)}
                </div>
              </div>
            </div>

            <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-quip-navy/10">
              <div className={`h-full ${barColor}`} style={{ width: `${percent}%` }} aria-hidden="true" />
            </div>

            {entry.is_current_player ? (
              <p className="mt-2 text-xs font-semibold uppercase tracking-wide text-quip-orange">
                You&apos;re here! Keep climbing the leaderboard.
              </p>
            ) : (
              <p className="mt-2 text-xs text-quip-navy/50">
                Costs {currencyFormatter.format(entry.total_costs)} · Earnings {currencyFormatter.format(entry.total_earnings)}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default WeeklyLeaderboard;
