import React from 'react';
import type {
  PhrasesetDetails as PhrasesetDetailsType,
  PhrasesetStatus,
  PhrasesetSummary,
} from '../api/types';
import { StatusBadge } from './StatusBadge';
import { ProgressBar } from './ProgressBar';
import { ActivityTimeline } from './PhrasesetActivityTimeline';
import { formatDateTimeInUserZone } from '../utils/datetime';
import { BotIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';

interface PhrasesetDetailsProps {
  phraseset: PhrasesetDetailsType | null;
  summary?: PhrasesetSummary | null;
  loading?: boolean;
}

const STATUS_LABELS: Record<PhrasesetStatus, string> = {
  waiting_copies: 'Waiting for Copies',
  waiting_copy1: 'Waiting for Final Copy',
  active: 'Voting Active',
  voting: 'Voting Active',
  closing: 'Closing Soon',
  finalized: 'Finalized',
  abandoned: 'Abandoned',
};

const formatStatusLabel = (status: PhrasesetStatus) => STATUS_LABELS[status] ?? status.replace('_', ' ');

export const PhrasesetDetails: React.FC<PhrasesetDetailsProps> = ({
  phraseset,
  summary,
  loading,
}) => {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-600">
        Loading round details…
      </div>
    );
  }

  // If we have a summary but no full phraseset (prompt without copies yet)
  if (!phraseset && summary) {
    return (
      <div className="bg-white rounded-lg shadow p-6 space-y-6">
        <header className="space-y-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h2 className="text-2xl font-semibold text-gray-800">{summary.prompt_text}</h2>
            <StatusBadge status={summary.status} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
              <p className="text-xs text-blue-700 uppercase tracking-wide">Your Role</p>
              <p className="text-lg font-semibold text-blue-900 capitalize">{summary.your_role}</p>
              {summary.your_phrase && (
                <>
                  <p className="text-xs text-blue-700 mt-3 uppercase tracking-wide">Your Phrase</p>
                  <p className="text-md font-semibold text-blue-900">{summary.your_phrase}</p>
                </>
              )}
              {summary.your_role === 'copy' && summary.original_phrase && (
                <>
                  <p className="text-xs text-blue-700 mt-3 uppercase tracking-wide">Original Phrase</p>
                  <p className="text-md font-semibold text-blue-900">{summary.original_phrase}</p>
                </>
              )}
            </div>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
              <p className="text-xs text-gray-700 uppercase tracking-wide">Status</p>
              <p className="text-lg font-semibold text-gray-900">{formatStatusLabel(summary.status)}</p>
              {summary.vote_count != null && (
                <>
                  <p className="text-xs text-gray-700 mt-3 uppercase tracking-wide">Votes</p>
                  <p className="text-md font-semibold text-gray-900">{summary.vote_count}</p>
                </>
              )}
            </div>
          </div>
        </header>

        {(summary.status === 'waiting_copies' || summary.status === 'waiting_copy1') && !summary.phraseset_id && (
          <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
            <p className="text-sm text-yellow-800">
              This prompt is waiting for copies to join. Full details will be available once the round is complete.
            </p>
          </div>
        )}

        <section className="text-xs text-gray-600">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <span className="font-semibold text-gray-700">Created:</span>{' '}
              {formatDateTimeInUserZone(summary.created_at)}
            </div>
            {summary.updated_at && (
              <div>
                <span className="font-semibold text-gray-700">Updated:</span>{' '}
                {formatDateTimeInUserZone(summary.updated_at)}
              </div>
            )}
          </div>
        </section>
      </div>
    );
  }

  if (!phraseset) {
    return (
      <div className="bg-white rounded-lg shadow p-8 text-center text-gray-500">
        Select a round to see more details.
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <header className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 className="text-2xl font-semibold text-gray-800">{phraseset.prompt_text}</h2>
          <StatusBadge status={phraseset.status} />
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <p className="text-xs text-blue-700 uppercase tracking-wide">Your Role</p>
            <p className="text-lg font-semibold text-blue-900 capitalize">{phraseset.your_role}</p>
            {(summary?.your_phrase || phraseset.your_phrase) && (
              <>
                <p className="text-xs text-blue-700 mt-3 uppercase tracking-wide">Your Phrase</p>
                <p className="text-md font-semibold text-blue-900">{summary?.your_phrase || phraseset.your_phrase}</p>
              </>
            )}
            {phraseset.your_role === 'copy' && phraseset.original_phrase && (
              <>
                <p className="text-xs text-blue-700 mt-3 uppercase tracking-wide">Original Phrase</p>
                <p className="text-md font-semibold text-blue-900">{phraseset.original_phrase}</p>
              </>
            )}
          </div>
          <div className="bg-green-50 border border-green-200 rounded-lg p-4">
            <p className="text-xs text-green-700 uppercase tracking-wide">Earnings</p>
            <p className="text-lg font-semibold text-green-900">
              {phraseset.your_payout != null ? `$${phraseset.your_payout}` : '—'}
            </p>
            {phraseset.status === 'finalized' && (
              <>
                <p className="text-xs text-green-700 mt-3 uppercase tracking-wide">Status</p>
                <p className="text-sm font-medium text-green-800">
                  ✓ Auto-added at finalization
                </p>
              </>
            )}
          </div>
        </div>
      </header>

      <section>
        <ProgressBar current={phraseset.vote_count} max={20} />
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs text-gray-600 mt-4">
          <div>
            <span className="font-semibold text-gray-700">Created:</span>{' '}
            {formatDateTimeInUserZone(phraseset.created_at)}
          </div>
          <div>
            <span className="font-semibold text-gray-700">Third vote:</span>{' '}
            {formatDateTimeInUserZone(phraseset.third_vote_at)}
          </div>
          <div>
            <span className="font-semibold text-gray-700">Fifth vote:</span>{' '}
            {formatDateTimeInUserZone(phraseset.fifth_vote_at)}
          </div>
          <div>
            <span className="font-semibold text-gray-700">Closes:</span>{' '}
            {formatDateTimeInUserZone(phraseset.closes_at)}
          </div>
          <div>
            <span className="font-semibold text-gray-700">Finalized:</span>{' '}
            {formatDateTimeInUserZone(phraseset.finalized_at)}
          </div>
          <div>
            <span className="font-semibold text-gray-700">Total Pool:</span> ${phraseset.total_pool}
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-3">
        {phraseset.contributors.map((contributor) => (
          <div
            key={contributor.round_id}
            className={`rounded-lg border p-3 ${
              contributor.is_you ? 'border-blue-400 bg-blue-50' : 'border-gray-200 bg-gray-50'
            }`}
          >
            <p className="text-xs uppercase text-gray-500 mb-1">
              {contributor.is_you ? 'You' : 'Contributor'}
            </p>
            <p className="text-sm font-semibold text-gray-800 flex items-center gap-1">
              {contributor.username}
              {contributor.is_ai && <BotIcon className="h-4 w-4" />}
            </p>
            {contributor.phrase && (
              <p className="text-xs text-gray-600 mt-2">
                Phrase: <span className="font-semibold text-gray-700">{contributor.phrase}</span>
              </p>
            )}
          </div>
        ))}
      </section>

      <section>
        <h3 className="text-lg font-semibold text-gray-800 mb-3">Votes</h3>
        {phraseset.votes.length === 0 ? (
          <p className="text-sm text-gray-500">No votes recorded yet.</p>
        ) : (
          <div className="overflow-hidden rounded-lg border">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-100">
                <tr>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Voter</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Voted Phrase</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Correct</th>
                  <th className="px-4 py-2 text-left font-semibold text-gray-700">Time</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 bg-white">
                {phraseset.votes.map((vote) => (
                  <tr key={vote.vote_id}>
                    <td className="px-4 py-2 text-gray-700">
                      <span className="flex items-center gap-1">
                        {vote.voter_username}
                        {vote.is_ai && <BotIcon className="h-3.5 w-3.5" />}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-800 font-medium">{vote.voted_phrase}</td>
                    <td className="px-4 py-2">
                      <span
                        className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-semibold ${
                          vote.correct ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-600'
                        }`}
                      >
                        {vote.correct ? 'Correct' : 'Incorrect'}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-600">
                      {formatDateTimeInUserZone(vote.voted_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {phraseset.results && (
        <section>
          <h3 className="text-lg font-semibold text-gray-800 mb-3">Final Results</h3>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Vote Breakdown</h4>
              <ul className="space-y-2 text-sm text-gray-700">
                {Object.entries(phraseset.results.vote_counts).map(([phrase, votes]) => (
                  <li key={phrase} className="flex justify-between">
                    <span>{phrase}</span>
                    <span className="font-semibold">{votes} vote{votes === 1 ? '' : 's'}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className="border border-gray-200 rounded-lg p-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2">Payouts</h4>
              <ul className="space-y-2 text-sm text-gray-700">
                {Object.entries(phraseset.results.payouts).map(([role, info]) => (
                  <li key={role} className="flex justify-between">
                    <span className="capitalize">{role}</span>
                    <span className="font-semibold">${info.payout} ({info.points} pts)</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      )}

      <section>
        <h3 className="text-lg font-semibold text-gray-800 mb-3">Activity</h3>
        <ActivityTimeline activities={phraseset.activity} />
      </section>
    </div>
  );
};
