import { useState, useEffect } from 'react';
import { apiClient } from '../api/client';
import type { PlayerStatistics } from '../api/types';
import { Header } from '../components/Header';
import WinRateChart from '../components/statistics/WinRateChart';
import EarningsChart from '../components/statistics/EarningsChart';
import FrequencyChart from '../components/statistics/FrequencyChart';
import PerformanceRadar from '../components/statistics/PerformanceRadar';
import TopContentTable from '../components/statistics/TopContentTable';

export default function Statistics() {
  const [stats, setStats] = useState<PlayerStatistics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    const fetchStatistics = async () => {
      try {
        setLoading(true);
        setError(null);
        const data = await apiClient.getStatistics(controller.signal);
        setStats(data);
      } catch (err: any) {
        if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
          setError('Failed to load statistics. Please try again.');
          console.error('Failed to fetch statistics:', err);
        }
      } finally {
        setLoading(false);
      }
    };

    fetchStatistics();

    return () => {
      controller.abort();
    };
  }, []);

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

  if (error || !stats) {
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
              <h1 className="text-3xl font-display font-bold text-quip-navy">{stats.username}'s Statistics</h1>
              <p className="text-quip-teal mt-1">{stats.email}</p>
              <p className="text-quip-teal text-sm mt-1">Track your performance and progress</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-quip-teal">Current Balance</div>
              <div className="text-3xl font-bold text-quip-orange">${stats.overall_balance}</div>
            </div>
          </div>
        </div>

        {/* Charts Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Win Rate Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Win Rates by Role</h2>
            <WinRateChart
              promptStats={stats.prompt_stats}
              copyStats={stats.copy_stats}
              voterStats={stats.voter_stats}
            />
          </div>

          {/* Earnings Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Earnings Breakdown</h2>
            <EarningsChart earnings={stats.earnings} />
          </div>

          {/* Performance Radar */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Role Performance</h2>
            <PerformanceRadar
              promptStats={stats.prompt_stats}
              copyStats={stats.copy_stats}
              voterStats={stats.voter_stats}
            />
          </div>

          {/* Play Frequency */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Activity Metrics</h2>
            <FrequencyChart frequency={stats.frequency} />
          </div>
        </div>

        {/* Top Content Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
          {/* Favorite Prompts */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Top Earning Prompts</h2>
            <TopContentTable
              items={stats.favorite_prompts.map((prompt) => ({ text: prompt }))}
              emptyMessage="No prompts yet. Start a prompt round to earn!"
            />
          </div>

          {/* Best Performing Phrases */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Best Performing Phrases</h2>
            <TopContentTable
              items={stats.best_performing_phrases.map((phrase) => ({
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
}
