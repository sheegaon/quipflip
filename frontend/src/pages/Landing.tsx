import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';
import { landingLogger } from '../utils/logger';

export const Landing: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');
  const [guestCredentials, setGuestCredentials] = useState<{ email: string; password: string } | null>(null);

  const { actions } = useGame();
  const { startSession } = actions;
  const navigate = useNavigate();

  useEffect(() => {
    landingLogger.debug('Landing page rendered');
  }, []);

  const handleCreatePlayer = async (e: React.FormEvent) => {
    e.preventDefault();

    // Frontend validation
    if (!registerEmail.trim()) {
      setError('Please provide an email address.');
      landingLogger.warn('Registration attempted without email');
      return;
    }
    // Basic email validation
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRegex.test(registerEmail.trim())) {
      setError('Please provide a valid email address.');
      landingLogger.warn('Registration attempted with invalid email format', { registerEmail });
      return;
    }

    if (!registerPassword) {
      setError('Please provide a password.');
      landingLogger.warn('Registration attempted without password');
      return;
    }
    if (registerPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      landingLogger.warn('Registration attempted with short password');
      return;
    }
    if (registerPassword.length > 128) {
      setError('Password must be 128 characters or less.');
      landingLogger.warn('Registration attempted with overly long password');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      landingLogger.info('Creating player account');

      // Backend auto-generates the username/pseudonym, so send only credentials
      const response = await apiClient.createPlayer({
        email: registerEmail.trim(),
        password: registerPassword,
      });

      landingLogger.info('Player created successfully, starting session', { username: response.username });
      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to create your account. Please try again or contact support if the problem persists.';
      landingLogger.error('Failed to create player account', err);
      setError(message);
    } finally {
      setIsLoading(false);
      landingLogger.debug('Create player flow completed');
    }
  };

  const handleExistingPlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword.trim()) {
      setError('Please enter your email and password.');
      landingLogger.warn('Login attempted with missing credentials');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      landingLogger.info('Attempting login for existing player', { loginEmail });

      // Send email and password to backend (now with correct field names)
      const response = await apiClient.login({
        email: loginEmail.trim(),
        password: loginPassword,
      });

      landingLogger.info('Login successful, starting session', { username: response.username });
      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Login failed. Please check your email and password, or create a new account.';
      landingLogger.error('Login failed', err);
      setError(message);
    } finally {
      setIsLoading(false);
      landingLogger.debug('Existing player login flow completed');
    }
  };

  const handlePlayAsGuest = async () => {
    try {
      setIsLoading(true);
      setError(null);
      landingLogger.info('Creating guest account');

      const response = await apiClient.createGuest();

      landingLogger.info('Guest created successfully, starting session', { username: response.username });

      // Show guest credentials to user
      setGuestCredentials({ email: response.email, password: response.password });

      // Store guest credentials temporarily for tutorial display
      localStorage.setItem('quipflip_guest_credentials', JSON.stringify({
        email: response.email,
        password: response.password,
        timestamp: Date.now()
      }));

      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Unable to create guest account. Please try again.';
      landingLogger.error('Failed to create guest account', err);
      setError(message);
    } finally {
      setIsLoading(false);
      landingLogger.debug('Guest account creation completed');
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-quip-orange to-quip-turquoise flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-md w-full tile-card p-8 animate-slide-up">
        {/* Logo */}
        <div className="flex justify-center mb-4">
          <img
            src="/quipflip_logo.png"
            alt="Quipflip"
            className="h-auto w-auto"
          />
        </div>

        {error && (
          <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
            {error}
          </div>
        )}

        {guestCredentials && (
          <div className="mb-6 p-4 bg-blue-100 border border-blue-400 text-blue-900 rounded">
            <p className="font-semibold mb-2">Guest Account Created!</p>
            <p className="text-sm mb-1">Email: {guestCredentials.email}</p>
            <p className="text-sm">Password: {guestCredentials.password}</p>
            <p className="text-xs mt-2 text-blue-700">Save these credentials to log in later, or upgrade your account in Settings.</p>
          </div>
        )}

        {/* Play Instantly Button */}
        <div className="mb-6">
          <button
            onClick={handlePlayAsGuest}
            disabled={isLoading}
            className="w-full bg-gradient-to-r from-quip-orange to-quip-turquoise hover:from-quip-orange-deep hover:to-quip-teal disabled:bg-gray-400 text-white font-bold py-4 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5 text-lg"
          >
            {isLoading ? 'Creating Guest Account...' : 'Play Instantly'}
          </button>
        </div>

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
          <div className="border-b border-quip-teal pb-6">
            <h2 className="text-xl font-semibold mb-4 text-quip-navy">Create an Account</h2>
            <form onSubmit={handleCreatePlayer} className="space-y-3">
              <input
                type="email"
                value={registerEmail}
                onChange={(e) => setRegisterEmail(e.target.value)}
                placeholder="Your email"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
                disabled={isLoading}
                autoComplete="email"
              />
              <input
                type="password"
                value={registerPassword}
                onChange={(e) => setRegisterPassword(e.target.value)}
                placeholder="Create a password (min 8 characters)"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
                disabled={isLoading}
                autoComplete="new-password"
                minLength={8}
                maxLength={128}
              />
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5"
              >
                {isLoading ? 'Creating Account...' : 'Create New Account'}
              </button>
            </form>
          </div>

          {/* Returning Player */}
          <div>
            <h2 className="text-xl font-semibold mb-4 text-quip-navy">Returning Player</h2>
            <form onSubmit={handleExistingPlayer} className="space-y-3">
              <input
                type="email"
                value={loginEmail}
                onChange={(e) => setLoginEmail(e.target.value)}
                placeholder="Your email"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
                disabled={isLoading}
                autoComplete="email"
              />
              <input
                type="password"
                value={loginPassword}
                onChange={(e) => setLoginPassword(e.target.value)}
                placeholder="Password"
                className="w-full px-4 py-2 border border-gray-300 rounded-tile focus:outline-none focus:ring-2 focus:ring-quip-turquoise"
                disabled={isLoading}
                autoComplete="current-password"
              />
              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-quip-orange hover:bg-quip-orange-deep disabled:bg-gray-400 text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm transform hover:-translate-y-0.5"
              >
                {isLoading ? 'Logging in...' : 'Login'}
              </button>
            </form>
            <p className="text-sm text-gray-600 mt-2">
              Forgot your password? Email support@quipflip.xyz for assistance.
            </p>
          </div>
        </div>

        <div className="mt-8 text-center text-sm text-quip-navy">
          <p className="font-display font-semibold mb-2">How to Play:</p>
          <p className="text-quip-teal">1. Submit clever phrases for prompts</p>
          <p className="text-quip-teal">2. Copy phrases without seeing the prompt</p>
          <p className="text-quip-teal">3. Vote to identify the original phrase</p>
        </div>
      </div>
    </div>
  );
};

export default Landing;
