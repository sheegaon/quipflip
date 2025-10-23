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

  // Store the last fetched details to compare for changes
  const lastDetailsRef = useRef<PhrasesetDetailsType | null>(null);

  const fetchPhrasesets = useCallback(async () => {
    setListLoading(true);
    try {
      const data = await apiClient.getPlayerPhrasesets({
        role: roleFilter,
        status: statusFilter,
        limit: 100,
        offset: 0,
      });
      setPhrasesets(data.phrasesets);
      if (data.phrasesets.length > 0) {
        const first = data.phrasesets.find((item) =>
          item.phraseset_id ? item.phraseset_id === selectedId : item.prompt_round_id === selectedId
        ) ?? data.phrasesets[0];
        const id = first.phraseset_id ?? first.prompt_round_id;
        setSelectedId(id);
        setSelectedSummary(first);
      } else {
        setSelectedId(null);
        setSelectedSummary(null);
        setDetails(null);
      }
      setError(null);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to load your past rounds. Please refresh the page or try again in a moment.');
    } finally {
      setListLoading(false);
    }
  }, [roleFilter, statusFilter, selectedId]);

  const fetchDetails = useCallback(async (phraseset: PhrasesetSummary | null) => {
    if (!phraseset || !phraseset.phraseset_id) {
      setDetails(null);
      lastDetailsRef.current = null;
      return;
    }
    setDetailsLoading(true);
    try {
      const data = await apiClient.getPhrasesetDetails(phraseset.phraseset_id);
      
      // Only update state if the data has actually changed
      const hasChanged = !lastDetailsRef.current || 
        JSON.stringify(lastDetailsRef.current) !== JSON.stringify(data);
      
      if (hasChanged) {
        setDetails(data);
        lastDetailsRef.current = data;
      }
      
      setError(null);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to load the details for this round. It may no longer be available.');
    } finally {
      setDetailsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPhrasesets();
  }, [fetchPhrasesets]);

  useEffect(() => {
    if (selectedSummary) {
      fetchDetails(selectedSummary);
    }
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
      </div>
    </div>
  );
};
