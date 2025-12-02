import React, { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import apiClient, { extractErrorMessage } from '@/api/client';
import type { Circle, CircleMember, CircleJoinRequest } from '@crowdcraft/api/types.ts';
import { LoadingSpinner } from '../components/LoadingSpinner';
import { formatDateTimeInUserZone } from '@crowdcraft/utils/datetime.ts';

export const CircleDetails: React.FC = () => {
  const { circleId } = useParams<{ circleId: string }>();
  const navigate = useNavigate();

  const [circle, setCircle] = useState<Circle | null>(null);
  const [members, setMembers] = useState<CircleMember[]>([]);
  const [joinRequests, setJoinRequests] = useState<CircleJoinRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const loadCircleData = useCallback(async () => {
    if (!circleId) return;

    try {
      setLoading(true);
      setError(null);

      const [circleData, membersData] = await Promise.all([
        apiClient.getCircle(circleId),
        apiClient.getCircleMembers(circleId),
      ]);

      setCircle(circleData);
      setMembers(membersData.members);

      // Load join requests if user is admin
      if (circleData.is_admin) {
        try {
          const requestsData = await apiClient.getCircleJoinRequests(circleId);
          setJoinRequests(requestsData.join_requests);
        } catch (err) {
          // Ignore 403 errors (non-admins can't see join requests)
          console.warn('Failed to load join requests:', err);
        }
      }
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to load Circle details');
    } finally {
      setLoading(false);
    }
  }, [circleId]);

  useEffect(() => {
    if (circleId) {
      loadCircleData();
    }
  }, [circleId, loadCircleData]);

  const handleApproveRequest = async (requestId: string) => {
    if (!circleId) return;

    try {
      setActionLoading(`approve-${requestId}`);
      await apiClient.approveJoinRequest(circleId, requestId);
      await loadCircleData(); // Refresh data
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to approve request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleDenyRequest = async (requestId: string) => {
    if (!circleId) return;

    try {
      setActionLoading(`deny-${requestId}`);
      await apiClient.denyJoinRequest(circleId, requestId);
      await loadCircleData();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to deny request');
    } finally {
      setActionLoading(null);
    }
  };

  const handleRemoveMember = async (playerId: string, username: string) => {
    if (!circleId) return;
    if (!confirm(`Remove ${username} from this Circle?`)) return;

    try {
      setActionLoading(`remove-${playerId}`);
      await apiClient.removeCircleMember(circleId, playerId);
      await loadCircleData();
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to remove member');
    } finally {
      setActionLoading(null);
    }
  };

  const handleLeaveCircle = async () => {
    if (!circleId) return;
    if (!confirm('Are you sure you want to leave this Circle?')) return;

    try {
      setActionLoading('leave');
      await apiClient.leaveCircle(circleId);
      navigate('/circles');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to leave Circle');
      setActionLoading(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
        <div className="tile-card p-6 md:p-8">
          <LoadingSpinner isLoading message="Loading Circle details..." />
        </div>
      </div>
    );
  }

  if (!circle) {
    return (
      <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
        <div className="tile-card p-6 md:p-8">
          <p className="text-red-600">Circle not found</p>
          <button
            onClick={() => navigate('/circles')}
            className="mt-4 bg-ccl-navy text-white font-bold py-2 px-4 rounded-tile"
          >
            Back to Circles
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 pb-12 pt-4">
      <div className="tile-card p-6 md:p-8">
        {/* Header */}
        <div className="mb-6">
          <button
            onClick={() => navigate('/circles')}
            className="text-ccl-teal hover:text-ccl-teal/80 mb-4 inline-flex items-center gap-2"
          >
            ← Back to Circles
          </button>
          <div className="flex items-start justify-between">
            <div>
              <h1 className="text-3xl font-display font-bold text-ccl-navy mb-2">
                {circle.name}
              </h1>
              {circle.description && (
                <p className="text-ccl-navy/70 mb-2">{circle.description}</p>
              )}
              <div className="flex items-center gap-4 text-sm text-ccl-navy/60">
                <span>{circle.member_count} {circle.member_count === 1 ? 'member' : 'members'}</span>
                <span>{circle.is_public ? 'Public' : 'Private'}</span>
                {circle.is_admin && (
                  <span className="text-ccl-orange font-bold">You are an Admin</span>
                )}
              </div>
            </div>
            {circle.is_member && (
              <button
                onClick={handleLeaveCircle}
                disabled={actionLoading === 'leave'}
                className="bg-ccl-navy/10 text-ccl-navy font-bold py-2 px-4 rounded-tile hover:bg-ccl-navy/20 transition-all disabled:opacity-50"
              >
                {actionLoading === 'leave' ? 'Leaving...' : 'Leave Circle'}
              </button>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {/* Join Requests (Admin Only) */}
        {circle.is_admin && joinRequests.length > 0 && (
          <div className="mb-6">
            <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">
              Pending Join Requests ({joinRequests.length})
            </h2>
            <div className="space-y-3">
              {joinRequests.map((request) => (
                <div
                  key={request.request_id}
                  className="border-2 border-ccl-orange rounded-tile p-4 bg-ccl-orange/5"
                >
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="font-bold text-ccl-navy">{request.username}</p>
                      <p className="text-sm text-ccl-navy/60">
                        Requested {formatDateTimeInUserZone(request.requested_at, { fallback: 'recently' })}
                      </p>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApproveRequest(request.request_id)}
                        disabled={actionLoading === `approve-${request.request_id}`}
                        className="bg-ccl-teal text-white font-bold py-2 px-4 rounded-tile shadow-tile hover:shadow-tile-sm transition-all disabled:opacity-50"
                      >
                        {actionLoading === `approve-${request.request_id}` ? 'Approving...' : 'Approve'}
                      </button>
                      <button
                        onClick={() => handleDenyRequest(request.request_id)}
                        disabled={actionLoading === `deny-${request.request_id}`}
                        className="bg-ccl-navy/10 text-ccl-navy font-bold py-2 px-4 rounded-tile hover:bg-ccl-navy/20 transition-all disabled:opacity-50"
                      >
                        {actionLoading === `deny-${request.request_id}` ? 'Denying...' : 'Deny'}
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Members */}
        <div>
          <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">
            Members ({members.length})
          </h2>
          {members.length === 0 ? (
            <p className="text-ccl-navy/70">No members yet</p>
          ) : (
            <div className="space-y-2">
              {members.map((member) => (
                <div
                  key={member.player_id}
                  className="border-2 border-ccl-navy/20 rounded-tile p-3 bg-white flex items-center justify-between"
                >
                  <div>
                    <p className="font-bold text-ccl-navy">
                      {member.username}
                      {member.role === 'admin' && (
                        <span className="ml-2 text-xs bg-ccl-orange text-white px-2 py-1 rounded">
                          Admin
                        </span>
                      )}
                    </p>
                    <p className="text-sm text-ccl-navy/60">
                      Joined {formatDateTimeInUserZone(member.joined_at, { fallback: 'recently' })}
                    </p>
                  </div>
                  {circle.is_admin && member.role !== 'admin' && (
                    <button
                      onClick={() => handleRemoveMember(member.player_id, member.username)}
                      disabled={actionLoading === `remove-${member.player_id}`}
                      className="bg-ccl-navy/10 text-ccl-navy text-sm font-bold py-1 px-3 rounded hover:bg-ccl-navy/20 transition-all disabled:opacity-50"
                    >
                      {actionLoading === `remove-${member.player_id}` ? 'Removing...' : 'Remove'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default CircleDetails;
