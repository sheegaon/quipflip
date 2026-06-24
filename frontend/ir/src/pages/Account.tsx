import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Header from '../components/Header';
import MagicLinkPanel from '@crowdcraft/components/MagicLinkPanel.tsx';
import { playerAPI } from '@/api/client.ts';
import { GUEST_CREDENTIALS_KEY } from '../utils/storageKeys';

const Account: React.FC = () => {
  const navigate = useNavigate();
  const { player, pendingResults } = useIRGame();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stats, setStats] = useState<Awaited<ReturnType<typeof playerAPI.getStatistics>> | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchStats = async () => {
      if (!player?.player_id) {
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        setError(null);
        const response = await playerAPI.getStatistics();
        if (!cancelled) {
          setStats(response);
        }
      } catch (err) {
        if (!cancelled) {
          const message = err instanceof Error ? err.message : 'Failed to load account statistics';
          setError(message);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    };

    void fetchStats();

    return () => {
      cancelled = true;
    };
  }, [player?.player_id]);

  if (!player) {
    return (
      <div className="min-h-screen bg-ir-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    );
  }

  const hasCompletedHistory = Boolean(
    stats && (stats.entries_submitted > 0 || stats.votes_cast > 0 || stats.net_earnings !== 0 || pendingResults.length > 0),
  );

  return (
    <div className="min-h-screen bg-ir-cream bg-pattern">
      <Header />

      <div className="container mx-auto px-4 py-8">
        <div className="tile-card p-6 mb-6">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-display font-bold text-ir-navy">{player.username}</h1>
              <p className="text-ir-teal mt-1">
                {player.email ?? 'No email saved yet'}
              </p>
            </div>
            <button
              type="button"
              onClick={() => navigate('/settings')}
              className="rounded-tile border border-ir-teal px-4 py-2 font-semibold text-ir-teal transition hover:bg-ir-cream"
            >
              Open settings
            </button>
          </div>
        </div>

        {player.is_guest && hasCompletedHistory && (
          <div className="tile-card p-6 mb-6 bg-ir-orange bg-opacity-10 border-2 border-ir-orange">
            <MagicLinkPanel
              mode="save"
              title="Keep your stats"
              description="Save your name, wins, and backronym history across devices."
              ctaLabel="Save my account"
              guestPlayerId={player.player_id}
              currentSummary={stats ? `${stats.entries_submitted} entries • ${stats.votes_cast} votes` : undefined}
              guestCredentialsStorageKey={GUEST_CREDENTIALS_KEY}
            />
          </div>
        )}

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="tile-card p-5">
            <p className="text-sm text-ir-teal uppercase tracking-wide">Wallet</p>
            <p className="mt-2 text-3xl font-display font-bold text-ir-navy">{player.wallet ?? 0}</p>
          </div>
          <div className="tile-card p-5">
            <p className="text-sm text-ir-teal uppercase tracking-wide">Vault</p>
            <p className="mt-2 text-3xl font-display font-bold text-ir-navy">{player.vault ?? 0}</p>
          </div>
          <div className="tile-card p-5">
            <p className="text-sm text-ir-teal uppercase tracking-wide">Entries</p>
            <p className="mt-2 text-3xl font-display font-bold text-ir-navy">{stats?.entries_submitted ?? 0}</p>
          </div>
          <div className="tile-card p-5">
            <p className="text-sm text-ir-teal uppercase tracking-wide">Votes</p>
            <p className="mt-2 text-3xl font-display font-bold text-ir-navy">{stats?.votes_cast ?? 0}</p>
          </div>
        </div>

        <div className="tile-card p-6 mt-6">
          <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">Account summary</h2>
          {loading ? (
            <p className="text-ir-teal">Loading account statistics...</p>
          ) : error ? (
            <p className="text-red-700">{error}</p>
          ) : stats ? (
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <p className="text-sm text-ir-teal">Net earnings</p>
                <p className="text-xl font-semibold text-ir-navy">{stats.net_earnings}</p>
              </div>
              <div>
                <p className="text-sm text-ir-teal">Submitted entries</p>
                <p className="text-xl font-semibold text-ir-navy">{stats.entries_submitted}</p>
              </div>
              <div>
                <p className="text-sm text-ir-teal">Votes cast</p>
                <p className="text-xl font-semibold text-ir-navy">{stats.votes_cast}</p>
              </div>
            </div>
          ) : (
            <p className="text-ir-teal">No account statistics yet.</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Account;
