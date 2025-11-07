import React, { useEffect, useState, useMemo } from 'react';
import { Header } from '../components/Header';
import { apiClient } from '../api/client';
import type { CompletedPhrasesetItem } from '../api/types';
import { InlineLoadingSpinner } from '../components/LoadingSpinner';

type SortField = 'vote_count' | 'total_pool' | 'created_at' | 'finalized_at';
type SortDirection = 'asc' | 'desc';

export const Completed: React.FC = () => {
  const [phrasesets, setPhrasesets] = useState<CompletedPhrasesetItem[]>([]);
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
      } catch (err: any) {
        if (err.name !== 'CanceledError' && err.code !== 'ERR_CANCELED') {
          setError(err.detail || err.message || 'Failed to load completed phrasesets');
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
    return sortDirection === 'asc' ? <span className="text-quip-turquoise">↑</span> : <span className="text-quip-turquoise">↓</span>;
  };

  const getAriaSort = (field: SortField): 'ascending' | 'descending' | 'none' => {
    if (sortField !== field) return 'none';
    return sortDirection === 'asc' ? 'ascending' : 'descending';
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />

      <div className="max-w-6xl mx-auto px-4 py-8">
        <div className="mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Completed Rounds</h1>
          <p className="text-quip-teal mt-2">
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
            <div className="p-4 bg-quip-navy bg-opacity-5 border-b-2 border-quip-navy border-opacity-10">
              <p className="text-sm text-quip-teal">
                Showing <span className="font-semibold text-quip-navy">{phrasesets.length}</span> completed rounds
              </p>
            </div>

            {/* Table */}
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-quip-turquoise bg-opacity-10">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-semibold text-quip-teal uppercase tracking-wider">
                      Prompt
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-quip-teal uppercase tracking-wider cursor-pointer hover:bg-quip-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('vote_count')}
                      aria-sort={getAriaSort('vote_count')}
                    >
                      <div className="flex items-center gap-1">
                        Voters {getSortIcon('vote_count')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-quip-teal uppercase tracking-wider cursor-pointer hover:bg-quip-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('total_pool')}
                      aria-sort={getAriaSort('total_pool')}
                    >
                      <div className="flex items-center gap-1">
                        Prize Pool {getSortIcon('total_pool')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-quip-teal uppercase tracking-wider cursor-pointer hover:bg-quip-turquoise hover:bg-opacity-20"
                      onClick={() => handleSort('created_at')}
                      aria-sort={getAriaSort('created_at')}
                    >
                      <div className="flex items-center gap-1">
                        Created {getSortIcon('created_at')}
                      </div>
                    </th>
                    <th
                      className="px-4 py-3 text-left text-xs font-semibold text-quip-teal uppercase tracking-wider cursor-pointer hover:bg-quip-turquoise hover:bg-opacity-20"
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
                      <td colSpan={5} className="px-4 py-8 text-center text-quip-teal">
                        No completed rounds yet.
                      </td>
                    </tr>
                  ) : (
                    paginatedPhrasesets.map((phraseset) => (
                      <tr
                        key={phraseset.phraseset_id}
                        className="hover:bg-quip-teal-light transition-colors"
                      >
                        <td className="px-4 py-3 text-sm text-quip-navy">
                          <div className="max-w-md">
                            {phraseset.prompt_text}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-quip-navy font-semibold">
                          {phraseset.vote_count}
                        </td>
                        <td className="px-4 py-3 text-sm text-quip-orange font-semibold">
                          {phraseset.total_pool}
                        </td>
                        <td className="px-4 py-3 text-sm text-quip-teal">
                          {formatDate(phraseset.created_at)}
                        </td>
                        <td className="px-4 py-3 text-sm text-quip-teal">
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
              <div className="p-4 bg-quip-navy bg-opacity-5 border-t-2 border-quip-navy border-opacity-10 flex items-center justify-between">
                <div className="text-sm text-quip-teal">
                  Page {page + 1} of {totalPages}
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 0}
                    className="px-4 py-2 rounded-tile bg-quip-turquoise text-white font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-quip-teal transition-colors"
                  >
                    Previous
                  </button>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page >= totalPages - 1}
                    className="px-4 py-2 rounded-tile bg-quip-turquoise text-white font-semibold text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-quip-teal transition-colors"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default Completed;
