import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';

export const Landing: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [loginIdentifier, setLoginIdentifier] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  const { loginAsGuest, login, register } = useIRGame();
  const navigate = useNavigate();
  const isMountedRef = useRef(true);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const handleCreatePlayer = async (e: React.FormEvent) => {
    e.preventDefault();

    // Frontend validation
    if (!registerEmail.trim()) {
      setError('Please provide an email address.');
      return;
    }
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(registerEmail.trim())) {
      setError('Please provide a valid email address.');
      return;
    }

    if (!registerPassword) {
      setError('Please provide a password.');
      return;
    }
    if (registerPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }
    if (registerPassword.length > 128) {
      setError('Password must be 128 characters or less.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Backend requires username, use email prefix as placeholder
      await register(registerEmail.split('@')[0], registerEmail.trim(), registerPassword);

      if (isMountedRef.current) {
        navigate('/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create your account. Please try again.';
      if (isMountedRef.current) {
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  };

  const handleExistingPlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    const identifier = loginIdentifier.trim();
    if (!identifier || !loginPassword.trim()) {
      setError('Please enter your email and password.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);

      // Use email login endpoint
      await login(identifier, loginPassword);

      if (isMountedRef.current) {
        navigate('/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Login failed. Please check your email and password.';
      if (isMountedRef.current) {
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  };

  const handlePlayAsGuest = async () => {
    try {
      setIsLoading(true);
      setError(null);

      await loginAsGuest();

      if (isMountedRef.current) {
        navigate('/dashboard');
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unable to create guest account. Please try again.';
      if (isMountedRef.current) {
        setError(message);
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false);
      }
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-ir-orange to-ir-orange-deep flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-md w-full tile-card p-8 animate-slide-up">
        {/* Logo */}
        <div className="flex justify-center mb-4">
          <img
            src="/initial_reaction_logo.png"
            alt="Initial Reaction"
            className="h-auto w-auto"
          />
        </div>

        <p className="text-center text-ir-navy text-lg font-medium mb-4">
          Create clever backronyms and win InitCoins!
        </p>

        <div className="mb-6 border-t border-gray-200" aria-hidden="true"></div>

        {/* Play Now Button */}
        <div className="mb-6">
          <button
            onClick={handlePlayAsGuest}
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-ir-orange to-ir-turquoise hover:from-ir-orange-deep hover:to-ir-teal disabled:bg-gray-400 text-white font-bold py-4 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5 text-lg"
          >
            {isLoading ? 'Creating Guest Account...' : 'Play Now'}
          </button>
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        <div className="relative mb-6">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-gray-300"></div>
          </div>
          <div className="relative flex justify-center text-sm">
            <span className="px-2 bg-white text-gray-500">or</span>
          </div>
        </div>

        <div className="space-y-6">
          {/* New Player */}
          <div className="border-b border-ir-teal pb-6">
            <h2 className="text-xl font-semibold mb-4 text-ir-navy">Create an Account</h2>
            <form onSubmit={handleCreatePlayer} className="space-y-3">
              <input
                type="email"
                value={registerEmail}
                onChange={(e) => setRegisterEmail(e.target.value)}
                placeholder="Your email (no validation required)"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-ir-turquoise"
                disabled={isLoading}
                autoComplete="email"
              />
              <input
                type="password"
                value={registerPassword}
                onChange={(e) => setRegisterPassword(e.target.value)}
                placeholder="Password (min 8 characters)"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-ir-turquoise"
                disabled={isLoading}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-ir-turquoise hover:bg-ir-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5"
              >
                {isLoading ? 'Creating Account...' : 'Create New Account'}
              </button>
            </form>
          </div>

          {/* Returning Player */}
          <div>
            <h2 className="text-xl font-semibold mb-4 text-ir-navy">Returning Player</h2>
            <form onSubmit={handleExistingPlayer} className="space-y-3">
              <input
                type="text"
                value={loginIdentifier}
                onChange={(e) => setLoginIdentifier(e.target.value)}
                placeholder="Email"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-ir-turquoise"
                disabled={isLoading}
                autoComplete="username"
              />
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Password"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-ir-turquoise"
                disabled={isLoading}
                autoComplete="current-password"
              />
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-ir-orange hover:bg-ir-orange-deep disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5"
              >
                {isLoading ? 'Logging in...' : 'Login'}
              </button>
            </form>
            <p className="text-sm text-gray-600 mt-2">
              Forgot your password? Email support@initialreaction.xyz for assistance.
            </p>
          </div>
        </div>

        <div className="mt-8 text-center text-sm text-ir-navy">
          <p className="font-display font-semibold mb-2">How to Play:</p>
          <p className="text-ir-teal">1. Submit clever backronyms for prompts</p>
          <p className="text-ir-teal">2. Vote to identify the most popular entry</p>
          <p className="text-ir-teal">3. Win InitCoins and climb the leaderboard!</p>
        </div>
      </div>
    </div>
  );
};

export default Landing;
