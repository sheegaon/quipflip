import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient from '@crowdcraft/api/client.ts';
import { Header } from '../components/Header';
import type { QFPartyResultsResponse, QFPartyPlayerStats, QFPartyAward } from '@crowdcraft/api/types.ts';

/**
 * Party Results page - Displays match results, rankings, and awards
 */
export const PartyResults: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();

  const [results, setResults] = useState<QFPartyResultsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const loadResults = async () => {
      if (!sessionId) return;

      try {
        const data = await apiClient.qfGetPartyResults(sessionId);
        setResults(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load results');
      } finally {
        setLoading(false);
      }
    };

    loadResults();
  }, [sessionId]);

  const getRankColor = (rank: number) => {
    switch (rank) {
      case 1:
        return 'bg-ccl-orange text-white';
      case 2:
        return 'bg-gray-400 text-white';
      case 3:
        return 'bg-quest-milestone text-white';
      default:
        return 'bg-gray-200 text-ccl-navy';
    }
  };

  const getRankIcon = (rank: number) => {
    switch (rank) {
      case 1:
        return '🥇';
      case 2:
        return '🥈';
      case 3:
        return '🥉';
      default:
        return `#${rank}`;
    }
  };

  const getAwardIcon = (awardType: string) => {
    switch (awardType) {
      case 'best_writer':
        return '✍️';
      case 'top_impostor':
        return '🎭';
      case 'sharpest_voter':
        return '🎯';
      default:
        return '🏆';
    }
  };

  const getAwardTitle = (awardType: string) => {
    switch (awardType) {
      case 'best_writer':
        return 'Best Writer';
      case 'top_impostor':
        return 'Top Impostor';
      case 'sharpest_voter':
        return 'Sharpest Voter';
      default:
        return 'Award';
    }
  };

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col bg-ccl-cream">
        <Header />
        <div className="flex-grow flex items-center justify-center">
          <span className="text-lg font-semibold text-ccl-navy">Loading results...</span>
        </div>
      </div>
    );
  }

  if (error || !results) {
    return (
      <div className="flex min-h-screen flex-col bg-ccl-cream">
        <Header />
        <div className="flex-grow flex items-center justify-center p-4">
          <div className="max-w-md w-full space-y-4">
            <div className="tile-card bg-red-100 border-2 border-red-400 p-4">
              <p className="text-sm text-red-800">{error || 'Results not available'}</p>
            </div>
            <button
              onClick={() => navigate('/party')}
              className="w-full bg-ccl-navy hover:bg-ccl-teal text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Back to Party Mode
            </button>
          </div>
        </div>
      </div>
    );
  }

  const currentPlayerStats = results.rankings.find(r => r.player_id === player?.player_id);

  return (
    <div className="flex min-h-screen flex-col bg-ccl-cream">
      <Header />

      <div className="flex-grow p-4">
        <div className="max-w-4xl mx-auto space-y-6">
          {/* Header */}
          <div className="text-center py-6">
            <h1 className="text-4xl font-display font-bold text-ccl-navy mb-2">🎉 Party Results 🎉</h1>
            <p className="text-lg text-ccl-teal">Party Code: {results.party_code}</p>
          </div>

          {/* Awards Section */}
          {Object.keys(results.awards).length > 0 && (
            <div className="tile-card shadow-tile p-6">
              <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">🏆 Awards</h2>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {Object.entries(results.awards).map(([awardType, award]: [string, QFPartyAward]) => (
                  <div
                    key={awardType}
                    className="tile-card bg-ccl-orange bg-opacity-10 border-2 border-ccl-orange p-4 text-center"
                  >
                    <div className="text-4xl mb-2">{getAwardIcon(awardType)}</div>
                    <h3 className="font-display font-bold text-ccl-navy mb-1">{getAwardTitle(awardType)}</h3>
                    <p className="text-lg font-semibold text-ccl-orange-deep">{award.username}</p>
                    <p className="text-sm text-ccl-teal">Score: {award.metric_value}</p>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Your Stats */}
          {currentPlayerStats && (
            <div className="tile-card shadow-tile bg-ccl-turquoise text-white p-6">
              <h2 className="text-2xl font-display font-bold mb-4">Your Performance</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center">
                  <div className={`inline-flex items-center justify-center w-12 h-12 rounded-full ${getRankColor(currentPlayerStats.rank)} font-bold text-lg mb-2`}>
                    {getRankIcon(currentPlayerStats.rank)}
                  </div>
                  <p className="text-sm opacity-90">Final Rank</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-display font-bold">{currentPlayerStats.net >= 0 ? '+' : ''}{currentPlayerStats.net}</p>
                  <p className="text-sm opacity-90">Net Coins</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-display font-bold">{currentPlayerStats.vote_accuracy}%</p>
                  <p className="text-sm opacity-90">Vote Accuracy</p>
                </div>
                <div className="text-center">
                  <p className="text-3xl font-display font-bold">{currentPlayerStats.votes_fooled}</p>
                  <p className="text-sm opacity-90">Votes Fooled</p>
                </div>
              </div>
            </div>
          )}

          {/* Rankings Table */}
          <div className="tile-card shadow-tile p-6">
            <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Final Rankings</h2>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b-2 border-ccl-orange">
                    <th className="text-left py-3 px-4 font-display text-ccl-navy">Rank</th>
                    <th className="text-left py-3 px-4 font-display text-ccl-navy">Player</th>
                    <th className="text-right py-3 px-4 font-display text-ccl-navy">Net Coins</th>
                    <th className="text-right py-3 px-4 font-display text-ccl-navy">Earned</th>
                    <th className="text-right py-3 px-4 font-display text-ccl-navy">Spent</th>
                    <th className="text-right py-3 px-4 font-display text-ccl-navy">Accuracy</th>
                  </tr>
                </thead>
                <tbody>
                  {results.rankings.map((playerStat: QFPartyPlayerStats) => {
                    const isCurrentPlayer = playerStat.player_id === player?.player_id;
                    return (
                      <tr
                        key={playerStat.player_id}
                        className={`border-b border-gray-100 ${
                          isCurrentPlayer ? 'bg-ccl-turquoise bg-opacity-10 font-semibold' : ''
                        }`}
                      >
                        <td className="py-3 px-4">
                          <div className={`inline-flex items-center justify-center w-8 h-8 rounded-full ${getRankColor(playerStat.rank)} text-sm font-bold`}>
                            {playerStat.rank <= 3 ? getRankIcon(playerStat.rank) : playerStat.rank}
                          </div>
                        </td>
                        <td className="py-3 px-4 text-ccl-navy">
                          {playerStat.username}
                          {isCurrentPlayer && (
                            <span className="ml-2 px-2 py-1 text-xs font-semibold text-ccl-turquoise bg-ccl-turquoise bg-opacity-20 rounded-tile">
                              YOU
                            </span>
                          )}
                        </td>
                        <td className={`py-3 px-4 text-right font-bold ${
                          playerStat.net >= 0 ? 'text-ccl-turquoise' : 'text-quest-quality'
                        }`}>
                          {playerStat.net >= 0 ? '+' : ''}{playerStat.net}
                        </td>
                        <td className="py-3 px-4 text-right text-ccl-turquoise">{playerStat.earned}</td>
                        <td className="py-3 px-4 text-right text-quest-quality">{playerStat.spent}</td>
                        <td className="py-3 px-4 text-right text-ccl-navy">{playerStat.vote_accuracy}%</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Phrasesets Summary */}
          {results.phrasesets_summary.length > 0 && (
            <div className="tile-card shadow-tile p-6">
              <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Phrasesets</h2>
              <div className="space-y-4">
                {results.phrasesets_summary.map((ps) => (
                  <div key={ps.phraseset_id} className="tile-card border-2 border-ccl-turquoise p-4">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-semibold text-ccl-teal">{ps.prompt_text}</p>
                      <span className="text-sm text-gray-500">{ps.vote_count} votes</span>
                    </div>
                    <p className="text-xl font-display font-bold text-ccl-orange-deep mb-2">{ps.original_phrase}</p>
                    <div className="flex items-center justify-between text-sm">
                      <p className="text-ccl-teal">by {ps.original_player}</p>
                      <p className={`font-semibold ${
                        ps.most_votes === 'original' ? 'text-ccl-turquoise' : 'text-quest-quality'
                      }`}>
                        {ps.most_votes === 'original' ? '✓ Original won' : '✗ Copy won'}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Action Buttons */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <button
              onClick={() => navigate('/party')}
              className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Play Again
            </button>
            <button
              onClick={() => navigate('/dashboard')}
              className="bg-gray-200 hover:bg-gray-300 text-ccl-navy font-bold py-3 px-6 rounded-tile transition-all"
            >
              Return to Dashboard
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default PartyResults;
