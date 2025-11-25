import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '../api/client';
import type { FlaggedPromptItem } from '../api/types';
import { formatDateTimeInUserZone } from '../utils/datetime';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

type FlagStatusFilter = 'pending' | 'confirmed' | 'dismissed' | 'all';

const statusLabels: Record<FlagStatusFilter, string> = {
  pending: 'Pending review',
  confirmed: 'Confirmed',
  dismissed: 'Dismissed',
  all: 'All statuses',
};

const statusStyles: Record<FlagStatusFilter, string> = {
  pending: 'bg-quip-orange/15 text-quip-orange',
  confirmed: 'bg-quip-turquoise/15 text-quip-turquoise',
  dismissed: 'bg-gray-200 text-quip-navy',
  all: 'bg-quip-navy/10 text-quip-navy',
};

const AdminFlagged: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();
  const [flags, setFlags] = useState<FlaggedPromptItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<FlagStatusFilter>('pending');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [resolvingId, setResolvingId] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const loadFlags = useCallback(async (nextStatus: FlagStatusFilter) => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getFlaggedPrompts(nextStatus);
      setFlags(response.flags);
    } catch (err) {
      const message = extractErrorMessage(err, 'admin-load-flags') || 'Failed to load flagged phrases.';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!player) {
      return;
    }

    loadFlags(statusFilter);
  }, [loadFlags, player, statusFilter]);

  useEffect(() => {
    if (!successMessage) {
      return;
    }
    const timer = window.setTimeout(() => setSuccessMessage(null), 4000);
    return () => window.clearTimeout(timer);
  }, [successMessage]);

  const handleResolve = async (flagId: string, action: 'confirm' | 'dismiss') => {
    try {
      setResolvingId(flagId);
      const result = await apiClient.resolveFlaggedPrompt(flagId, action);
      setFlags((prev) => {
        const next = prev.map((item) => (item.flag_id === flagId ? result : item));
        return statusFilter === 'pending' ? next.filter((item) => item.status === 'pending') : next;
      });
      setSuccessMessage(action === 'confirm' ? 'Flag confirmed and refunds processed.' : 'Flag dismissed. Reporter notified.');
    } catch (err) {
      const message = extractErrorMessage(err, 'admin-resolve-flag') || 'Unable to resolve this flag.';
      setError(message);
    } finally {
      setResolvingId(null);
    }
  };

  const filteredLabel = useMemo(() => statusLabels[statusFilter], [statusFilter]);

  if (!player) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="flex items-center justify-center py-16 text-quip-teal">Loading...</div>
      </div>
    );
  }

  if (!player.is_admin) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="flex items-center justify-center py-16">
          <div className="rounded-tile border border-quip-orange/40 bg-white/80 p-6 text-center text-quip-teal">
            <p className="text-lg font-semibold text-quip-navy">Admin access required</p>
            <p className="mt-2 text-sm">You do not have permission to view flagged phrases.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto max-w-5xl px-4 py-8">
        <div className="tile-card mb-6 flex flex-col gap-4 border-2 border-quip-orange p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h1 className="text-3xl font-display font-bold text-quip-navy">Flagged Phrases</h1>
            <p className="text-quip-teal">Review community reports for offensive or nonsensical phrases.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <button
              onClick={() => navigate('/admin')}
              className="rounded-tile border-2 border-quip-navy px-4 py-2 text-sm font-semibold text-quip-navy transition hover:bg-quip-navy hover:text-white"
            >
              Back to Admin Panel
            </button>
            <select
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as FlagStatusFilter)}
              className="rounded-tile border-2 border-quip-teal px-4 py-2 text-sm font-semibold text-quip-teal focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
            >
              {(Object.keys(statusLabels) as FlagStatusFilter[]).map((status) => (
                <option key={status} value={status}>
                  {statusLabels[status]}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded border border-red-300 bg-red-100 px-4 py-3 text-red-700">{error}</div>
        )}

        {successMessage && (
          <div className="mb-4 rounded border border-quip-turquoise bg-quip-turquoise/10 px-4 py-3 text-quip-teal">{successMessage}</div>
        )}

        <div className="mb-4 text-sm text-quip-teal">Showing: <span className="font-semibold text-quip-navy">{filteredLabel}</span></div>

        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="inline-flex items-center gap-3 text-quip-teal">
              <span className="h-4 w-4 animate-spin rounded-full border-2 border-quip-orange border-r-transparent"></span>
              Loading flagged phrases...
            </div>
          </div>
        ) : flags.length === 0 ? (
          <div className="rounded-tile border border-dashed border-quip-teal/40 bg-white/80 p-8 text-center text-quip-teal">
            <p className="text-lg font-semibold">No flagged phrases in this view.</p>
            <p className="text-sm">Great job keeping things clean!</p>
          </div>
        ) : (
          <div className="space-y-6">
            {flags.map((flag) => {
              const createdLabel = formatDateTimeInUserZone(flag.created_at);
              const reviewedLabel = flag.reviewed_at ? formatDateTimeInUserZone(flag.reviewed_at) : null;
              const statusKey = flag.status as FlagStatusFilter;

              return (
                <div key={flag.flag_id} className="tile-card space-y-4 border border-quip-turquoise/30 p-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                    <div>
                      <p className="text-xs uppercase tracking-wide text-quip-teal">Original Phrase</p>
                      <p className="text-2xl font-display font-bold text-quip-navy">{flag.original_phrase}</p>
                      {flag.prompt_text && (
                        <p className="mt-2 text-sm text-quip-teal">
                          Prompt context: <span className="font-medium text-quip-navy">{flag.prompt_text}</span>
                        </p>
                      )}
                    </div>
                    <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${statusStyles[statusKey] || statusStyles.pending}`}>
                      {statusLabels[statusKey] ?? statusLabels.pending}
                    </span>
                  </div>

                  <div className="grid gap-4 text-sm text-quip-teal sm:grid-cols-2">
                    <div>
                      <span className="font-semibold text-quip-navy">Reported by:</span> {flag.reporter_username}
                      <div className="text-xs">{createdLabel}</div>
                    </div>
                    <div>
                      <span className="font-semibold text-quip-navy">Prompt author:</span> {flag.prompt_username}
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-quip-navy">Partial refund:</span>
                      <CurrencyDisplay amount={flag.partial_refund_amount} iconClassName="w-3 h-3" textClassName="text-sm text-quip-navy" />
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-quip-navy">Penalty held:</span>
                      <CurrencyDisplay amount={flag.penalty_kept} iconClassName="w-3 h-3" textClassName="text-sm text-quip-navy" />
                    </div>
                  </div>

                  {flag.status === 'pending' ? (
                    <div className="flex flex-col gap-3 sm:flex-row sm:justify-end">
                      <button
                        type="button"
                        onClick={() => handleResolve(flag.flag_id, 'dismiss')}
                        disabled={resolvingId === flag.flag_id}
                        className="rounded-tile border-2 border-quip-navy px-4 py-2 text-sm font-semibold text-quip-navy transition hover:bg-quip-navy hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {resolvingId === flag.flag_id ? 'Processing...' : 'Dismiss flag'}
                      </button>
                      <button
                        type="button"
                        onClick={() => handleResolve(flag.flag_id, 'confirm')}
                        disabled={resolvingId === flag.flag_id}
                        className="rounded-tile bg-quip-orange px-4 py-2 text-sm font-semibold text-white shadow-tile-sm transition hover:bg-quip-orange/90 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {resolvingId === flag.flag_id ? 'Processing...' : 'Confirm & refund'}
                      </button>
                    </div>
                  ) : (
                    <div className="text-sm text-quip-teal">
                      <span className="font-semibold text-quip-navy">Reviewed</span>{' '}
                      {reviewedLabel ? reviewedLabel : '—'}
                      {flag.reviewer_username && (
                        <span className="ml-1">by {flag.reviewer_username}</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default AdminFlagged;
