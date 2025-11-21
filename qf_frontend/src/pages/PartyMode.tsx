import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient from '../api/client';
import { PartyIcon } from '../components/icons/NavigationIcons';
import type { PartyListItem } from '../api/types';

/**
 * Party Mode entry page - Create or Join a party session
 */
export const PartyMode: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();
  const [parties, setParties] = useState<PartyListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isCreating, setIsCreating] = useState(false);
  const [joiningSessionId, setJoiningSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleCreateParty = async () => {
    if (!player) return;

    setIsCreating(true);
    setError(null);

    try {
      const response = await apiClient.createPartySession({
        min_players: 6,
        max_players: 9,
        prompts_per_player: 1,
        copies_per_player: 2,
        votes_per_player: 3,
      });

      // Navigate to party lobby
      navigate(`/party/${response.session_id}`);
    } catch (err: unknown) {
      if (axios.isAxiosError<{ detail?: string }>(err)) {
        const detail = err.response?.data?.detail;
        if (detail === 'already_in_another_session') {
          setError('You already have an active party. Leave it before creating a new one.');
        } else {
          setError(detail || err.message || 'Failed to create party');
        }
      } else {
        setError(err instanceof Error ? err.message : 'Failed to create party');
      }
    } finally {
      setIsCreating(false);
    }
  };

  const loadParties = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.listActiveParties();
      setParties(response.parties);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load parties');
    } finally {
      setIsLoading(false);
    }
  };

  const handleJoinParty = async (sessionId: string) => {
    if (!player) return;

    setJoiningSessionId(sessionId);
    setError(null);

    try {
      const response = await apiClient.joinPartySessionById(sessionId);

      // Navigate to party lobby
      navigate(`/party/${response.session_id}`);
    } catch (err: unknown) {
      if (axios.isAxiosError<{ detail?: string }>(err)) {
        const detail = err.response?.data?.detail;
        if (detail === 'already_in_another_session') {
          setError('You are already in another party. Leave it before joining a new one.');
        } else {
          setError(detail || err.message || 'Failed to join party');
        }
      } else {
        setError(err instanceof Error ? err.message : 'Failed to join party');
      }
    } finally {
      setJoiningSessionId(null);
    }
  };

  // Load parties on mount and refresh every 5 seconds
  useEffect(() => {
    // Only start polling if authenticated
    if (!state.isAuthenticated) {
      return;
    }

    loadParties();
    const interval = setInterval(loadParties, 5000);
    return () => clearInterval(interval);
  }, [state.isAuthenticated]); // Key: depend on auth state

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-md w-full tile-card p-8 slide-up-enter space-y-6">
        {/* Header */}
        <div className="text-center mb-2">
          <div className="flex items-center justify-center gap-2 mb-2">
            <PartyIcon className="w-12 h-12" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Party Mode</h1>
          </div>
          <p className="text-quip-teal">Play with 6-9 players!</p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-100 border-2 border-red-400 rounded-tile p-4">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Create Party */}
        <div className="bg-quip-orange bg-opacity-5 border-2 border-quip-orange rounded-tile p-6">
          <h2 className="text-xl font-display font-bold text-quip-navy mb-2">Create a Party</h2>
          <p className="text-quip-teal mb-4 text-sm">
            Host a new party match with 6-9 players. You'll get a code to share with friends.
          </p>
          <button
            onClick={handleCreateParty}
            disabled={isCreating}
            className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
          >
            {isCreating ? 'Creating...' : 'Create Party'}
          </button>
        </div>

        {/* Divider */}
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-quip-teal opacity-30"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-quip-warm-ivory text-quip-teal font-semibold">OR</span>
          </div>
        </div>

        {/* Join Party */}
        <div className="bg-quip-turquoise bg-opacity-5 border-2 border-quip-turquoise rounded-tile p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-xl font-display font-bold text-quip-navy">Join a Party</h2>
            <button
              onClick={loadParties}
              disabled={isLoading}
              className="text-quip-turquoise hover:text-quip-teal transition-colors"
              title="Refresh party list"
            >
              <svg className={`w-5 h-5 ${isLoading ? 'animate-spin' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
          </div>
          <p className="text-quip-teal mb-4 text-sm">
            Browse available parties and join with one click.
          </p>

          {/* Party List */}
          {isLoading && parties.length === 0 ? (
            <div className="text-center py-8 text-quip-teal">
              <svg className="animate-spin h-8 w-8 mx-auto mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Loading parties...
            </div>
          ) : parties.length === 0 ? (
            <div className="text-center py-8 text-quip-teal">
              <p className="mb-2">No parties available</p>
              <p className="text-sm">Be the first to create one!</p>
            </div>
          ) : (
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {parties.map((party) => (
                <div
                  key={party.session_id}
                  className="bg-white border-2 border-quip-teal rounded-tile p-3 flex items-center justify-between hover:border-quip-turquoise transition-colors"
                >
                  <div className="flex-1">
                    <p className="font-bold text-quip-navy">{party.host_username}'s Party</p>
                    <p className="text-sm text-quip-teal">
                      {party.participant_count} / {party.max_players} players
                      {party.participant_count >= party.min_players && (
                        <span className="ml-2 text-xs bg-quip-turquoise text-white px-2 py-0.5 rounded">Ready to start</span>
                      )}
                    </p>
                  </div>
                  <button
                    onClick={() => handleJoinParty(party.session_id)}
                    disabled={joiningSessionId === party.session_id}
                    className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-2 px-4 rounded-tile transition-all text-sm"
                  >
                    {joiningSessionId === party.session_id ? 'Joining...' : 'Join'}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Back to Dashboard */}
        <button
          onClick={() => navigate('/dashboard')}
          className="w-full mt-4 flex items-center justify-center gap-2 text-quip-teal hover:text-quip-turquoise py-2 font-medium transition-colors"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
          </svg>
          <span>Back to Dashboard</span>
        </button>
      </div>
    </div>
  );
};

export default PartyMode;
