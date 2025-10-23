import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGameStructured } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';

export const Landing: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  const { actions } = useGameStructured();
  const { startSession } = actions;
  const navigate = useNavigate();

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
      const response = await apiClient.createPlayer({
        email: registerEmail.trim(),
        password: registerPassword,
      });
      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Unable to create your account. Please try again or contact support if the problem persists.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleExistingPlayer = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!loginEmail.trim() || !loginPassword.trim()) {
      setError('Please enter your email and password.');
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      const response = await apiClient.login({
        email: loginEmail.trim(),
        password: loginPassword,
      });
      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      setError(extractErrorMessage(err) || 'Login failed. Please check your email and password, or create a new account.');
    } finally {
      setIsLoading(false);
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
                  placeholder="Email address"
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
                Forgot your password? Email support@quipflip.gg for assistance.
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
