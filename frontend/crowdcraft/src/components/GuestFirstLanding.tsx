import React from 'react';
import { Link } from 'react-router-dom';

interface GuestFirstLandingProps {
  logoSrc: string;
  logoAlt: string;
  title: string;
  subtitle: string;
  signInPath: string;
  signInLabel?: string;
  primaryActionLabel?: string;
  primaryActionLoadingLabel?: string;
  onPrimaryAction?: () => void | Promise<void>;
  primaryActionDisabled?: boolean;
  className?: string;
  cardClassName?: string;
  buttonClassName?: string;
  signInHint?: string;
}

const GuestFirstLanding: React.FC<GuestFirstLandingProps> = ({
  logoSrc,
  logoAlt,
  title,
  subtitle,
  signInPath,
  signInLabel = 'Played before? Sign in',
  primaryActionLabel,
  primaryActionLoadingLabel = 'Continuing...',
  onPrimaryAction,
  primaryActionDisabled = false,
  className = '',
  cardClassName = '',
  buttonClassName = '',
  signInHint = 'New visitors are created as guests automatically. Returning players can restore their account with email.',
}) => {
  return (
    <div className={`min-h-screen flex items-center justify-center p-4 bg-pattern ${className}`}>
      <div className={`max-w-md w-full tile-card p-8 animate-slide-up ${cardClassName}`}>
        <div className="flex justify-center mb-4">
          <img src={logoSrc} alt={logoAlt} className="h-auto w-auto" />
        </div>

        <p className="text-center text-slate-800 text-lg font-medium mb-4">
          {title}
        </p>

        <p className="text-center text-slate-600 mb-6">
          {subtitle}
        </p>

        <div className="rounded-tile border border-slate-200 bg-white p-4 mb-4">
          <p className="text-sm text-slate-700">{signInHint}</p>
        </div>

        <div className="space-y-3">
          {onPrimaryAction && primaryActionLabel ? (
            <button
              type="button"
              onClick={() => void onPrimaryAction()}
              disabled={primaryActionDisabled}
              className="block w-full rounded-tile bg-ccl-orange px-4 py-3 text-center font-semibold text-white transition hover:bg-ccl-orange-deep disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {primaryActionDisabled ? primaryActionLoadingLabel : primaryActionLabel}
            </button>
          ) : null}

          <Link
            to={signInPath}
            className={`block w-full rounded-tile px-4 py-3 text-center font-semibold transition ${onPrimaryAction
              ? 'border-2 border-slate-300 bg-white text-slate-900 hover:border-slate-500 hover:bg-slate-50'
              : 'bg-slate-900 text-white hover:bg-slate-700'} ${buttonClassName}`}
          >
            {signInLabel}
          </Link>
        </div>
      </div>
    </div>
  );
};

export default GuestFirstLanding;
