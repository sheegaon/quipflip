import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '../api/client';
import type { WeeklyLeaderboardResponse } from '../api/types';
import { Header } from '../components/Header';
import WeeklyLeaderboard from '../components/statistics/WeeklyLeaderboard';
import { leaderboardLogger } from '../utils/logger';

type LeaderboardPeriod = 'weekly' | 'alltime';

const Leaderboard: React.FC = () => {
  const navigate = useNavigate();
  const [activePeriod, setActivePeriod] = useState<LeaderboardPeriod>('weekly');
  const [weeklyData, setWeeklyData] = useState<WeeklyLeaderboardResponse | null>(null);
  const [alltimeData, setAlltimeData] = useState<WeeklyLeaderboardResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
            <p className="mt-4 text-quip-navy font-display">Loading leaderboard...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="tile-card p-8">
            <h1 className="text-2xl font-display font-bold text-quip-navy mb-4">Leaderboard</h1>
            <div className="text-red-600">{error}</div>
          </div>
        </div>
      </div>
    );
  }

  const currentData = activePeriod === 'weekly' ? weeklyData : alltimeData;

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        {/* Header with link to statistics */}
        <div className="tile-card p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-display font-bold text-quip-navy">Leaderboard</h1>
              <p className="text-quip-teal mt-1">See how you rank among all players</p>
            </div>
            <div>
              <button
                onClick={() => navigate('/statistics')}
                className="flex items-center gap-2 bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
                title="View your statistics"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path d="M2 11a1 1 0 011-1h2a1 1 0 011 1v5a1 1 0 01-1 1H3a1 1 0 01-1-1v-5zM8 7a1 1 0 011-1h2a1 1 0 011 1v9a1 1 0 01-1 1H9a1 1 0 01-1-1V7zM14 4a1 1 0 011-1h2a1 1 0 011 1v12a1 1 0 01-1 1h-2a1 1 0 01-1-1V4z" />
                </svg>
                <span>My Statistics</span>
              </button>
            </div>
          </div>
        </div>

        {/* Period Tabs */}
        <div className="tile-card p-6">
          <div className="flex border-b border-quip-navy/10 mb-6" role="tablist">
            <button
              role="tab"
              aria-selected={activePeriod === 'weekly'}
              onClick={() => setActivePeriod('weekly')}
              className={`px-6 py-3 font-semibold transition-colors duration-200 border-b-2 ${
                activePeriod === 'weekly'
                  ? 'border-quip-orange text-quip-orange'
                  : 'border-transparent text-quip-navy/60 hover:text-quip-navy hover:border-quip-navy/30'
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
                  ? 'border-quip-orange text-quip-orange'
                  : 'border-transparent text-quip-navy/60 hover:text-quip-navy hover:border-quip-navy/30'
              }`}
            >
              All-Time Leaders
            </button>
          </div>

          {/* Description */}
          <p className="text-sm text-quip-teal mb-4">
            {activePeriod === 'weekly'
              ? 'Ranking players by win rate over the past seven days across all three roles.'
              : 'All-time rankings by win rate across all three roles since the beginning.'}
          </p>

          {/* Leaderboard Content */}
          {currentData && (
            <WeeklyLeaderboard
              promptLeaderboard={currentData.prompt_leaderboard}
              copyLeaderboard={currentData.copy_leaderboard}
              voterLeaderboard={currentData.voter_leaderboard}
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
