import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import { BalanceFlipper } from './BalanceFlipper';
import SubHeader from './SubHeader';
import { ArrowLeftIcon } from './icons/ArrowIcons';
import { HomeIcon, SettingsIcon } from './icons/NavigationIcons';

const Header: React.FC = () => {
  const { player, logout, isAuthenticated } = useIRGame();
  const navigate = useNavigate();
  const location = useLocation();

  const [showDropdown, setShowDropdown] = React.useState(false);
  const [showGuestWarning, setShowGuestWarning] = React.useState(false);
  const [guestCredentials, setGuestCredentials] = React.useState<{ email: string | null; password: string | null } | null>(null);
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
    if (!player?.is_guest) {
      logout();
      return;
    }

    let email: string | null = player?.email ?? null;
    let password: string | null = null;

    if (typeof window !== 'undefined') {
      try {
        const stored = window.localStorage.getItem('ir_guest_credentials');
        if (stored) {
          const parsed = JSON.parse(stored) as { email?: string; password?: string };
          if (parsed.email) {
            email = parsed.email;
          }
          if (parsed.password) {
            password = parsed.password;
          }
        }
      } catch (err) {
        console.warn('Failed to read guest credentials from storage', err);
      }
    }

    setGuestCredentials({ email, password });
    setShowGuestWarning(true);
  }, [player?.is_guest, player?.email, logout]);

  const handleDismissGuestLogout = React.useCallback(() => {
    setShowGuestWarning(false);
    setGuestCredentials(null);
  }, []);

  const handleConfirmGuestLogout = React.useCallback(() => {
    setShowGuestWarning(false);
    setGuestCredentials(null);
    logout();
  }, [logout]);

  if (!isAuthenticated || !player) {
    return null;
  }

  const logoTitle = 'Open menu';
  const backArrowTitle = 'Go back';

  return (
    <>
      {/* Guest Logout Warning Modal */}
      {showGuestWarning && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-[200] px-4">
          <div className="tile-card max-w-md w-full p-6">
            <h3 className="text-xl font-display font-bold text-ir-navy mb-4">Logout as Guest?</h3>
            <p className="text-ir-teal mb-4">
              You're logged in as a guest. If you log out without upgrading to a full account, you may lose access to this account.
            </p>
            {guestCredentials?.email && (
              <div className="mb-4 p-3 bg-ir-teal-light rounded-lg">
                <p className="text-sm text-ir-navy">
                  <strong>Username:</strong> {player.username}
                </p>
                {guestCredentials.email && (
                  <p className="text-sm text-ir-navy">
                    <strong>Email:</strong> {guestCredentials.email}
                  </p>
                )}
                {guestCredentials.password && (
                  <p className="text-sm text-ir-navy mt-2">
                    <strong>Password:</strong> {guestCredentials.password}
                  </p>
                )}
              </div>
            )}
            <div className="flex gap-3">
              <button
                onClick={handleDismissGuestLogout}
                className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-tile transition-colors font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmGuestLogout}
                className="flex-1 px-4 py-2 bg-ir-orange hover:bg-ir-orange-deep text-white rounded-tile transition-colors font-semibold"
              >
                Logout Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Header */}
      <div className="bg-ir-warm-ivory shadow-tile-sm relative z-50">
        <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
          <div className="flex justify-between items-center">
            {/* Left: Logo + Back Arrow */}
            <div className="flex items-center gap-0.5 md:gap-3 relative">
              {showBackArrow && (
                <button
                  type="button"
                  onClick={handleBackArrowClick}
                  className="cursor-pointer transition-opacity hover:opacity-80"
                  title={backArrowTitle}
                  aria-label={backArrowTitle}
                >
                  <ArrowLeftIcon className="w-7 h-7 md:w-9 md:h-9" aria-hidden="true" />
                </button>
              )}
              <button
                ref={logoButtonRef}
                type="button"
                onClick={handleLogoClick}
                className="cursor-pointer transition-opacity hover:opacity-90"
                title={logoTitle}
                aria-label={logoTitle}
              >
                <img src="/landing_logo.png" alt="Initial Reaction" className="md:h-11 h-9 w-auto" />
              </button>

              {/* Dropdown Menu */}
              {showDropdown && (
                <div
                  ref={dropdownRef}
                  className="absolute top-full left-0 mt-2 w-48 bg-white rounded-tile shadow-tile-lg border-2 border-ir-navy border-opacity-10 z-[100] slide-up-enter"
                >
                  <div className="py-2">
                    <button
                      onClick={() => handleNavigate('/dashboard')}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left text-ir-teal hover:bg-ir-cream transition-colors"
                    >
                      <HomeIcon className="h-5 w-5" />
                      <span className="font-semibold">Dashboard</span>
                    </button>

                    <button
                      onClick={() => handleNavigate('/settings')}
                      className="w-full flex items-center gap-3 px-4 py-3 text-left text-ir-navy hover:bg-ir-cream transition-colors"
                    >
                      <SettingsIcon className="h-5 w-5" />
                      <span className="font-semibold">Settings</span>
                    </button>

                    {player.is_guest && (
                      <button
                        onClick={() => handleNavigate('/settings')}
                        className="w-full flex items-center gap-3 px-4 py-3 text-left text-ir-navy hover:bg-ir-cream transition-colors"
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

                    {player.is_guest && (
                      <>
                        <div className="border-t border-ir-navy border-opacity-10 my-2"></div>

                        <button
                          onClick={() => {
                            setShowDropdown(false);
                            handleLogoutClick();
                          }}
                          className="w-full flex items-center gap-3 px-4 py-3 text-left text-ir-teal hover:bg-ir-cream transition-colors"
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
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Center: Username */}
            <div className="flex-1 text-center">
              <div className="text-lg md:text-2xl text-ir-turquoise font-semibold">
                <div className="flex items-center justify-center gap-2 md:gap-3">
                  <span>{player.username}</span>
                  {player.is_guest && (
                    <span className="text-xs md:text-sm bg-ir-orange bg-opacity-20 text-ir-orange-deep px-2 py-0.5 rounded-full font-bold">
                      Guest
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Right: Wallet + Vault + Logout (guest only) */}
            <div className="flex items-center gap-0.5 md:gap-4">
              {/* Wallet Balance */}
              <button
                type="button"
                className="flex items-center gap-0.5 border border-white/10 rounded-xl px-1 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ir-teal"
                title="Wallet balance"
                aria-label="Wallet balance"
              >
                <img src="/wallet.png" alt="Wallet" className="w-5 h-5 md:w-7 md:h-7" />
                <BalanceFlipper
                  value={player.wallet}
                  className="text-xl md:text-2xl font-display font-bold text-ir-turquoise"
                />
              </button>

              {/* Vault Balance */}
              <button
                type="button"
                className="flex items-center gap-0.5 border border-white/10 rounded-xl px-1 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ir-teal"
                title="Vault balance"
                aria-label="Vault balance"
              >
                <img src="/vault.png" alt="Vault" className="w-5 h-5 md:w-7 md:h-7" />
                <BalanceFlipper
                  value={player.vault}
                  className="text-xl md:text-2xl font-display font-bold text-ir-turquoise"
                />
              </button>

              {/* Logout Button - Only visible for guests */}
              {player.is_guest && (
                <button
                  onClick={handleLogoutClick}
                  className="text-ir-teal hover:text-ir-turquoise"
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
