import { useState, useEffect } from 'react';
import { useGame } from '../contexts/GameContext';
import type { PlayerStatistics } from '../api/types';
import { Header } from '../components/Header';
import WinRateChart from '../components/statistics/WinRateChart';
import EarningsChart from '../components/statistics/EarningsChart';
import CostsChart from '../components/statistics/CostsChart';
import FrequencyChart from '../components/statistics/FrequencyChart';
import PerformanceRadar from '../components/statistics/PerformanceRadar';
import TopContentTable from '../components/statistics/TopContentTable';

const Statistics: React.FC = () => {
  const { actions } = useGame();
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
        const statisticsData = await getStatistics(controller.signal);
        setData(statisticsData);
        // Give the DOM a moment to settle before rendering charts
        setTimeout(() => setChartsReady(true), 100);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        setError('Failed to load statistics. Please try again.');
      } finally {
        setLoading(false);
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
            <div>
              <h1 className="text-3xl font-display font-bold text-quip-navy">{data.username}'s Statistics</h1>
              <p className="text-quip-teal mt-1">{data.email}</p>
              <p className="text-quip-teal text-sm mt-1">Track your performance and progress</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-quip-teal">Current Balance</div>
              <div className="text-3xl font-bold text-quip-orange">${data.overall_balance}</div>
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

          {/* Costs Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Costs Breakdown</h2>
            {chartsReady ? (
              <CostsChart earnings={data.earnings} />
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
