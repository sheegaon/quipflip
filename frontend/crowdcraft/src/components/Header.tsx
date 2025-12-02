import React, { useCallback, useEffect, useRef, useState } from 'react';
import { BalanceFlipper } from './BalanceFlipper';
import { ArrowLeftIcon } from './icons/ArrowIcons';
import type { ComponentType, ReactNode } from 'react';

export interface HeaderMenuItem {
  key: string;
  label: string;
  icon: ComponentType<{ className?: string }>;
  onClick: () => void;
  variant?: 'accent' | 'default';
  iconProps?: Record<string, unknown>;
}

export interface HeaderProps {
  logoSrc: string;
  logoAlt: string;
  playerName: string;
  wallet: number;
  vault: number;
  isGuest: boolean;
  isOffline?: boolean;
  showBackArrow?: boolean;
  onBackClick?: () => void | Promise<void>;
  onStatisticsClick: () => void;
  onLogoutClick: () => void;
  dropdownSections: HeaderMenuItem[][];
  footerItems?: HeaderMenuItem[];
  logoutLabel?: string;
  renderGuestLogoutWarning?: ReactNode;
  renderSubHeader?: ReactNode;
  logoTitle?: string;
  backTitle?: string;
}

const renderMenuItem = (
  item: HeaderMenuItem,
  closeDropdown: () => void,
): React.ReactElement => {
  const Icon = item.icon;
  const textColor = item.variant === 'accent' ? 'text-ccl-teal' : 'text-ccl-navy';

  return (
    <button
      key={item.key}
      onClick={() => {
        closeDropdown();
        item.onClick();
      }}
      className={`w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left ${textColor} hover:bg-ccl-cream transition-colors`}
    >
      <Icon className="h-5 w-5" {...item.iconProps} />
      <span className="font-semibold">{item.label}</span>
    </button>
  );
};

export const Header: React.FC<HeaderProps> = ({
  logoSrc,
  logoAlt,
  playerName,
  wallet,
  vault,
  isGuest,
  isOffline = false,
  showBackArrow = false,
  onBackClick,
  onStatisticsClick,
  onLogoutClick,
  dropdownSections,
  footerItems = [],
  logoutLabel = 'Logout',
  renderGuestLogoutWarning,
  renderSubHeader,
  logoTitle = 'Open menu',
  backTitle = 'Go back',
}) => {
  const [showDropdown, setShowDropdown] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const logoButtonRef = useRef<HTMLButtonElement>(null);

  const closeDropdown = useCallback(() => setShowDropdown(false), []);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      const target = event.target as Node;
      if (
        dropdownRef.current &&
        !dropdownRef.current.contains(target) &&
        logoButtonRef.current &&
        !logoButtonRef.current.contains(target)
      ) {
        closeDropdown();
      }
    };

    if (showDropdown) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [showDropdown, closeDropdown]);

  return (
    <>
      {renderGuestLogoutWarning}
      <div className="bg-ccl-warm-ivory shadow-tile-sm relative z-50">
        <div className="max-w-6xl mx-auto px-1 py-0 md:px-4 md:py-1.5">
          <div className="flex justify-between items-center">
            {/* Left: Logo + Back Arrow (on certain pages) */}
            <div className="flex items-center gap-0.5 md:gap-3 relative">
              {showBackArrow && (
                <button
                  type="button"
                  onClick={onBackClick}
                  className="cursor-pointer transition-opacity hover:opacity-80"
                  title={backTitle}
                  aria-label={backTitle}
                >
                  <ArrowLeftIcon className="w-7 h-7 md:w-9 md:h-9" aria-hidden="true" />
                </button>
              )}
              <button
                ref={logoButtonRef}
                type="button"
                onClick={() => setShowDropdown((prev) => !prev)}
                className="cursor-pointer transition-opacity hover:opacity-90"
                title={logoTitle}
                aria-label={logoTitle}
              >
                <img src={logoSrc} alt={logoAlt} className="md:h-10 h-8 w-auto" />
              </button>

              {/* Dropdown Menu */}
              {showDropdown && (
                <div
                  ref={dropdownRef}
                  className="absolute top-full left-0 mt-2 w-48 bg-white rounded-tile shadow-tile-lg border-2 border-ccl-navy border-opacity-10 z-[100] slide-up-enter"
                >
                  <div className="py-2">
                    {dropdownSections.map((section, sectionIndex) => (
                      <div key={`section-${sectionIndex}`} className="contents">
                        {section.map((item) => renderMenuItem(item, closeDropdown))}
                        {sectionIndex < dropdownSections.length - 1 && (
                          <div className="border-t border-ccl-navy border-opacity-10 my-2" />
                        )}
                      </div>
                    ))}
                    {footerItems.length > 0 && <div className="border-t border-ccl-navy border-opacity-10 my-2" />}
                    {footerItems.map((item) => renderMenuItem(item, closeDropdown))}
                    <div className="border-t border-ccl-navy border-opacity-10 my-2" />
                    <button
                      onClick={() => {
                        closeDropdown();
                        onLogoutClick();
                      }}
                      className="w-full flex items-center md:gap-3 gap-1 md:px-4 px-2 py-1.5 md:py-3 text-left text-ccl-teal hover:bg-ccl-cream transition-colors"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                      </svg>
                      <span className="font-semibold">{logoutLabel}</span>
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Center: Username (clickable to statistics) */}
            <div className="flex-1 text-center">
              <button
                onClick={onStatisticsClick}
                className="text-md md:text-2xl text-ccl-turquoise font-semibold hover:text-ccl-teal transition-colors"
                title="View your statistics"
              >
                <div className="flex items-center justify-center gap-0.5 md:gap-3">
                  {!isGuest && (
                    <div className="flex items-center" role="status" aria-live="polite">
                      <div className={`w-2 h-2 rounded-full ${!isOffline ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`}>
                        <span className="sr-only">{!isOffline ? 'Online' : 'Offline'}</span>
                      </div>
                    </div>
                  )}
                  <span>{playerName}</span>
                </div>
              </button>
            </div>

            {/* Right: Wallet + Vault + Logout (guest only) */}
            <div className="flex items-center gap-0.5 md:gap-4">
              {/* Wallet Balance */}
              <button
                type="button"
                onClick={onStatisticsClick}
                className="flex items-center gap-0.5 tutorial-balance border border-white/10 rounded-xl px-0.5 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
                title="Wallet balance"
                aria-label="Wallet balance"
              >
                <img src="/wallet.png" alt="Wallet" className="w-5 h-5 md:w-7 md:h-7" />
                <BalanceFlipper
                  value={wallet}
                  className="text-xl md:text-2xl font-display font-bold text-ccl-turquoise"
                />
              </button>
              {/* Vault Balance */}
              <button
                type="button"
                onClick={onStatisticsClick}
                className="flex items-center gap-0.5 border border-white/10 rounded-xl px-0.5 md:px-3 py-1 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ccl-teal"
                title="Vault balance"
                aria-label="Vault balance"
              >
                <img src="/vault.png" alt="Vault" className="w-5 h-5 md:w-7 md:h-7" />
                <BalanceFlipper
                  value={vault}
                  className="text-xl md:text-2xl font-display font-bold text-ccl-turquoise"
                />
              </button>
              {/* Logout Button - Only visible for guests */}
              {isGuest && (
                <button onClick={onLogoutClick} className="text-ccl-teal hover:text-ccl-turquoise" title="Logout">
                  <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 md:h-9 md:w-9" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
                  </svg>
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
      {renderSubHeader}
    </>
  );
};

export default Header;
