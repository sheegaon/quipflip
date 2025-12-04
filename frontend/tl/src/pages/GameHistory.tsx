import React, { useCallback, useEffect, useMemo, useState } from 'react';
import apiClient from '@crowdcraft/api/client.ts';
import type { TLRoundDetails, TLRoundHistoryItem, TLRoundHistoryQuery } from '@crowdcraft/api/types.ts';
import { useGame } from '../contexts/GameContext';

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  return new Date(value).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  });
};

const formatCoverage = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(1)}%`;
};

const formatPayout = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return `${value} coins`;
};

const defaultFilterForm = {
  sort_by: 'date',
  sort_direction: 'desc',
  min_coverage: '',
  max_coverage: '',
  min_payout: '',
  max_payout: '',
  start_date: '',
  end_date: '',
};

const normalizeDate = (value: string, endOfDay?: boolean) => {
  if (!value) return undefined;

  if (endOfDay) {
    return new Date(`${value}T23:59:59.999Z`).toISOString();
  }

  return new Date(`${value}T00:00:00.000Z`).toISOString();
};

const GameHistory: React.FC = () => {
  const { state } = useGame();
  const [rounds, setRounds] = useState<TLRoundHistoryItem[]>([]);
  const [selectedRoundId, setSelectedRoundId] = useState<string | null>(null);
  const [roundDetails, setRoundDetails] = useState<TLRoundDetails | null>(null);
  const [historyFilters, setHistoryFilters] = useState(defaultFilterForm);
  const [appliedFilters, setAppliedFilters] = useState<TLRoundHistoryQuery>({
    sort_by: 'date',
    sort_direction: 'desc',
  });
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [loadingDetails, setLoadingDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(
    async (signal?: AbortSignal) => {
      if (!state.isAuthenticated) return;

      setLoadingHistory(true);
      setError(null);

      try {
        const response = await apiClient.tlGetRoundHistory(appliedFilters, signal);
        setRounds(response.rounds);

        if (!selectedRoundId && response.rounds.length > 0) {
          setSelectedRoundId(response.rounds[0].round_id);
        } else if (
          selectedRoundId &&
          response.rounds.length > 0 &&
          !response.rounds.find(round => round.round_id === selectedRoundId)
        ) {
          // Selected round is no longer in the filtered results
          setSelectedRoundId(response.rounds[0].round_id);
        }
      } catch (err) {
        console.error('Failed to load game history', err);
        setError('Unable to load your game history right now. Please try again later.');
      } finally {
        setLoadingHistory(false);
      }
    },
    [appliedFilters, selectedRoundId, state.isAuthenticated],
  );

  const fetchRoundDetails = useCallback(
    async (roundId: string, signal?: AbortSignal) => {
      if (!state.isAuthenticated) return;

      setLoadingDetails(true);
      setError(null);

      try {
        const response = await apiClient.tlGetRoundDetails(roundId, signal);
        setRoundDetails(response);
      } catch (err) {
        console.error('Failed to load round details', err);
        setError('Unable to load round details. Please try again later.');
      } finally {
        setLoadingDetails(false);
      }
    },
    [state.isAuthenticated],
  );

  useEffect(() => {
    const controller = new AbortController();
    fetchHistory(controller.signal);

    return () => controller.abort();
  }, [fetchHistory]);

  useEffect(() => {
    if (!selectedRoundId) {
      setRoundDetails(null);
      return;
    }

    const controller = new AbortController();
    fetchRoundDetails(selectedRoundId, controller.signal);

    return () => controller.abort();
  }, [fetchRoundDetails, selectedRoundId]);

  const applyFilters = () => {
    const nextFilters: TLRoundHistoryQuery = {
      sort_by: historyFilters.sort_by as TLRoundHistoryQuery['sort_by'],
      sort_direction: historyFilters.sort_direction as TLRoundHistoryQuery['sort_direction'],
    };

    if (historyFilters.min_coverage !== '') {
      nextFilters.min_coverage = Number(historyFilters.min_coverage) / 100;
    }

    if (historyFilters.max_coverage !== '') {
      nextFilters.max_coverage = Number(historyFilters.max_coverage) / 100;
    }

    if (historyFilters.min_payout !== '') {
      nextFilters.min_payout = Number(historyFilters.min_payout);
    }

    if (historyFilters.max_payout !== '') {
      nextFilters.max_payout = Number(historyFilters.max_payout);
    }

    if (historyFilters.start_date) {
      nextFilters.start_date = normalizeDate(historyFilters.start_date);
    }

    if (historyFilters.end_date) {
      nextFilters.end_date = normalizeDate(historyFilters.end_date, true);
    }

    setAppliedFilters(nextFilters);
  };

  const resetFilters = () => {
    setHistoryFilters(defaultFilterForm);
    setAppliedFilters({ sort_by: 'date', sort_direction: 'desc' });
  };

  const selectedSummary = useMemo(
    () => rounds.find(round => round.round_id === selectedRoundId) ?? null,
    [rounds, selectedRoundId],
  );

  return state.isAuthenticated ? (
    <div className="min-h-screen bg-ccl-cream p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col gap-2">
          <h1 className="text-3xl font-bold text-ccl-navy">Game History</h1>
          <p className="text-gray-600">Review your past ThinkLink rounds and performance.</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
            {error}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1 space-y-6">
            <div className="bg-white rounded-lg shadow p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800">Filters & Sorting</h2>
                  <p className="text-sm text-gray-500">Find rounds by payout, coverage, or date.</p>
                </div>
                <button
                  type="button"
                  onClick={resetFilters}
                  className="text-sm text-ccl-orange hover:text-ccl-orange-dark"
                >
                  Reset
                </button>
              </div>

              <div className="grid grid-cols-1 gap-3">
                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm text-gray-700">
                    Sort by
                    <select
                      value={historyFilters.sort_by}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, sort_by: e.target.value }))}
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    >
                      <option value="date">Date</option>
                      <option value="payout">Payout</option>
                      <option value="coverage">Coverage</option>
                    </select>
                  </label>

                  <label className="text-sm text-gray-700">
                    Order
                    <select
                      value={historyFilters.sort_direction}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, sort_direction: e.target.value }))}
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    >
                      <option value="desc">Newest first</option>
                      <option value="asc">Oldest first</option>
                    </select>
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm text-gray-700">
                    Min coverage (%)
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      value={historyFilters.min_coverage}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, min_coverage: e.target.value }))}
                      placeholder="0"
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>

                  <label className="text-sm text-gray-700">
                    Max coverage (%)
                    <input
                      type="number"
                      min={0}
                      max={100}
                      step={1}
                      value={historyFilters.max_coverage}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, max_coverage: e.target.value }))}
                      placeholder="100"
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm text-gray-700">
                    Min payout
                    <input
                      type="number"
                      min={0}
                      value={historyFilters.min_payout}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, min_payout: e.target.value }))}
                      placeholder="0"
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>

                  <label className="text-sm text-gray-700">
                    Max payout
                    <input
                      type="number"
                      min={0}
                      value={historyFilters.max_payout}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, max_payout: e.target.value }))}
                      placeholder="300"
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <label className="text-sm text-gray-700">
                    From date
                    <input
                      type="date"
                      value={historyFilters.start_date}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, start_date: e.target.value }))}
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>

                  <label className="text-sm text-gray-700">
                    To date
                    <input
                      type="date"
                      value={historyFilters.end_date}
                      onChange={e => setHistoryFilters(prev => ({ ...prev, end_date: e.target.value }))}
                      className="mt-1 w-full rounded-md border border-gray-200 p-2 text-sm focus:border-ccl-orange focus:ring-1 focus:ring-ccl-orange"
                    />
                  </label>
                </div>

                <button
                  type="button"
                  onClick={applyFilters}
                  className="w-full rounded-md bg-ccl-orange px-4 py-2 text-white font-semibold shadow hover:bg-ccl-orange-dark transition"
                  disabled={loadingHistory}
                >
                  {loadingHistory ? 'Applying...' : 'Apply filters'}
                </button>
              </div>
            </div>

            <div className="bg-white rounded-lg shadow p-6">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800">Your rounds</h2>
                  <p className="text-sm text-gray-500">Select a round to view the full breakdown.</p>
                </div>
                <div className="text-xs text-gray-500">{rounds.length} results</div>
              </div>

              {loadingHistory ? (
                <div className="py-8 text-center text-gray-500">Loading your rounds...</div>
              ) : rounds.length === 0 ? (
                <div className="py-8 text-center text-gray-500">
                  No past rounds found. Play a round to see your history here.
                </div>
              ) : (
                <div className="space-y-3">
                  {rounds.map(round => {
                    const isSelected = selectedRoundId === round.round_id;

                    return (
                      <button
                        key={round.round_id}
                        type="button"
                        onClick={() => setSelectedRoundId(round.round_id)}
                        className={`w-full rounded-lg border p-4 text-left transition hover:border-ccl-orange ${
                          isSelected ? 'border-ccl-orange bg-orange-50' : 'border-gray-200 bg-white'
                        }`}
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-ccl-navy truncate">{round.prompt_text}</p>
                            <p className="text-xs text-gray-500">{formatDate(round.created_at)}</p>
                          </div>
                          <span
                            className={`text-xs font-semibold px-2 py-1 rounded-full ${
                              round.status === 'completed'
                                ? 'bg-green-50 text-green-700'
                                : 'bg-yellow-50 text-yellow-700'
                            }`}
                          >
                            {round.status}
                          </span>
                        </div>

                        <div className="mt-3 grid grid-cols-3 gap-2 text-sm">
                          <div>
                            <p className="text-gray-500 text-xs">Coverage</p>
                            <p className="font-semibold text-ccl-navy">{formatCoverage(round.final_coverage)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs">Payout</p>
                            <p className="font-semibold text-ccl-navy">{formatPayout(round.gross_payout)}</p>
                          </div>
                          <div>
                            <p className="text-gray-500 text-xs">Strikes</p>
                            <p className="font-semibold text-ccl-navy">{round.strikes}</p>
                          </div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              )}
            </div>
          </div>

          <div className="lg:col-span-2">
            <div className="bg-white rounded-lg shadow p-6 min-h-[300px]">
              <div className="flex items-center justify-between mb-4">
                <div>
                  <h2 className="text-lg font-semibold text-gray-800">Round details</h2>
                  <p className="text-sm text-gray-500">Full breakdown for the selected round.</p>
                </div>
                {selectedSummary && (
                  <span className="text-xs font-semibold px-2 py-1 rounded-full bg-gray-100 text-gray-700 capitalize">
                    {selectedSummary.status}
                  </span>
                )}
              </div>

              {!selectedRoundId && (
                <div className="py-10 text-center text-gray-500">Select a round to view details.</div>
              )}

              {loadingDetails && selectedRoundId && (
                <div className="py-10 text-center text-gray-500">Loading round details...</div>
              )}

              {!loadingDetails && selectedRoundId && roundDetails && (
                <div className="space-y-4">
                  <div className="p-4 bg-orange-50 border border-ccl-orange/30 rounded-lg">
                    <p className="text-sm text-gray-600">Prompt</p>
                    <p className="text-lg font-semibold text-ccl-navy">{roundDetails.prompt_text}</p>
                  </div>

                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Coverage</p>
                      <p className="text-xl font-bold text-ccl-navy">{formatCoverage(roundDetails.final_coverage)}</p>
                    </div>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Payout</p>
                      <p className="text-xl font-bold text-ccl-navy">{formatPayout(roundDetails.gross_payout)}</p>
                    </div>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Strikes used</p>
                      <p className="text-xl font-bold text-ccl-navy">{roundDetails.strikes}</p>
                    </div>
                    <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
                      <p className="text-xs text-gray-500">Snapshot size</p>
                      <p className="text-xl font-bold text-ccl-navy">{roundDetails.snapshot_answer_count}</p>
                    </div>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="border border-gray-200 rounded-lg p-4">
                      <p className="text-xs text-gray-500">Started</p>
                      <p className="font-semibold text-ccl-navy">{formatDate(roundDetails.created_at)}</p>
                    </div>
                    <div className="border border-gray-200 rounded-lg p-4">
                      <p className="text-xs text-gray-500">Completed</p>
                      <p className="font-semibold text-ccl-navy">{formatDate(roundDetails.ended_at)}</p>
                    </div>
                  </div>

                  <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                    <p className="text-xs text-gray-500 mb-2">Matched clusters</p>
                    <p className="text-sm text-ccl-navy">
                      {roundDetails.matched_clusters.length > 0
                        ? `${roundDetails.matched_clusters.length} clusters hit`
                        : 'No clusters matched'}
                    </p>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  ) : (
    <div className="p-8 text-center text-gray-500">
      Please log in to view your game history.
    </div>
  );
};

export default GameHistory;
