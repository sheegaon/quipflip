import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import SubHeader from './SubHeader';

const Header: React.FC = () => {
  const { player, logout, isAuthenticated } = useIRGame();
  const navigate = useNavigate();
  const location = useLocation();

  const [showDropdown, setShowDropdown] = React.useState(false);
  const [showGuestWarning, setShowGuestWarning] = React.useState(false);
  const dropdownRef = React.useRef<HTMLDivElement>(null);
  const logoButtonRef = React.useRef<HTMLButtonElement>(null);

  // Show back arrow on all pages except dashboard and landing
  const showBackArrow = location.pathname !== '/dashboard' && location.pathname !== '/';

  // Close dropdown when clicking outside
  React.useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(target) &&
        logoButtonRef.current &&
        !logoButtonRef.current.contains(target)
      ) {
        setShowDropdown(false);
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDropdown]);

  const handleLogoClick = React.useCallback(() => {
    setShowDropdown((prev) => !prev);
  }, []);

  const handleNavigate = React.useCallback(
    (path: string) => {
      setShowDropdown(false);
      navigate(path);
    },
    [navigate]
  );

  const handleBackArrowClick = React.useCallback(() => {
    navigate(-1);
  }, [navigate]);

  const handleLogoutClick = React.useCallback(() => {
    if (player?.is_guest) {
      setShowGuestWarning(true);
    } else {
      logout();
    }
  }, [player?.is_guest, logout]);

  const confirmGuestLogout = React.useCallback(() => {
    setShowGuestWarning(false);
    logout();
  }, [logout]);

  if (!isAuthenticated || !player) {
    return null;
  }

  return (
    <>
      {/* Guest Logout Warning Modal */}
      {showGuestWarning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[200]">
          <div className="bg-white rounded-lg shadow-xl p-6 max-w-md mx-4">
            <h3 className="text-xl font-bold text-gray-800 mb-4">Logout as Guest?</h3>
            <p className="text-gray-600 mb-6">
              You're logged in as a guest. If you log out without upgrading to a full account, you may lose access to this account.
              <br /><br />
              <strong>Username:</strong> {player.username}
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowGuestWarning(false)}
                className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition-colors font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={confirmGuestLogout}
                className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg transition-colors font-semibold"
              >
                Logout Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-gradient-to-r from-purple-600 to-indigo-600 shadow-lg relative z-50">
        <div className="max-w-6xl mx-auto px-2 py-2 md:px-4 md:py-3">
          <div className="flex justify-between items-center">
            {/* Left: Logo + Back Arrow */}
            <div className="flex items-center gap-2 md:gap-3 relative">
              {showBackArrow && (
                <button
                  type="button"
                  onClick={handleBackArrowClick}
                  className="text-white hover:text-purple-200 transition-colors"
                  title="Go back"
                  aria-label="Go back"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-7 w-7 md:h-9 md:w-9"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 19l-7-7 7-7"
                    />
                  </svg>
                </button>
              )}
              <button
                ref={logoButtonRef}
                type="button"
                onClick={handleLogoClick}
                className="hover:opacity-90 transition-opacity"
                title="Open menu"
                aria-label="Open menu"
              >
                <img src="/logo.png" alt="Initial Reaction" className="h-9 md:h-11 w-auto" />
              </button>

              {/* Dropdown Menu */}
              {showDropdown && (
                <div
                  ref={dropdownRef}
                  className="absolute top-full left-0 mt-2 w-48 bg-white rounded-lg shadow-xl border-2 border-purple-200 z-[100] animate-slideDown"
                  style={{
                    animation: 'slideDown 0.2s ease-out'
                  }}
                >
                  <div className="py-2">
                    <button
                      onClick={() => handleNavigate('/dashboard')}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 hover:bg-purple-50 transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
                      </svg>
                      <span className="font-semibold">Dashboard</span>
                    </button>

                    {player.is_guest && (
                      <button
                        onClick={() => handleNavigate('/dashboard')}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left text-gray-700 hover:bg-purple-50 transition-colors"
                      >
                        <svg
                          xmlns="http://www.w3.org/2000/svg"
                          className="h-5 w-5"
                          fill="none"
                          viewBox="0 0 24 24"
                          stroke="currentColor"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        <span className="font-semibold">Upgrade Account</span>
                      </button>
                    )}

                    <div className="border-t border-gray-200 my-2"></div>

                    <button
                      onClick={() => {
                        setShowDropdown(false);
                        handleLogoutClick();
                      }}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left text-red-600 hover:bg-red-50 transition-colors"
                    >
                      <svg
                        xmlns="http://www.w3.org/2000/svg"
                        className="h-5 w-5"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                        />
                      </svg>
                      <span className="font-semibold">Logout</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Center: Username */}
            <div className="flex-1 text-center">
              <div className="text-lg md:text-2xl text-white font-semibold">
                <div className="flex items-center justify-center gap-2">
                  <span>{player.username}</span>
                  {player.is_guest && (
                    <span className="text-xs md:text-sm bg-white/20 px-2 py-0.5 rounded-full">
                      Guest
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Wallet + Vault + Logout (guest only) */}
            <div className="flex items-center gap-1 md:gap-3">
              {/* Wallet Balance */}
              <div className="flex items-center gap-1 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl px-2 md:px-3 py-1">
                <img src="/initcoin.png" alt="Wallet" className="w-5 h-5 md:w-7 md:h-7" />
                <span className="text-lg md:text-2xl font-bold text-yellow-300">
                  {player.wallet}
                </span>
              </div>

              {/* Vault Balance */}
              <div className="flex items-center gap-1 bg-white/10 backdrop-blur-sm border border-white/20 rounded-xl px-2 md:px-3 py-1">
                <img src="/vault.png" alt="Vault" className="w-5 h-5 md:w-7 md:h-7" />
                <span className="text-lg md:text-2xl font-bold text-green-300">
                  {player.vault}
                </span>
              </div>

              {/* Logout Button - Only visible for guests */}
              {player.is_guest && (
                <button
                  onClick={handleLogoutClick}
                  className="text-white hover:text-purple-200 transition-colors"
                  title="Logout"
                >
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    className="h-7 w-7 md:h-9 md:w-9"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"
                    />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Conditionally render SubHeader on dashboard */}
      {location.pathname === '/dashboard' && <SubHeader />}
    </>
  );
};

export default Header;
