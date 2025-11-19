import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient from '../api/client';
import { Header } from '../components/Header';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

/**
 * Party Mode entry page - Create or Join a party session
 */
export const PartyMode: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();
  const [partyCode, setPartyCode] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateParty = async () => {
    if (!player) return;

    setIsCreating(true);
    setError(null);

    try {
      const response = await apiClient.createPartySession({
        min_players: 3,
        max_players: 8,
        prompts_per_player: 1,
        copies_per_player: 2,
        votes_per_player: 3,
      });

      // Navigate to party lobby
      navigate(`/party/${response.session_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create party');
    } finally {
      setIsCreating(false);
    }
  };

  const handleJoinParty = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!player || !partyCode.trim()) return;

    setIsJoining(true);
    setError(null);

    try {
      const response = await apiClient.joinPartySession(partyCode.trim().toUpperCase());

      // Navigate to party lobby
      navigate(`/party/${response.session_id}`);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to join party');
    } finally {
      setIsJoining(false);
    }
  };

  return (
    <div className="flex min-h-screen flex-col bg-quip-navy/5">
      <Header title="Party Mode" />

      <div className="flex-grow flex items-center justify-center p-4">
        <div className="max-w-md w-full space-y-8">
          {/* Player Info */}
          {player && (
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center justify-between">
                <span className="font-semibold text-quip-navy">{player.username}</span>
                <CurrencyDisplay wallet={player.wallet} vault={player.vault} showVault={false} />
              </div>
            </div>
          )}

          {/* Error Display */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-sm text-red-800">{error}</p>
            </div>
          )}

          {/* Create Party */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-quip-navy mb-4">Create a Party</h2>
            <p className="text-gray-600 mb-4">
              Host a new party match with 3-8 players. You'll get a code to share with friends.
            </p>
            <button
              onClick={handleCreateParty}
              disabled={isCreating}
              className="w-full bg-quip-blue hover:bg-quip-blue/90 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
            >
              {isCreating ? 'Creating...' : 'Create Party'}
            </button>
          </div>

          {/* Join Party */}
          <div className="bg-white rounded-lg shadow p-6">
            <h2 className="text-xl font-bold text-quip-navy mb-4">Join a Party</h2>
            <p className="text-gray-600 mb-4">
              Enter an 8-character party code to join an existing match.
            </p>
            <form onSubmit={handleJoinParty} className="space-y-4">
              <input
                type="text"
                value={partyCode}
                onChange={(e) => setPartyCode(e.target.value.toUpperCase())}
                placeholder="Enter Party Code"
                maxLength={8}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg text-center text-2xl font-mono uppercase tracking-widest focus:outline-none focus:ring-2 focus:ring-quip-blue"
              />
              <button
                type="submit"
                disabled={isJoining || partyCode.length !== 8}
                className="w-full bg-quip-green hover:bg-quip-green/90 disabled:bg-gray-400 text-white font-semibold py-3 px-4 rounded-lg transition-colors"
              >
                {isJoining ? 'Joining...' : 'Join Party'}
              </button>
            </form>
          </div>

          {/* Back to Dashboard */}
          <button
            onClick={() => navigate('/dashboard')}
            className="w-full text-quip-navy hover:text-quip-blue font-medium"
          >
            ← Back to Dashboard
          </button>
        </div>
      </div>
    </div>
  );
};

export default PartyMode;
