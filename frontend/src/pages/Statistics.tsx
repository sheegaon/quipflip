import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useResults } from '../contexts/ResultsContext';
import { extractErrorMessage } from '../api/client';
import type { PlayerStatistics } from '../api/types';
import { Header } from '../components/Header';
import { CurrencyDisplay } from '../components/CurrencyDisplay';
import WinRateChart from '../components/statistics/WinRateChart';
import EarningsChart from '../components/statistics/EarningsChart';
import SpendingChart from '../components/statistics/SpendingChart';
import FrequencyChart from '../components/statistics/FrequencyChart';
import PerformanceRadar from '../components/statistics/PerformanceRadar';
import TopContentTable from '../components/statistics/TopContentTable';
import { statisticsLogger } from '../utils/logger';

const Statistics: React.FC = () => {
  const navigate = useNavigate();
  const { actions } = useResults();
  const { getStatistics } = actions;
  const [data, setData] = useState<PlayerStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartsReady, setChartsReady] = useState(false);

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
              <div className="text-right">
                <div className="text-sm text-quip-teal">Current Balance</div>
                <div className="text-3xl font-bold text-quip-orange">
                  <CurrencyDisplay
                    amount={data.overall_balance}
                    iconClassName="w-8 h-8"
                    textClassName="text-3xl font-bold text-quip-orange"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

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
export { Statistics };
