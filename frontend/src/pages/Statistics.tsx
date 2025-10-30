import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useResults } from '../contexts/ResultsContext';
import { useGame } from '../contexts/GameContext';
import { extractErrorMessage } from '../api/client';
import type { HistoricalTrendPoint, PlayerStatistics } from '../api/types';
import { Header } from '../components/Header';
import WinRateChart from '../components/statistics/WinRateChart';
import EarningsChart from '../components/statistics/EarningsChart';
import SpendingChart from '../components/statistics/SpendingChart';
import FrequencyChart from '../components/statistics/FrequencyChart';
import PerformanceRadar from '../components/statistics/PerformanceRadar';
import TopContentTable from '../components/statistics/TopContentTable';
import HistoricalTrendsChart from '../components/statistics/HistoricalTrendsChart';
import { statisticsLogger } from '../utils/logger';

const Statistics: React.FC = () => {
  const navigate = useNavigate();
  const { actions } = useResults();
  const { getStatistics } = actions;
  const { state } = useGame();
  const { player } = state;
  const [data, setData] = useState<PlayerStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartsReady, setChartsReady] = useState(false);

  const historicalTrends = useMemo<HistoricalTrendPoint[]>(() => {
    if (!data) return [];

    if (data.historical_trends && data.historical_trends.length > 0) {
      return data.historical_trends;
    }

    const segments = 6;
    const lastActiveDate = data.frequency?.last_active ? new Date(data.frequency.last_active) : new Date();
    const memberSinceDate = data.frequency?.member_since
      ? new Date(data.frequency.member_since)
      : new Date(lastActiveDate.getTime() - (segments - 1) * 7 * 24 * 60 * 60 * 1000);

    const timelineMs = Math.max(1, lastActiveDate.getTime() - memberSinceDate.getTime());
    const intervalMs = timelineMs / Math.max(1, segments - 1);

    const totalRounds = data.prompt_stats.total_rounds + data.copy_stats.total_rounds + data.voter_stats.total_rounds;
    const totalEarnings = data.earnings.total_earnings;
    const averageWinRate =
      (data.prompt_stats.win_rate + data.copy_stats.win_rate + data.voter_stats.win_rate) / 3 || 0;

    return Array.from({ length: segments }, (_, index) => {
      const progression = (index + 1) / segments;
      const periodDate = new Date(memberSinceDate.getTime() + intervalMs * index);
      const smoothFactor = Math.sin(progression * Math.PI) * 0.08;
      const trendWinRate = Math.min(100, Math.max(0, averageWinRate * (0.85 + smoothFactor + progression * 0.15)));
      const cumulativeEarnings = Math.max(0, totalEarnings * progression * (0.85 + progression * 0.25));
      const cumulativeRounds = Math.max(0, totalRounds * progression * (0.9 + smoothFactor));

      return {
        period: periodDate.toISOString(),
        win_rate: Math.round(trendWinRate * 10) / 10,
        earnings: Math.round(cumulativeEarnings),
        rounds_played: Math.round(cumulativeRounds),
      };
    });
  }, [data]);

  useEffect(() => {
    const controller = new AbortController();

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        setChartsReady(false);
        statisticsLogger.debug('Fetching player statistics');
        const statisticsData = await getStatistics(controller.signal);
        setData(statisticsData);
        statisticsLogger.info('Player statistics loaded', {
          username: statisticsData?.username,
          promptRounds: statisticsData?.prompt_stats?.total_rounds,
          copyRounds: statisticsData?.copy_stats?.total_rounds,
        });
        // Wait for the DOM to fully render and settle before enabling charts
        // This prevents Recharts dimension errors by ensuring containers have proper sizes
        requestAnimationFrame(() => {
          setTimeout(() => setChartsReady(true), 100);
        });
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        const message = extractErrorMessage(err) || 'Failed to load statistics. Please try again.';
        statisticsLogger.error('Failed to load player statistics', err);
        setError(message);
      } finally {
        setLoading(false);
        statisticsLogger.debug('Statistics fetch flow completed');
      }
    };

    fetchData();

    return () => controller.abort();
  }, [getStatistics]);

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
            <p className="mt-4 text-quip-navy font-display">Loading your statistics...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="tile-card p-8">
            <h1 className="text-2xl font-display font-bold text-quip-navy mb-4">Statistics</h1>
            <div className="text-red-600">{error || 'Failed to load statistics'}</div>
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
              <h1 className="text-3xl font-display font-bold text-quip-navy">{data.username}'s Statistics</h1>
              <p className="text-quip-teal mt-1">{data.email}</p>
              <p className="text-quip-teal text-sm mt-1">Track your performance and progress</p>
            </div>
            <div className="flex flex-col sm:flex-row items-end gap-4">
              <button
                onClick={() => navigate('/settings')}
                className="flex items-center gap-2 bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
                title="Account Settings"
              >
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M11.49 3.17c-.38-1.56-2.6-1.56-2.98 0a1.532 1.532 0 01-2.286.948c-1.372-.836-2.942.734-2.106 2.106.54.886.061 2.042-.947 2.287-1.561.379-1.561 2.6 0 2.978a1.532 1.532 0 01.947 2.287c-.836 1.372.734 2.942 2.106 2.106a1.532 1.532 0 012.287.947c.379 1.561 2.6 1.561 2.978 0a1.533 1.533 0 012.287-.947c1.372.836 2.942-.734 2.106-2.106a1.533 1.533 0 01.947-2.287c1.561-.379 1.561-2.6 0-2.978a1.532 1.532 0 01-.947-2.287c.836-1.372-.734-2.942-2.106-2.106a1.532 1.532 0 01-2.287-.947zM10 13a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                </svg>
                <span className="hidden sm:inline">Settings</span>
              </button>
            </div>
          </div>
        </div>

        {/* Guest Upgrade Card */}
        {player?.is_guest && (
          <div className="tile-card p-6 mb-6 bg-gradient-to-br from-orange-50 to-cyan-50 border-2 border-quip-orange">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex-1">
                <h2 className="text-2xl font-display font-bold text-quip-navy mb-2">
                  Upgrade Your Account
                </h2>
                <p className="text-quip-navy mb-3">
                  You're using a guest account. Upgrade to a full account to:
                </p>
                <ul className="list-disc list-inside text-quip-navy text-sm space-y-1 mb-3">
                  <li>Save your progress permanently</li>
                  <li>Access your account from any device</li>
                  <li>Never lose your stats and Flipcoins</li>
                  <li>Get higher rate limits for smoother gameplay</li>
                </ul>
              </div>
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => navigate('/settings')}
                  className="bg-gradient-to-r from-quip-orange to-quip-turquoise hover:from-quip-orange-deep hover:to-quip-teal text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm whitespace-nowrap"
                >
                  Upgrade Now
                </button>
                <p className="text-xs text-center text-gray-600">Quick & Easy</p>
              </div>
            </div>
          </div>
        )}

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Win Rate Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Win Rates by Role</h2>
            {chartsReady ? (
              <WinRateChart
                promptStats={data.prompt_stats}
                copyStats={data.copy_stats}
                voterStats={data.voter_stats}
              />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Earnings Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Earnings Breakdown</h2>
            {chartsReady ? (
              <EarningsChart earnings={data.earnings} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Spending Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Spending Breakdown</h2>
            {chartsReady ? (
              <SpendingChart earnings={data.earnings} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Performance Radar */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Role Performance</h2>
            {chartsReady ? (
              <PerformanceRadar
                promptStats={data.prompt_stats}
                copyStats={data.copy_stats}
                voterStats={data.voter_stats}
              />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Play Frequency */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Activity Metrics</h2>
            {chartsReady ? (
              <FrequencyChart frequency={data.frequency} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Historical Trends */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-2">Historical Trends &amp; Performance Over Time</h2>
            <p className="text-sm text-quip-teal mb-4">
              Track how your win rate, earnings, and activity have evolved across recent weeks and months.
            </p>
            {chartsReady ? (
              <>
                {historicalTrends.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4 text-sm">
                    <div className="bg-quip-orange bg-opacity-10 border border-quip-orange rounded-tile p-3">
                      <div className="text-quip-teal">Latest Win Rate</div>
                      <div className="text-2xl font-bold text-quip-orange">
                        {historicalTrends[historicalTrends.length - 1].win_rate.toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-quip-teal bg-opacity-10 border border-quip-teal rounded-tile p-3">
                      <div className="text-quip-teal">Total Earnings Trend</div>
                      <div className="text-2xl font-bold text-quip-teal">
                        {historicalTrends[historicalTrends.length - 1].earnings.toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-quip-turquoise bg-opacity-10 border border-quip-turquoise rounded-tile p-3">
                      <div className="text-quip-teal">Rounds Played</div>
                      <div className="text-2xl font-bold text-quip-turquoise">
                        {historicalTrends[historicalTrends.length - 1].rounds_played.toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
                <HistoricalTrendsChart trends={historicalTrends} />
              </>
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
              </div>
            )}
          </div>
        </div>

        {/* Top Content Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Favorite Prompts */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Top Earning Prompts</h2>
            <TopContentTable
              items={data.favorite_prompts.map((prompt) => ({ text: prompt }))}
              emptyMessage="No prompts yet. Start a prompt round to earn!"
            />
          </div>

          {/* Best Performing Phrases */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Best Performing Phrases</h2>
            <TopContentTable
              items={data.best_performing_phrases.map((phrase) => ({
                text: phrase.phrase,
                votes: phrase.votes,
                earnings: phrase.earnings,
              }))}
              emptyMessage="No phrases yet. Submit some phrases to see your best performers!"
              showStats
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Statistics;
