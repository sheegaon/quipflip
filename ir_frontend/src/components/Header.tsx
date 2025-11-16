import React from 'react';
import { useIRGame } from '../contexts/IRGameContext';
import InitCoinDisplay from './InitCoinDisplay';

const Header: React.FC = () => {
  const { player, logout, isAuthenticated } = useIRGame();

  return (
    <header className="bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-lg">
      <div className="container mx-auto px-4 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-4">
            <h1 className="text-2xl font-bold">Initial Reaction</h1>
            {player && (
              <span className="text-sm bg-white/20 px-3 py-1 rounded-full">
                {player.username}
                {player.is_guest && ' (Guest)'}
              </span>
            )}
          </div>

          <div className="flex items-center space-x-4">
            {player && <InitCoinDisplay wallet={player.wallet} vault={player.vault} />}
            {isAuthenticated && (
              <button
                onClick={logout}
                className="px-4 py-2 bg-white/20 hover:bg-white/30 rounded-lg transition-colors"
              >
                Logout
              </button>
            )}
          </div>
        </div>
      </div>
    </header>
  );
};

export default Header;
