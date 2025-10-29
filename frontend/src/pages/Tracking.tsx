import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useSmartPolling, PollConfigs } from '../utils/smartPolling';
import { useLoadingState, InlineLoadingSpinner } from '../components/LoadingSpinner';
import type {
  PhrasesetSummary,
  PhrasesetDetails as PhrasesetDetailsType,
} from '../api/types';
import { useGame } from '../contexts/GameContext';
import { buildPhrasesetListKey } from '../utils/gameKeys';
import { PhrasesetList } from '../components/PhrasesetList';
import { PhrasesetDetails } from '../components/PhrasesetDetails';
import { Header } from '../components/Header';
import { useResults } from '../contexts/ResultsContext';
import { trackingLogger } from '../utils/logger';

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
  const { state: gameState } = useGame();
  const { state: resultsState, actions: resultsActions } = useResults();
  const { phrasesetSummary } = gameState;
  const {
    playerPhrasesets,
    phrasesetDetails,
  } = resultsState;
  const {
    refreshPlayerPhrasesets,
    refreshPhrasesetDetails,
  } = resultsActions;

  const { startPoll, stopPoll } = useSmartPolling();
  const { setLoading, clearLoading, getLoadingState } = useLoadingState();

  const [roleFilter, setRoleFilter] = useState<RoleFilter>('all');
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('in_progress');
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [infoExpanded, setInfoExpanded] = useState(false);

  const refreshPlayerPhrasesetsRef = useRef(refreshPlayerPhrasesets);
  const refreshPhrasesetDetailsRef = useRef(refreshPhrasesetDetails);
  const lastRequestedListKeyRef = useRef<string | null>(null);
  const lastRequestedDetailsIdRef = useRef<string | null>(null);

  useEffect(() => {
    refreshPlayerPhrasesetsRef.current = refreshPlayerPhrasesets;
  }, [refreshPlayerPhrasesets]);
  useEffect(() => {
    refreshPhrasesetDetailsRef.current = refreshPhrasesetDetails;
  }, [refreshPhrasesetDetails]);

  useEffect(() => {
    trackingLogger.debug('Tracking page mounted');
  }, []);

  const params = useMemo(() => ({
    role: roleFilter === 'all' ? undefined : roleFilter,
    status: statusFilter === 'all' ? undefined : statusFilter,
    limit: 100,
    offset: 0,
  }), [roleFilter, statusFilter]);

  const paramsKey = useMemo(() => buildPhrasesetListKey(params), [params]);
  const listEntry = playerPhrasesets[paramsKey];
  const rawPhrasesets = listEntry?.data?.phrasesets;
  const phrasesets = useMemo<PhrasesetSummary[]>(
    () => rawPhrasesets ?? [],
    [rawPhrasesets],
  );
  const listLoading = listEntry?.loading ?? false;
  const listError = listEntry?.error ?? null;

  useEffect(() => {
    if (lastRequestedListKeyRef.current === paramsKey) {
      trackingLogger.debug('Skipping duplicate list refresh for params', { paramsKey });
      return;
    }

    lastRequestedListKeyRef.current = paramsKey;

    trackingLogger.debug('Forcing player phrasesets refresh on navigation', {
      params,
      paramsKey,
    });

    refreshPlayerPhrasesetsRef.current(params, { force: true })
      .then((data) => {
        trackingLogger.debug('Player phrasesets refreshed', {
          forced: true,
          count: data?.phrasesets?.length ?? 0,
        });
      })
      .catch((err: any) => {
        trackingLogger.error('Failed to refresh phrasesets', err);
      });
  }, [params, paramsKey]);

  useEffect(() => {
    if (phrasesets.length === 0) {
      setSelectedId(null);
      return;
    }

    const alreadySelected = phrasesets.find((summary) => {
      const id = summary.phraseset_id ?? summary.prompt_round_id;
      return id === selectedId;
    });

    if (!alreadySelected) {
      const first = phrasesets[0];
      const newId = first.phraseset_id ?? first.prompt_round_id ?? null;
      setSelectedId(newId);
    }
  }, [phrasesets, selectedId]);

  const selectedSummary = useMemo(() => {
    if (!selectedId) return null;
    return (
      phrasesets.find((summary) => {
        const id = summary.phraseset_id ?? summary.prompt_round_id;
        return id === selectedId;
      }) ?? null
    );
  }, [phrasesets, selectedId]);

  const selectedDetailsEntry = selectedSummary?.phraseset_id
    ? phrasesetDetails[selectedSummary.phraseset_id]
    : undefined;
  const details = selectedDetailsEntry?.data ?? null;
  const detailsLoading = selectedDetailsEntry?.loading ?? false;
  const detailsError = selectedDetailsEntry?.error ?? null;

  useEffect(() => {
    if (!selectedSummary?.phraseset_id) {
      trackingLogger.debug('No phraseset selected, stopping detail polling');
      lastRequestedDetailsIdRef.current = null;
      stopPoll('phraseset-details');
      return;
    }

    if (lastRequestedDetailsIdRef.current === selectedSummary.phraseset_id) {
      trackingLogger.debug('Skipping duplicate details refresh for phraseset', {
        phrasesetId: selectedSummary.phraseset_id,
      });
      return;
    }

    lastRequestedDetailsIdRef.current = selectedSummary.phraseset_id;

    trackingLogger.debug('Forcing phraseset details refresh on selection', {
      phrasesetId: selectedSummary.phraseset_id,
    });

    refreshPhrasesetDetailsRef.current(selectedSummary.phraseset_id!, { force: true })
      .then(() => {
        trackingLogger.debug('Phraseset details refreshed', {
          phrasesetId: selectedSummary.phraseset_id,
          forced: true,
        });
      })
      .catch((err: any) => {
        trackingLogger.error('Failed to refresh phraseset details', err);
      });
  }, [selectedSummary?.phraseset_id, stopPoll]);

  useEffect(() => {
    if (!selectedSummary?.phraseset_id) {
      stopPoll('phraseset-details');
      return;
    }

    if (selectedDetailsEntry?.data?.status === 'finalized') {
      stopPoll('phraseset-details');
      return;
    }

    startPoll(PollConfigs.PHRASESET_DETAILS, async () => {
      trackingLogger.debug('Polling phraseset details', {
        phrasesetId: selectedSummary.phraseset_id,
      });
      await refreshPhrasesetDetailsRef.current(selectedSummary.phraseset_id!, { force: true });
    });

    return () => {
      stopPoll('phraseset-details');
    };
  }, [selectedSummary?.phraseset_id, selectedDetailsEntry?.data?.status, startPoll, stopPoll]);

  useEffect(() => {
    if (listLoading) {
      setLoading('phrasesets', {
        isLoading: true,
        type: 'refresh',
        message: 'Loading your past rounds...',
      });
    } else {
      clearLoading('phrasesets');
    }
  }, [listLoading]); // Remove setLoading and clearLoading from dependencies

  useEffect(() => {
    if (detailsLoading) {
      setLoading('details', {
        isLoading: true,
        type: 'refresh',
        message: 'Loading details...',
      });
    } else {
      clearLoading('details');
    }
  }, [detailsLoading]); // Remove setLoading and clearLoading from dependencies

  const handleSelect = (summary: PhrasesetSummary) => {
    const id = summary.phraseset_id ?? summary.prompt_round_id;
    trackingLogger.debug('Phraseset selected from list', {
      summaryId: id,
      status: summary.status,
      role: summary.your_role,
    });
    setSelectedId(id ?? null);
  };

  const handleRoleFilterChange = (nextRole: RoleFilter) => {
    trackingLogger.debug('Role filter changed', { nextRole });
    setRoleFilter(nextRole);
  };

  const handleStatusFilterChange = (nextStatus: StatusFilter) => {
    trackingLogger.debug('Status filter changed', { nextStatus });
    setStatusFilter(nextStatus);
  };

  const totalTracked = useMemo(() => phrasesets.length, [phrasesets.length]);

  const combinedError = listError ?? detailsError;

  const listLoadingState = getLoadingState('phrasesets');
  const detailsLoadingState = getLoadingState('details');

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Round Tracking</h1>
          <p className="text-quip-teal mt-2">
            Keep an eye on your in-progress rounds, review voting status, and celebrate finalized quipsets.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 space-y-6">
            <div className="tile-card p-4">
              <div className="flex items-center justify-between mb-4">
                <h2 className="font-display font-bold text-lg text-quip-navy">Your Activity</h2>
                <button
                  onClick={() => setInfoExpanded((prev) => !prev)}
                  className="text-sm text-quip-teal hover:text-quip-turquoise"
                >
                  {infoExpanded ? 'Hide Info' : 'What is this?'}
                </button>
              </div>

              {infoExpanded && (
                <div className="bg-quip-turquoise bg-opacity-10 border-2 border-quip-turquoise rounded-tile p-3 mb-4 text-sm text-quip-teal">
                  Track every quipset you've touched. Use the filters to drill into specific roles or statuses.
                </div>
              )}

              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-quip-navy bg-opacity-5 border-2 border-quip-navy rounded-tile p-3 text-center">
                  <p className="text-xs text-quip-teal uppercase tracking-wide">Total Rounds</p>
                  <p className="text-2xl font-display font-bold text-quip-navy">{totalTracked}</p>
                </div>
                <div className="bg-quip-orange bg-opacity-10 border-2 border-quip-orange rounded-tile p-3 text-center">
                  <p className="text-xs text-quip-orange-deep uppercase tracking-wide">Finalized</p>
                  <p className="text-2xl font-display font-bold text-quip-orange-deep">
                    {(phrasesetSummary?.finalized?.prompts ?? 0) + (phrasesetSummary?.finalized?.copies ?? 0)}
                  </p>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <label className="block text-xs font-semibold text-quip-teal mb-2">Role</label>
                  <select
                    value={roleFilter}
                    onChange={(event) => handleRoleFilterChange(event.target.value as RoleFilter)}
                    className="w-full rounded-tile border-2 border-quip-teal bg-white p-2 text-sm"
                  >
                    {roleOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-quip-teal mb-2">Status</label>
                  <select
                    value={statusFilter}
                    onChange={(event) => handleStatusFilterChange(event.target.value as StatusFilter)}
                    className="w-full rounded-tile border-2 border-quip-teal bg-white p-2 text-sm"
                  >
                    {statusOptions.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>

            <div className="tile-card p-0 overflow-hidden">
              {detailsLoadingState?.isLoading ? (
                <div className="p-6">
                  <InlineLoadingSpinner message={detailsLoadingState.message} />
                </div>
              ) : selectedSummary ? (
                <PhrasesetDetails
                  phraseset={details as PhrasesetDetailsType | null}
                  summary={selectedSummary}
                />
              ) : (
                <div className="p-6 text-center text-quip-teal">
                  Select a round to see more information.
                </div>
              )}
            </div>

          </div>

          <div className="lg:col-span-1 space-y-4">
            {combinedError && (
              <div className="bg-red-100 border-2 border-red-400 text-red-700 rounded-tile p-3">
                {combinedError}
              </div>
            )}

            <div className="tile-card p-0 overflow-hidden">
              {listLoadingState?.isLoading ? (
                <div className="p-6">
                  <InlineLoadingSpinner message={listLoadingState.message} />
                </div>
              ) : (
                <PhrasesetList
                  phrasesets={phrasesets}
                  selectedId={selectedId}
                  onSelect={handleSelect}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Tracking;
