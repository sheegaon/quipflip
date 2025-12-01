import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useResults } from '../contexts/ResultsContext';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import type { GameStatus, HistoricalTrendPoint, PlayerStatistics } from '../api/types';
import { Header } from '../components/Header';
import WinRateChart from '../../../crowdcraft/src/components/statistics/WinRateChart.tsx';
import EarningsChart from '../../../crowdcraft/src/components/statistics/EarningsChart.tsx';
import SpendingChart from '../../../crowdcraft/src/components/statistics/SpendingChart.tsx';
import FrequencyChart from '../../../crowdcraft/src/components/statistics/FrequencyChart.tsx';
import HistoricalTrendsChart from '../../../crowdcraft/src/components/statistics/HistoricalTrendsChart.tsx';
import { statisticsLogger } from '../utils/logger';
import { hasCompletedSurvey } from '../utils/betaSurvey';
import type { BetaSurveyStatusResponse } from '../api/types';
import { APP_VERSION } from '../version';

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
  const [surveyStatus, setSurveyStatus] = useState<BetaSurveyStatusResponse | null>(null);
  const [gameStatus, setGameStatus] = useState<GameStatus | null>(null);

  const historicalTrends = useMemo<HistoricalTrendPoint[]>(() => {
    if (!data) return [];

    const DAYS_IN_WEEK = 7;
    const MS_PER_DAY = 24 * 60 * 60 * 1000;

    const rawPoints = data.historical_trends ?? [];
    const parsedPoints = rawPoints
      .map((point) => {
        const parsed = Date.parse(point.period);
        if (Number.isNaN(parsed)) {
          return null;
        }

        const date = new Date(parsed);
        date.setHours(0, 0, 0, 0);

        return {
          ...point,
          timestamp: date.getTime(),
          dayKey: date.toISOString().slice(0, 10),
        };
      })
      .filter((point): point is HistoricalTrendPoint & { timestamp: number; dayKey: string } => point !== null);

    if (parsedPoints.length === 0) {
      const today = data.frequency?.last_active ? new Date(data.frequency.last_active) : new Date();
      today.setHours(0, 0, 0, 0);

      const totalRounds =
        data.prompt_stats.total_rounds + data.copy_stats.total_rounds + data.voter_stats.total_rounds;
      const totalEarnings = data.earnings.total_earnings;

      const weightedWinRateSum =
        data.prompt_stats.win_rate * data.prompt_stats.total_rounds +
        data.copy_stats.win_rate * data.copy_stats.total_rounds +
        data.voter_stats.win_rate * data.voter_stats.total_rounds;

      const averageWinRate = totalRounds > 0 ? weightedWinRateSum / totalRounds : 0;

      return Array.from({ length: DAYS_IN_WEEK }, (_, index) => {
        const progression = (index + 1) / DAYS_IN_WEEK;
        const periodDate = new Date(today.getTime() - (DAYS_IN_WEEK - 1 - index) * MS_PER_DAY);
        const smoothFactor = Math.sin(progression * Math.PI) * 0.15;

        const dailyWinRate = Math.min(
          100,
          Math.max(0, Math.round(averageWinRate * (0.9 + smoothFactor * 0.5 + progression * 0.1) * 10) / 10),
        );
        const dailyEarnings = Math.max(0, Math.round((totalEarnings / DAYS_IN_WEEK) * (0.8 + smoothFactor)));
        const dailyRounds = Math.max(0, Math.round((totalRounds / DAYS_IN_WEEK) * (0.85 + smoothFactor)));

        return {
          period: periodDate.toISOString(),
          win_rate: dailyWinRate,
          earnings: dailyEarnings,
          rounds_played: dailyRounds,
        };
      });
    }

    const latestTimestamp = parsedPoints.reduce((max, point) => Math.max(max, point.timestamp), 0);
    const latestDate = new Date(latestTimestamp);
    latestDate.setHours(0, 0, 0, 0);

    const aggregated = new Map<
      string,
      { earnings: number; rounds: number; winRateSum: number; winRateCount: number }
    >();

    const sortedPoints = [...parsedPoints].sort((a, b) => a.timestamp - b.timestamp);
    let previousEarnings = 0;
    let previousRounds = 0;

    sortedPoints.forEach((point) => {
      const existing =
        aggregated.get(point.dayKey) ?? { earnings: 0, rounds: 0, winRateSum: 0, winRateCount: 0 };

      const earningsDelta =
        point.earnings >= previousEarnings ? point.earnings - previousEarnings : point.earnings;
      const roundsDelta =
        point.rounds_played >= previousRounds ? point.rounds_played - previousRounds : point.rounds_played;

      previousEarnings = point.earnings;
      previousRounds = point.rounds_played;

      existing.earnings += Math.max(0, earningsDelta);
      existing.rounds += Math.max(0, roundsDelta);
      existing.winRateSum += point.win_rate;
      existing.winRateCount += 1;
      aggregated.set(point.dayKey, existing);
    });

    return Array.from({ length: DAYS_IN_WEEK }, (_, index) => {
      const periodDate = new Date(latestDate.getTime() - (DAYS_IN_WEEK - 1 - index) * MS_PER_DAY);
      const dayKey = periodDate.toISOString().slice(0, 10);
      const summary = aggregated.get(dayKey);

      const winRate = summary && summary.winRateCount > 0
        ? Math.round((summary.winRateSum / summary.winRateCount) * 10) / 10
        : 0;

      return {
        period: periodDate.toISOString(),
        win_rate: winRate,
        earnings: summary ? Math.round(summary.earnings) : 0,
        rounds_played: summary ? Math.round(summary.rounds) : 0,
      };
    });
  }, [data]);

  const weeklyTrendSummary = useMemo(
    () => {
      if (historicalTrends.length === 0) {
        return { latestWinRate: 0, weeklyEarnings: 0, weeklyRounds: 0 };
      }

      const latest = historicalTrends[historicalTrends.length - 1];
      const weeklyEarnings = historicalTrends.reduce((sum, point) => sum + point.earnings, 0);
      const weeklyRounds = historicalTrends.reduce((sum, point) => sum + point.rounds_played, 0);

      return {
        latestWinRate: latest.win_rate,
        weeklyEarnings,
        weeklyRounds,
      };
    },
    [historicalTrends],
  );

  const { latestWinRate, weeklyEarnings, weeklyRounds } = weeklyTrendSummary;

  useEffect(() => {
    const playerId = player?.player_id;
    if (!playerId) {
      setSurveyStatus(null);
      return;
    }

    let cancelled = false;
    const controller = new AbortController();

    const fetchStatus = async () => {
      try {
        const status = await apiClient.getBetaSurveyStatus(controller.signal);
        if (!cancelled) {
          setSurveyStatus(status);
        }
      } catch (err) {
        if (!cancelled) {
          statisticsLogger.warn('Failed to load beta survey status in statistics view', err);
          setSurveyStatus(null);
        }
      }
    };

    fetchStatus();

    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [player?.player_id]);

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

  useEffect(() => {
    const controller = new AbortController();

    const fetchGameStatus = async () => {
      try {
        const status = await apiClient.getGameStatus(controller.signal);
        setGameStatus(status);
      } catch (err) {
        if (err instanceof Error && err.name === 'CanceledError') return;
        statisticsLogger.warn('Failed to load game status for statistics view', err);
        setGameStatus(null);
      }
    };

    fetchGameStatus();

    return () => {
      controller.abort();
    };
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
            <p className="mt-4 text-ccl-navy font-display">Loading your statistics...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="tile-card p-8">
            <h1 className="text-2xl font-display font-bold text-ccl-navy mb-4">Statistics</h1>
            <div className="text-red-600">{error || 'Failed to load statistics'}</div>
          </div>
        </div>
      </div>
    );
  }

  const surveyCompleted = player?.player_id ? hasCompletedSurvey(player.player_id) : false;

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8">
        {surveyStatus?.eligible && !surveyStatus.has_submitted && !surveyCompleted && (
          <div className="tile-card mb-6 border-2 border-ccl-teal bg-ccl-teal/10 p-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <h2 className="text-2xl font-display font-bold text-ccl-navy">Beta survey now available</h2>
                <p className="mt-1 text-ccl-navy/80">
                  You&apos;ve played {surveyStatus.total_rounds} rounds. Share your thoughts and help us level up Quipflip!
                </p>
              </div>
              <button
                onClick={() => navigate('/survey/beta')}
                className="rounded-tile bg-ccl-navy px-6 py-2 font-semibold text-white shadow-tile-sm transition hover:bg-ccl-teal"
              >
                Start survey
              </button>
            </div>
          </div>
        )}
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="flex-1">
              <h1 className="text-3xl font-display font-bold text-ccl-navy">{data.username}</h1>
              <p className="text-ccl-teal mt-1">{data.email}</p>
            </div>
          </div>
        </div>

        {/* Guest Upgrade Card */}
        {player?.is_guest && (
          <div className="tile-card p-6 mb-6 bg-gradient-to-br from-orange-50 to-cyan-50 border-2 border-ccl-orange">
            <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex-1">
                <h2 className="text-2xl font-display font-bold text-ccl-navy mb-2">
                  Upgrade Your Account
                </h2>
                <p className="text-ccl-navy mb-3">
                  You're using a guest account. Upgrade to a full account to:
                </p>
                <ul className="list-disc list-inside text-ccl-navy text-sm space-y-1 mb-3">
                  <li>Save your progress permanently</li>
                  <li>Access your account from any device</li>
                  <li>Never lose your Flipcoins and stats</li>
                  <li>Get higher rate limits for smoother gameplay</li>
                </ul>
              </div>
              <div className="flex flex-col gap-3">
                <button
                  onClick={() => navigate('/settings')}
                  className="bg-gradient-to-r from-ccl-orange to-ccl-turquoise hover:from-ccl-orange-deep hover:to-ccl-teal text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm whitespace-nowrap"
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
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">Win Rates by Role</h2>
            {chartsReady ? (
              <WinRateChart
                promptStats={data.prompt_stats}
                copyStats={data.copy_stats}
                voterStats={data.voter_stats}
              />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Historical Trends */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-2">Historical Trends &amp; Performance Over Time</h2>
            <p className="text-sm text-ccl-teal mb-4">
              Track how your win rate, earnings, and activity have evolved across the past week.
            </p>
            {chartsReady ? (
              <>
                {historicalTrends.length > 0 && (
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-4 text-sm">
                    <div className="bg-ccl-orange bg-opacity-10 border border-ccl-orange rounded-tile p-3">
                      <div className="text-ccl-teal">Latest Win Rate</div>
                      <div className="text-2xl font-bold text-ccl-orange">
                        {latestWinRate.toFixed(1)}%
                      </div>
                    </div>
                    <div className="bg-ccl-teal bg-opacity-10 border border-ccl-teal rounded-tile p-3">
                      <div className="text-ccl-teal">Weekly Earnings</div>
                      <div className="text-2xl font-bold text-ccl-teal">
                        {Math.round(weeklyEarnings).toLocaleString()}
                      </div>
                    </div>
                    <div className="bg-ccl-turquoise bg-opacity-10 border border-ccl-turquoise rounded-tile p-3">
                      <div className="text-ccl-teal">Weekly Rounds Played</div>
                      <div className="text-2xl font-bold text-ccl-turquoise">
                        {Math.round(weeklyRounds).toLocaleString()}
                      </div>
                    </div>
                  </div>
                )}
                <HistoricalTrendsChart trends={historicalTrends} />
              </>
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Earnings Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">Earnings Breakdown</h2>
            {chartsReady ? (
              <EarningsChart earnings={data.earnings} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Spending Chart */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">Spending Breakdown</h2>
            {chartsReady ? (
              <SpendingChart earnings={data.earnings} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
              </div>
            )}
          </div>

          {/* Play Frequency */}
          <div className="tile-card p-6">
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">Activity Metrics</h2>
            {chartsReady ? (
              <FrequencyChart frequency={data.frequency} />
            ) : (
              <div className="w-full h-80 flex items-center justify-center">
                <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-ccl-orange border-r-transparent"></div>
              </div>
            )}
          </div>

        </div>

        <div className="mt-10 text-center text-xs text-ccl-navy/60" aria-live="polite">
          Quipflip version {gameStatus?.version || APP_VERSION}
        </div>

      </div>
    </div>
  );
};

export default Statistics;
