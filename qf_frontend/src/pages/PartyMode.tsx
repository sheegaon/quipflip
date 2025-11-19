import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient from '../api/client';
import { PartyIcon } from '../components/icons/NavigationIcons';

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
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-md w-full tile-card p-8 slide-up-enter space-y-6">
        {/* Header */}
        <div className="text-center mb-2">
          <div className="flex items-center justify-center gap-2 mb-2">
            <PartyIcon className="w-12 h-12" />
            <h1 className="text-3xl font-display font-bold text-quip-navy">Party Mode</h1>
          </div>
          <p className="text-quip-teal">Play with 3-8 friends!</p>
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
            Host a new party match with 3-8 players. You'll get a code to share with friends.
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
          <h2 className="text-xl font-display font-bold text-quip-navy mb-2">Join a Party</h2>
          <p className="text-quip-teal mb-4 text-sm">
            Enter an 8-character party code to join an existing match.
          </p>
          <form onSubmit={handleJoinParty} className="space-y-4">
            <input
              type="text"
              value={partyCode}
              onChange={(e) => setPartyCode(e.target.value.toUpperCase())}
              placeholder="ABCD1234"
              maxLength={8}
              className="w-full px-4 py-3 border-2 border-quip-teal rounded-tile text-center text-2xl font-mono uppercase tracking-widest focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
            />
            <button
              type="submit"
              disabled={isJoining || partyCode.length !== 8}
              className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm text-lg"
            >
              {isJoining ? 'Joining...' : 'Join Party'}
            </button>
          </form>
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
