import React from 'react';
import { Link } from 'react-router-dom';

interface GuestFirstLandingProps {
  logoSrc: string;
  logoAlt: string;
  title: string;
  subtitle: string;
  signInPath: string;
  signInLabel?: string;
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

        <Link
          to={signInPath}
          className={`block w-full rounded-tile bg-slate-900 px-4 py-3 text-center font-semibold text-white transition hover:bg-slate-700 ${buttonClassName}`}
        >
          {signInLabel}
        </Link>
      </div>
    </div>
  );
};

export default GuestFirstLanding;
