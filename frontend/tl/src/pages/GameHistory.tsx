import React, { useState } from 'react';
import { useGame } from '../contexts/GameContext';

interface RoundSummary {
  round_id: string;
  prompt_text: string;
  final_coverage?: number;
  gross_payout?: number;
  created_at: string;
  status: string;
}

interface RoundDetailsType {
  round_id: string;
  prompt_text: string;
  snapshot_answer_count: number;
  final_coverage?: number;
  gross_payout?: number;
  status: string;
  strikes: number;
  created_at: string;
  ended_at?: string;
  guesses?: any[];
}

const GameHistory: React.FC = () => {
  const { state } = useGame();
  const [selectedRoundId, setSelectedRoundId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Stub data - in real implementation, would fetch from API
  const rounds: RoundSummary[] = [];
  const selectedRound: RoundDetailsType | null = null;

  if (!state.isAuthenticated) {
    return (
      <div className="p-8 text-center text-gray-500">
        Please log in to view your game history.
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-ccl-cream p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-bold text-ccl-navy mb-2">Game History</h1>
          <p className="text-gray-600">Review your past rounds and performance</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <div className="lg:col-span-1">
            <div className="bg-white rounded-lg shadow p-6">
              <h2 className="text-lg font-semibold text-gray-800 mb-4">Your Rounds</h2>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default GameHistory;
