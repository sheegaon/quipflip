import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import type { Circle, CreateCircleRequest } from '@crowdcraft/api/types.ts';
import { LoadingSpinner } from '../components/LoadingSpinner';

export const Circles: React.FC = () => {
  const navigate = useNavigate();
  const [circles, setCircles] = useState<Circle[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Create Circle modal state
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<CreateCircleRequest>({
    name: '',
    description: '',
    is_public: true,
  });
  const [createError, setCreateError] = useState<string | null>(null);
  const [createLoading, setCreateLoading] = useState(false);

  useEffect(() => {
    loadCircles();
  }, []);

  const loadCircles = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.listCircles({ limit: 100 });
      setCircles(response.circles);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to load Circles');
    } finally {
      setLoading(false);
    }
  };

  const handleJoinCircle = async (circleId: string) => {
    try {
      setActionLoading(circleId);
      await apiClient.joinCircle(circleId);
      await loadCircles(); // Refresh to show updated state
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to join Circle');
    } finally {
      setActionLoading(null);
    }
  };

  const handleLeaveCircle = async (circleId: string) => {
    if (!confirm('Are you sure you want to leave this Circle?')) return;

    try {
      setActionLoading(circleId);
      await apiClient.leaveCircle(circleId);
      await loadCircles();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to leave Circle');
    } finally {
      setActionLoading(null);
    }
  };

  const handleCreateCircle = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreateError(null);

    if (!createForm.name.trim()) {
      setCreateError('Circle name is required');
      return;
    }

    try {
      setCreateLoading(true);
      const response = await apiClient.createCircle({
        name: createForm.name.trim(),
        description: createForm.description?.trim() || undefined,
        is_public: createForm.is_public,
      });

      // Navigate to the new Circle details page
      navigate(`/circles/${response.circle.circle_id}`);
    } catch (err) {
      setCreateError(extractErrorMessage(err) || 'Failed to create Circle');
    } finally {
      setCreateLoading(false);
    }
  };

  const handleCloseCreateModal = () => {
    setShowCreateModal(false);
    setCreateForm({ name: '', description: '', is_public: true });
    setCreateError(null);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
      <div className="tile-card p-6 md:p-8">
        <div className="flex items-center justify-between mb-6">
          <h1 className="text-3xl font-display font-bold text-ccl-navy">Circles</h1>
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-ccl-orange text-white font-bold py-2 px-6 rounded-tile shadow-tile hover:shadow-tile-sm transition-all"
          >
            Create Circle
          </button>
        </div>

        <p className="text-ccl-navy mb-6">
          Join or create Circles to play with friends. Circle members see each other's captions more often.
        </p>

        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {loading ? (
          <div className="py-10 flex justify-center">
            <LoadingSpinner isLoading message="Loading Circles..." />
          </div>
        ) : circles.length === 0 ? (
          <div className="text-center py-10">
            <p className="text-ccl-navy/70 mb-4">No Circles found. Create one to get started!</p>
          </div>
        ) : (
          <div className="space-y-4">
            {circles.map((circle) => (
              <div
                key={circle.circle_id}
                className="border-2 border-ccl-navy rounded-tile p-4 bg-white hover:shadow-tile-sm transition-shadow"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <h3 className="text-xl font-display font-bold text-ccl-navy mb-1">
                      {circle.name}
                    </h3>
                    {circle.description && (
                      <p className="text-ccl-navy/70 mb-2">{circle.description}</p>
                    )}
                    <div className="flex items-center gap-4 text-sm text-ccl-navy/60">
                      <span>{circle.member_count} {circle.member_count === 1 ? 'member' : 'members'}</span>
                      <span>{circle.is_public ? 'Public' : 'Private'}</span>
                      {circle.is_admin && (
                        <span className="text-ccl-orange font-bold">Admin</span>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-col gap-2 ml-4">
                    {circle.is_member ? (
                      <>
                        <button
                          onClick={() => navigate(`/circles/${circle.circle_id}`)}
                          className="bg-ccl-teal text-white font-bold py-2 px-4 rounded-tile shadow-tile hover:shadow-tile-sm transition-all whitespace-nowrap"
                        >
                          View
                        </button>
                        <button
                          onClick={() => handleLeaveCircle(circle.circle_id)}
                          disabled={actionLoading === circle.circle_id}
                          className="bg-ccl-navy/10 text-ccl-navy font-bold py-2 px-4 rounded-tile hover:bg-ccl-navy/20 transition-all whitespace-nowrap disabled:opacity-50"
                        >
                          {actionLoading === circle.circle_id ? 'Leaving...' : 'Leave'}
                        </button>
                      </>
                    ) : circle.has_pending_request ? (
                      <button
                        disabled
                        className="bg-ccl-navy/20 text-ccl-navy/60 font-bold py-2 px-4 rounded-tile whitespace-nowrap"
                      >
                        Request Pending
                      </button>
                    ) : (
                      <button
                        onClick={() => handleJoinCircle(circle.circle_id)}
                        disabled={actionLoading === circle.circle_id}
                        className="bg-ccl-orange text-white font-bold py-2 px-4 rounded-tile shadow-tile hover:shadow-tile-sm transition-all whitespace-nowrap disabled:opacity-50"
                      >
                        {actionLoading === circle.circle_id ? 'Joining...' : 'Request to Join'}
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Circle Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-tile p-6 max-w-md w-full shadow-tile">
            <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Create a Circle</h2>

            {createError && (
              <div className="mb-4 p-3 bg-red-100 border border-red-400 text-red-700 rounded text-sm">
                {createError}
              </div>
            )}

            <form onSubmit={handleCreateCircle}>
              <div className="mb-4">
                <label className="block text-ccl-navy font-bold mb-2">
                  Circle Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  maxLength={100}
                  className="w-full px-3 py-2 border-2 border-ccl-navy rounded focus:outline-none focus:ring-2 focus:ring-ccl-orange"
                  placeholder="My Awesome Circle"
                  disabled={createLoading}
                />
              </div>

              <div className="mb-4">
                <label className="block text-ccl-navy font-bold mb-2">
                  Description (Optional)
                </label>
                <textarea
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  maxLength={500}
                  rows={3}
                  className="w-full px-3 py-2 border-2 border-ccl-navy rounded focus:outline-none focus:ring-2 focus:ring-ccl-orange"
                  placeholder="A brief description of your Circle..."
                  disabled={createLoading}
                />
              </div>

              <div className="mb-6">
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={createForm.is_public}
                    onChange={(e) => setCreateForm({ ...createForm, is_public: e.target.checked })}
                    className="w-4 h-4"
                    disabled={createLoading}
                  />
                  <span className="text-ccl-navy">Public (anyone can request to join)</span>
                </label>
              </div>

              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={handleCloseCreateModal}
                  disabled={createLoading}
                  className="flex-1 bg-ccl-navy/10 text-ccl-navy font-bold py-2 px-4 rounded-tile hover:bg-ccl-navy/20 transition-all disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={createLoading}
                  className="flex-1 bg-ccl-orange text-white font-bold py-2 px-4 rounded-tile shadow-tile hover:shadow-tile-sm transition-all disabled:opacity-50"
                >
                  {createLoading ? 'Creating...' : 'Create'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Circles;
