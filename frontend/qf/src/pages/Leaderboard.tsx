import { useEffect, useRef, useState } from 'react';
import apiClient, { extractErrorMessage } from '../api/client';
import type { LeaderboardResponse } from '../api/types';
import { Header } from '../components/Header';
import WeeklyLeaderboard from '../components/statistics/WeeklyLeaderboard';
import { leaderboardLogger } from '../utils/logger';

type LeaderboardPeriod = 'weekly' | 'alltime';

const Leaderboard: React.FC = () => {
  const [activePeriod, setActivePeriod] = useState<LeaderboardPeriod>('weekly');
  const [weeklyData, setWeeklyData] = useState<LeaderboardResponse | null>(null);
  const [alltimeData, setAlltimeData] = useState<LeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const touchStartX = useRef<number | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);

        leaderboardLogger.debug('Fetching leaderboard data');
        const [weekly, alltime] = await Promise.all([
          apiClient.getWeeklyLeaderboard(controller.signal),
          apiClient.getAllTimeLeaderboard(controller.signal),
        ]);

        setWeeklyData(weekly);
        setAlltimeData(alltime);

        leaderboardLogger.info('Leaderboard data loaded', {
          weeklyPromptEntries: weekly?.prompt_leaderboard?.leaders?.length ?? 0,
          alltimePromptEntries: alltime?.prompt_leaderboard?.leaders?.length ?? 0,
        });
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        const message = extractErrorMessage(err) || 'Failed to load leaderboard. Please try again.';
        leaderboardLogger.error('Failed to load leaderboard', err);
        setError(message);
      } finally {
        setLoading(false);
        leaderboardLogger.debug('Leaderboard fetch flow completed');
      }
    };

    fetchData();

    return () => controller.abort();
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
            <p className="mt-4 text-ccl-navy font-display">Loading leaderboard...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="tile-card p-8">
            <h1 className="text-2xl font-display font-bold text-ccl-navy mb-4">Leaderboard</h1>
            <div className="text-red-600">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  const currentData = activePeriod === 'weekly' ? weeklyData : alltimeData;

  const handleTouchStart = (event: React.TouchEvent<HTMLDivElement>) => {
    touchStartX.current = event.touches[0]?.clientX ?? null;
  };

  const handleTouchEnd = (event: React.TouchEvent<HTMLDivElement>) => {
    if (touchStartX.current === null) return;
    const endX = event.changedTouches[0]?.clientX ?? touchStartX.current;
    const deltaX = endX - touchStartX.current;

    if (Math.abs(deltaX) > 40) {
      if (deltaX < 0 && activePeriod === 'weekly') {
        setActivePeriod('alltime');
      } else if (deltaX > 0 && activePeriod === 'alltime') {
        setActivePeriod('weekly');
      }
    }

    touchStartX.current = null;
  };

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-display font-bold text-ccl-navy">Leaderboard</h1>
              <p className="text-ccl-teal mt-1">See how you rank among all players</p>
            </div>
          </div>
        </div>

        {/* Period Tabs */}
        <div className="tile-card p-6" onTouchStart={handleTouchStart} onTouchEnd={handleTouchEnd}>
          <div className="flex border-b border-ccl-navy/10 mb-6" role="tablist">
            <button
              role="tab"
              aria-selected={activePeriod === 'weekly'}
              onClick={() => setActivePeriod('weekly')}
              className={`px-6 py-3 font-semibold transition-colors duration-200 border-b-2 ${
                activePeriod === 'weekly'
                  ? 'border-ccl-orange text-ccl-orange'
                  : 'border-transparent text-ccl-navy/60 hover:text-ccl-navy hover:border-ccl-navy/30'
              }`}
            >
              Weekly Leaders
            </button>
            <button
              role="tab"
              aria-selected={activePeriod === 'alltime'}
              onClick={() => setActivePeriod('alltime')}
              className={`px-6 py-3 font-semibold transition-colors duration-200 border-b-2 ${
                activePeriod === 'alltime'
                  ? 'border-ccl-orange text-ccl-orange'
                  : 'border-transparent text-ccl-navy/60 hover:text-ccl-navy hover:border-ccl-navy/30'
              }`}
            >
              All-Time Leaders
            </button>
          </div>

          {/* Description */}
          <p className="text-sm text-ccl-teal mb-4">
            {activePeriod === 'weekly'
              ? 'Ranking players by vault gains over the past seven days.'
              : 'All-time rankings by vault balance since the beginning.'}
          </p>

          {/* Leaderboard Content */}
          {currentData && (
            <WeeklyLeaderboard
              grossEarningsLeaderboard={currentData.gross_earnings_leaderboard}
              loading={false}
              error={null}
            />
          )}
        </div>
      </div>
    </div>
  );
};

export default Leaderboard;
