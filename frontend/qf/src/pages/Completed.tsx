import React, { useEffect, useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { Header } from '../components/Header';
import { apiClient } from '@crowdcraft/api/client.ts';
import type { QFCompletedPhrasesetItem } from '@crowdcraft/api/types.ts';
import { InlineLoadingSpinner } from '../components/LoadingSpinner';
import { ReviewIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import { ArrowLeftIcon, ArrowRightIcon } from '@crowdcraft/components/icons/ArrowIcons.tsx';
import { getErrorMessage, isError } from '@crowdcraft/types/errors.ts';

type SortField = 'vote_count' | 'total_pool' | 'created_at' | 'finalized_at';
type SortDirection = 'asc' | 'desc';

export const Completed: React.FC = () => {
  const navigate = useNavigate();
  const [phrasesets, setPhrasesets] = useState<QFCompletedPhrasesetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [sortField, setSortField] = useState<SortField>('finalized_at');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const itemsPerPage = 10;

  useEffect(() => {
    const controller = new AbortController();

    const fetchData = async () => {
      try {
        setLoading(true);
        setError(null);
        const response = await apiClient.getCompletedPhrasesets(
          { limit: 500, offset: 0 }, // Fetch up to 500 for client-side pagination and sorting
          controller.signal
        );
        setPhrasesets(response.phrasesets);
      } catch (err: unknown) {
        // Check if error is a cancellation (AbortController)
        const isCanceled =
          isError(err) && (err.name === 'CanceledError' || err.name === 'AbortError');

        if (!isCanceled) {
          setError(getErrorMessage(err, 'Failed to load completed phrasesets'));
        }
      } finally {
        setLoading(false);
      }
    };

    fetchData();

    return () => {
      controller.abort();
    };
  }, []);

  const sortedPhrasesets = useMemo(() => {
    const sorted = [...phrasesets].sort((a, b) => {
      let aVal: number | string;
      let bVal: number | string;

      if (sortField === 'vote_count' || sortField === 'total_pool') {
        aVal = a[sortField];
        bVal = b[sortField];
      } else {
        aVal = new Date(a[sortField]).getTime();
        bVal = new Date(b[sortField]).getTime();
      }

      if (aVal < bVal) return sortDirection === 'asc' ? -1 : 1;
      if (aVal > bVal) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });

    return sorted;
  }, [phrasesets, sortField, sortDirection]);

  const paginatedPhrasesets = useMemo(() => {
    const start = page * itemsPerPage;
    return sortedPhrasesets.slice(start, start + itemsPerPage);
  }, [sortedPhrasesets, page]);

  const totalPages = Math.ceil(sortedPhrasesets.length / itemsPerPage);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('desc');
    }
    setPage(0);
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  const formatDateTime = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getSortIcon = (field: SortField) => {
    if (sortField !== field) {
      return <span className="text-gray-400">↕</span>;
    }
    return sortDirection === 'asc' ? <span className="text-ccl-turquoise">↑</span> : <span className="text-ccl-turquoise">↓</span>;
  };

  const getAriaSort = (field: SortField): 'ascending' | 'descending' | 'none' => {
    if (sortField !== field) return 'none';
    return sortDirection === 'asc' ? 'ascending' : 'descending';
  };

  const handleRowClick = (phrasesetId: string) => {
    navigate(`/phraseset/${phrasesetId}/review`);
  };

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-ccl-navy">Completed Rounds</h1>
          <p className="text-ccl-teal mt-2">
            View all finalized quipsets and their results.
          </p>
        </div>

        {loading ? (
          <div className="tile-card p-8">
            <InlineLoadingSpinner message="Loading completed rounds..." />
          </div>
        ) : error ? (
          <div className="tile-card p-6">
            <div className="bg-red-100 border-2 border-red-400 text-red-700 rounded-tile p-4">
              {error}
            </div>
          </div>
        ) : (
          <div className="tile-card p-0 overflow-hidden">
            {/* Stats summary */}
            <div className="p-4 bg-ccl-navy bg-opacity-5 border-b-2 border-ccl-navy border-opacity-10">
              <p className="text-sm text-ccl-teal">
                Showing <span className="font-semibold text-ccl-navy">{phrasesets.length}</span> completed rounds
              </p>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-ccl-turquoise bg-opacity-10">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-ccl-teal uppercase tracking-wider">
                      Prompt
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-ccl-teal uppercase tracking-wider cursor-pointer hover:bg-ccl-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('vote_count')}
                      aria-sort={getAriaSort('vote_count')}
                    >
                      <div className="flex items-center gap-1">
                        Voters {getSortIcon('vote_count')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-ccl-teal uppercase tracking-wider cursor-pointer hover:bg-ccl-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('total_pool')}
                      aria-sort={getAriaSort('total_pool')}
                    >
                      <div className="flex items-center gap-1">
                        Prize Pool {getSortIcon('total_pool')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-ccl-teal uppercase tracking-wider cursor-pointer hover:bg-ccl-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('created_at')}
                      aria-sort={getAriaSort('created_at')}
                    >
                      <div className="flex items-center gap-1">
                        Created {getSortIcon('created_at')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-ccl-teal uppercase tracking-wider cursor-pointer hover:bg-ccl-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('finalized_at')}
                      aria-sort={getAriaSort('finalized_at')}
                    >
                      <div className="flex items-center gap-1">
                        Finalized {getSortIcon('finalized_at')}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {paginatedPhrasesets.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-4 py-8 text-center text-ccl-teal">
                        No completed rounds yet.
                      </td>
                    </tr>
                  ) : (
                    paginatedPhrasesets.map((phraseset) => (
                      <tr
                        key={phraseset.phraseset_id}
                        onClick={() => handleRowClick(phraseset.phraseset_id)}
                        className="hover:bg-ccl-teal-light transition-colors cursor-pointer"
                        title="Click to review this phraseset"
                      >
                        <td className="px-4 py-3 text-sm text-ccl-navy">
                          <div className="max-w-md flex items-center gap-2">
                            <ReviewIcon className="h-4 w-4 flex-shrink-0" />
                            <span>{phraseset.prompt_text}</span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-ccl-navy font-semibold">
                          {phraseset.vote_count}
                        </td>
                        <td className="px-4 py-3 text-sm text-ccl-orange font-semibold">
                          {phraseset.total_pool}
                        </td>
                        <td className="px-4 py-3 text-sm text-ccl-teal">
                          {formatDate(phraseset.created_at)}
                        </td>
                        <td className="px-4 py-3 text-sm text-ccl-teal">
                          {formatDateTime(phraseset.finalized_at)}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="p-4 bg-ccl-navy bg-opacity-5 border-t-2 border-ccl-navy border-opacity-10 flex items-center justify-between">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page === 0}
                  className="disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-70 transition-opacity"
                  aria-label="Previous page"
                >
                  <ArrowLeftIcon className="w-4 h-6" aria-hidden="true" />
                </button>
                <div className="text-sm text-ccl-teal">
                  Page {page + 1} of {totalPages}
                </div>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages - 1}
                  className="disabled:opacity-30 disabled:cursor-not-allowed hover:opacity-70 transition-opacity"
                  aria-label="Next page"
                >
                  <ArrowRightIcon className="w-4 h-6" aria-hidden="true" />
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Completed;
