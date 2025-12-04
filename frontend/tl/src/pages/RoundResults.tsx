import React from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { CurrencyDisplay } from '../components/CurrencyDisplay';

interface ResultsLocationState {
  roundId?: string;
  promptText?: string;
  finalCoverage?: number;
  grossPayout?: number;
  walletAward?: number;
  vaultAward?: number;
  matchedClusters?: number;
  totalClusters?: number;
  strikeCount?: number;
}

export const RoundResults: React.FC = () => {
  const navigate = useNavigate();
  const { state: gameState } = useGame();
  const { player } = gameState;
  const locationState = (useLocation().state as ResultsLocationState) || {};

  const promptText = locationState.promptText || 'Round Complete';
  const finalCoverage = locationState.finalCoverage ?? 0;
  const grossPayout = locationState.grossPayout ?? 0;
  const walletAward = locationState.walletAward ?? 0;
  const vaultAward = locationState.vaultAward ?? 0;
  const matchedClusters = locationState.matchedClusters ?? 0;
  const totalClusters = locationState.totalClusters ?? 0;
  const strikeCount = locationState.strikeCount ?? 0;

  const coveragePercent = Math.round(finalCoverage * 100);
  const netWalletChange = walletAward - 100; // Minus entry cost

  return (
    <div className="min-h-screen bg-ccl-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-3xl w-full">
        {/* Coverage Header */}
        <div className="tile-card p-8 md:p-10 mb-6 text-center">
          <p className="text-sm text-ccl-teal uppercase tracking-wide mb-2">Round Complete</p>
          <h1 className="text-3xl md:text-4xl font-display font-bold text-ccl-navy mb-4">
            Your Coverage
          </h1>
          <div className="text-5xl md:text-6xl font-display font-bold text-ccl-orange mb-4">
            {coveragePercent}%
          </div>
          <p className="text-ccl-teal text-lg">
            You matched {matchedClusters} of {totalClusters} clusters
          </p>
        </div>

        {/* Prompt and Round Details */}
        <div className="tile-card p-8 md:p-10 mb-6">
          <div className="mb-6">
            <p className="text-sm text-ccl-teal uppercase tracking-wide mb-2">Prompt</p>
            <p className="text-xl md:text-2xl font-display font-bold text-ccl-navy">
              {promptText}
            </p>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div className="border-2 border-ccl-navy rounded-tile p-4 text-center">
              <p className="text-sm text-ccl-teal">Strikes Used</p>
              <p className="text-2xl font-display font-bold text-ccl-navy">{strikeCount}/3</p>
            </div>
            <div className="border-2 border-ccl-navy rounded-tile p-4 text-center">
              <p className="text-sm text-ccl-teal">Entry Cost</p>
              <p className="text-2xl font-display font-bold text-ccl-navy">
                <CurrencyDisplay amount={100} />
              </p>
            </div>
            <div className="border-2 border-ccl-navy rounded-tile p-4 text-center">
              <p className="text-sm text-ccl-teal">Gross Payout</p>
              <p className="text-2xl font-display font-bold text-ccl-orange">
                <CurrencyDisplay amount={grossPayout} />
              </p>
            </div>
          </div>
        </div>

        {/* Payout Breakdown */}
        <div className="tile-card p-8 md:p-10 mb-6">
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-6">Payout Breakdown</h2>

          <div className="space-y-3">
            <div className="flex justify-between items-center p-4 border-2 border-ccl-teal rounded-tile bg-white">
              <span className="font-semibold text-ccl-navy">Gross Payout</span>
              <CurrencyDisplay amount={grossPayout} />
            </div>

            <div className="flex justify-between items-center p-4 border-2 border-ccl-orange rounded-tile bg-white">
              <span className="font-semibold text-ccl-navy">Wallet Award</span>
              <span className="text-ccl-orange font-bold">+<CurrencyDisplay amount={walletAward} /></span>
            </div>

            <div className="flex justify-between items-center p-4 border-2 border-ccl-teal rounded-tile bg-white">
              <span className="font-semibold text-ccl-navy">Vault Award</span>
              <span className="text-ccl-teal font-bold">+<CurrencyDisplay amount={vaultAward} /></span>
            </div>

            <div className="flex justify-between items-center p-4 border-2 border-red-400 rounded-tile bg-red-50">
              <span className="font-semibold text-ccl-navy">Entry Cost (Deducted)</span>
              <span className="text-red-600 font-bold">-<CurrencyDisplay amount={100} /></span>
            </div>

            <div className="flex justify-between items-center p-4 bg-gradient-to-r from-ccl-orange to-ccl-orange-deep rounded-tile text-white">
              <span className="font-bold text-lg">Net Wallet Change</span>
              <span className="text-xl font-display font-bold">
                {netWalletChange >= 0 ? '+' : ''}<CurrencyDisplay amount={netWalletChange} />
              </span>
            </div>
          </div>
        </div>

        {/* Updated Balance */}
        <div className="tile-card p-8 md:p-10 mb-6">
          <h2 className="text-xl font-display font-bold text-ccl-navy mb-4">Your New Balance</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="border-2 border-ccl-navy rounded-tile p-6 text-center">
              <p className="text-sm text-ccl-teal uppercase tracking-wide mb-2">Wallet</p>
              <p className="text-3xl font-display font-bold text-ccl-navy">
                <CurrencyDisplay amount={player?.wallet || 0} />
              </p>
            </div>
            <div className="border-2 border-ccl-teal rounded-tile p-6 text-center">
              <p className="text-sm text-ccl-teal uppercase tracking-wide mb-2">Vault</p>
              <p className="text-3xl font-display font-bold text-ccl-navy">
                <CurrencyDisplay amount={player?.vault || 0} />
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4">
          <button
            onClick={() => navigate('/dashboard')}
            className="flex-1 bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-4 px-6 rounded-tile transition-colors"
          >
            Play Again
          </button>
          <button
            onClick={() => navigate('/history')}
            className="flex-1 border-2 border-ccl-navy bg-white text-ccl-navy font-bold py-4 px-6 rounded-tile hover:bg-ccl-navy hover:text-white transition-colors"
          >
            View History
          </button>
        </div>
      </div>
    </div>
  );
};

export default RoundResults;
