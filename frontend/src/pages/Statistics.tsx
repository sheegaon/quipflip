import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
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
  const navigate = useNavigate();

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
            <div className="text-red-600 mb-4">{error || 'Failed to load statistics'}</div>
            <button
              onClick={() => navigate('/dashboard')}
              className="px-4 py-2 bg-quip-orange hover:bg-quip-orange-deep text-white rounded-tile transition-all hover:shadow-tile-sm font-bold"
            >
              Back to Dashboard
            </button>
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
              <p className="text-quip-teal mt-1">Track your performance and progress</p>
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
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-quip-teal">Total Rounds Played</span>
                <span className="text-2xl font-bold text-quip-navy">
                  {stats.frequency.total_rounds_played}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-quip-teal">Days Active</span>
                <span className="text-2xl font-bold text-quip-navy">{stats.frequency.days_active}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-quip-teal">Rounds per Day</span>
                <span className="text-2xl font-bold text-quip-navy">
                  {stats.frequency.rounds_per_day.toFixed(1)}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-quip-teal">Member Since</span>
                <span className="text-sm font-medium text-quip-navy">
                  {new Date(stats.frequency.member_since).toLocaleDateString()}
                </span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-quip-teal">Last Active</span>
                <span className="text-sm font-medium text-quip-navy">
                  {new Date(stats.frequency.last_active).toLocaleDateString()}
                </span>
              </div>
            </div>
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

        {/* Back Button */}
        <div className="text-center">
          <button
            onClick={() => navigate('/dashboard')}
            className="px-6 py-3 bg-quip-navy hover:bg-quip-teal text-white rounded-tile transition-all hover:shadow-tile-sm font-bold"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
}
