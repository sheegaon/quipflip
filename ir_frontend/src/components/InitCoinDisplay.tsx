import React from 'react';

interface InitCoinDisplayProps {
  wallet: number;
  vault: number;
  showVault?: boolean;
}

const InitCoinDisplay: React.FC<InitCoinDisplayProps> = ({
  wallet,
  vault,
  showVault = true,
}) => {
  return (
    <div className="flex items-center space-x-4">
      <div className="flex items-center space-x-2 bg-white/20 px-3 py-2 rounded-lg">
        <span className="text-yellow-300 text-xl">💰</span>
        <div className="flex flex-col">
          <span className="text-xs opacity-75">Wallet</span>
          <span className="font-bold">{wallet} IC</span>
        </div>
      </div>
      {showVault && (
        <div className="flex items-center space-x-2 bg-white/20 px-3 py-2 rounded-lg">
          <span className="text-green-300 text-xl">🏦</span>
          <div className="flex flex-col">
            <span className="text-xs opacity-75">Vault</span>
            <span className="font-bold">{vault} IC</span>
          </div>
        </div>
      )}
    </div>
  );
};

export default InitCoinDisplay;
