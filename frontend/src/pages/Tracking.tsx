import React, { useCallback, useEffect, useMemo, useState, useRef } from 'react';
import apiClient, { extractErrorMessage } from '../api/client';
import type {
  PhrasesetSummary,
  PhrasesetDetails as PhrasesetDetailsType,
} from '../api/types';
import { useGame } from '../contexts/GameContext';
import { PhrasesetList } from '../components/PhrasesetList';
import { PhrasesetDetails } from '../components/PhrasesetDetails';
import { Header } from '../components/Header';

type RoleFilter = 'all' | 'prompt' | 'copy';
type StatusFilter = 'all' | 'in_progress' | 'voting' | 'finalized' | 'abandoned';

const roleOptions: { value: RoleFilter; label: string }[] = [
  { value: 'all', label: 'All Roles' },
  { value: 'prompt', label: 'Prompts' },
  { value: 'copy', label: 'Copies' },
];

const statusOptions: { value: StatusFilter; label: string }[] = [
  { value: 'all', label: 'All Statuses' },
  { value: 'in_progress', label: 'In Progress' },
  { value: 'voting', label: 'Voting' },
  { value: 'finalized', label: 'Finalized' },
  { value: 'abandoned', label: 'Abandoned' },
];

export const Tracking: React.FC = () => {
  const {
    player,
    refreshBalance,
    refreshDashboard,
    phrasesetSummary,
  } = useGame();

  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [phrasesets, setPhrasesets] = useState<PhrasesetSummary[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [selectedSummary, setSelectedSummary] = useState<PhrasesetSummary | null>(null);
  const [details, setDetails] = useState<PhrasesetDetailsType | null>(null);
  const [listLoading, setListLoading] = useState(false);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [claiming, setClaiming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [infoExpanded, setInfoExpanded] = useState(false);

  // Store the last fetched details to compare for changes
  const lastDetailsRef = useRef<PhrasesetDetailsType | null>(null);

  const fetchPhrasesets = useCallback(async (signal?: AbortSignal) => {
    setListLoading(true);
    try {
      const data = await apiClient.getPlayerPhrasesets({
        role: roleFilter,
        status: statusFilter,
        limit: 100,
        offset: 0,
      }, signal);
      setPhrasesets(data.phrasesets);
      if (data.phrasesets.length > 0) {
        // Preserve selected item if it still exists in the new list
        const currentlySelected = data.phrasesets.find((item) =>
          item.phraseset_id ? item.phraseset_id === selectedId : item.prompt_round_id === selectedId
        );

        if (currentlySelected) {
          // Keep the current selection
          setSelectedSummary(currentlySelected);
        } else if (!selectedId) {
          // No previous selection, select first item
          const first = data.phrasesets[0];
          const id = first.phraseset_id ?? first.prompt_round_id;
          setSelectedId(id);
          setSelectedSummary(first);
        }
      } else {
        setSelectedId(null);
        setSelectedSummary(null);
        setDetails(null);
      }
      setError(null);
    } catch (err: any) {
      if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
        setError(extractErrorMessage(err) || 'Unable to load your past rounds. Please refresh the page or try again in a moment.');
      }
    } finally {
      setListLoading(false);
    }
  }, [roleFilter, statusFilter, selectedId]);

  const fetchDetails = useCallback(async (phraseset: PhrasesetSummary | null, signal?: AbortSignal) => {
    if (!phraseset || !phraseset.phraseset_id) {
      setDetails(null);
      lastDetailsRef.current = null;
      return;
    }
    setDetailsLoading(true);
    try {
      const data = await apiClient.getPhrasesetDetails(phraseset.phraseset_id, signal);

      // Only update state if the data has actually changed
      const hasChanged = !lastDetailsRef.current ||
        JSON.stringify(lastDetailsRef.current) !== JSON.stringify(data);

      if (hasChanged) {
        setDetails(data);
        lastDetailsRef.current = data;
      }

      setError(null);
    } catch (err: any) {
      if (err.name !== 'AbortError' && err.code !== 'ERR_CANCELED') {
        setError(extractErrorMessage(err) || 'Unable to load the details for this round. It may no longer be available.');
      }
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    fetchPhrasesets(controller.signal);

    return () => {
      controller.abort();
    };
  }, [fetchPhrasesets]);

  useEffect(() => {
    if (!selectedSummary) return;

    const controller = new AbortController();
    fetchDetails(selectedSummary, controller.signal);

    return () => {
      controller.abort();
    };
  }, [selectedSummary, fetchDetails]);

  // Poll details every 60 seconds when phraseset is active (reduced from 10 seconds)
  useEffect(() => {
    if (!selectedSummary?.phraseset_id) return;
    if (details?.status === 'finalized') return;

    const interval = setInterval(() => {
      fetchDetails(selectedSummary);
    }, 60000); // Changed from 10000 to 60000 (60 seconds)

    return () => clearInterval(interval);
  }, [selectedSummary, details?.status, fetchDetails]);

  const handleSelect = (summary: PhrasesetSummary) => {
    const id = summary.phraseset_id ?? summary.prompt_round_id;
    setSelectedId(id);
    setSelectedSummary(summary);
  };

  const handleClaim = async (phrasesetId: string) => {
    setClaiming(true);
    try {
      await apiClient.claimPhrasesetPrize(phrasesetId);
      await Promise.all([
        fetchDetails(selectedSummary),
        fetchPhrasesets(),
        refreshBalance(),
        refreshDashboard(),
      ]);
      setError(null);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to claim prize');
    } finally {
      setClaiming(false);
    }
  };

  const totalTracked = useMemo(() => phrasesets.length, [phrasesets.length]);

  if (!player) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center">
        <div className="text-xl">Loading...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />

      <div className="max-w-6xl mx-auto px-4 py-8 space-y-6">
        <div>
          <h1 className="text-2xl font-display font-bold text-quip-navy">Past Round Tracking</h1>
          <p className="text-sm text-quip-teal">
            Monitor your quips throughout the game lifecycle.
          </p>
        </div>

        {phrasesetSummary && (
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="tile-card p-4">
              <p className="text-xs uppercase text-quip-teal font-medium">In Progress</p>
              <p className="text-lg font-display font-semibold text-quip-navy">
                {phrasesetSummary.in_progress.prompts} prompt
                {phrasesetSummary.in_progress.prompts === 1 ? '' : 's'} &nbsp;•&nbsp;
                {phrasesetSummary.in_progress.copies} cop
                {phrasesetSummary.in_progress.copies === 1 ? 'y' : 'ies'}
              </p>
            </div>
            <div className="tile-card p-4">
              <p className="text-xs uppercase text-quip-teal font-medium">Finalized</p>
              <p className="text-lg font-display font-semibold text-quip-navy">
                {phrasesetSummary.finalized.prompts} prompt
                {phrasesetSummary.finalized.prompts === 1 ? '' : 's'} &nbsp;•&nbsp;
                {phrasesetSummary.finalized.copies} cop
                {phrasesetSummary.finalized.copies === 1 ? 'y' : 'ies'}
              </p>
            </div>
            <div className="tile-card p-4 bg-quip-turquoise bg-opacity-10">
              <p className="text-xs uppercase text-quip-teal font-medium">Unclaimed</p>
              <p className="text-lg font-display font-semibold text-quip-turquoise">
                ${phrasesetSummary.total_unclaimed_amount}
              </p>
            </div>
          </div>
        )}

        <div className="tile-card p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex flex-wrap gap-3">
              <label className="text-sm text-gray-700 flex items-center gap-2">
                Role
                <select
                  value={roleFilter}
                  onChange={(event) => setRoleFilter(event.target.value as RoleFilter)}
                  className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                >
                  {roleOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="text-sm text-gray-700 flex items-center gap-2">
                Status
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value as StatusFilter)}
                  className="border border-gray-300 rounded-md px-2 py-1 text-sm"
                >
                  {statusOptions.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="text-sm text-gray-600">
              Showing {totalTracked} round{totalTracked === 1 ? '' : 's'}
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="min-w-0 lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Your Past Rounds</h2>
              <PhrasesetList
                phrasesets={phrasesets}
                selectedId={selectedId}
                onSelect={handleSelect}
                isLoading={listLoading}
              />
            </div>
          </div>
          <div className="min-w-0 lg:col-span-2">
            <PhrasesetDetails
              phraseset={details}
              summary={selectedSummary}
              loading={detailsLoading}
              claiming={claiming}
              onClaim={handleClaim}
            />
          </div>
        </div>

        {/* Collapsible Info Section */}
        <div className="tile-card overflow-hidden">
          <button
            onClick={() => setInfoExpanded(!infoExpanded)}
            className="w-full p-4 flex items-center justify-between hover:bg-quip-cream hover:bg-opacity-30 transition-colors"
          >
            <div className="flex items-center gap-3">
              <svg className="w-5 h-5 text-quip-teal flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <span className="text-sm font-semibold text-quip-navy">
                How does voting priority work?
              </span>
            </div>
            <svg
              className={`w-5 h-5 text-quip-teal transition-transform ${infoExpanded ? 'rotate-180' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          {infoExpanded && (
            <div className="px-4 pb-4 pt-2 border-t border-gray-100">
              <div className="text-sm text-gray-700 space-y-3">
                <p>
                  When voters request a round, phrasesets are prioritized to ensure fair and timely completion:
                </p>

                <div className="space-y-2">
                  <div className="flex gap-2">
                    <span className="font-semibold text-quip-turquoise min-w-[3rem]">High:</span>
                    <span>Phrasesets with <strong>5+ votes</strong> (FIFO from 5th vote timestamp)</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-semibold text-quip-teal min-w-[3rem]">Medium:</span>
                    <span>Phrasesets with <strong>3-4 votes</strong> (FIFO from 3rd vote timestamp)</span>
                  </div>
                  <div className="flex gap-2">
                    <span className="font-semibold text-gray-500 min-w-[3rem]">Low:</span>
                    <span>Phrasesets with <strong>0-2 votes</strong> (random selection)</span>
                  </div>
                </div>

                <div className="bg-quip-teal bg-opacity-5 p-3 rounded-lg mt-3">
                  <p className="text-xs text-quip-navy">
                    <strong>Key Milestones:</strong> The <strong>3rd vote</strong> and <strong>5th vote</strong> timestamps
                    determine when your phraseset enters priority queues, affecting how quickly it receives additional votes and finalizes.
                  </p>
                </div>

                <div className="text-xs text-gray-600 mt-3 space-y-1">
                  <p><strong>Voting Window:</strong></p>
                  <ul className="list-disc list-inside ml-2 space-y-0.5">
                    <li>After 3rd vote: Remains open for 10 minutes or until 5th vote (whichever comes first)</li>
                    <li>After 5th vote: Accepts new voters for 60 seconds</li>
                    <li>Maximum: 20 votes per phraseset</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
