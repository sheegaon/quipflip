import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import apiClient, { extractErrorMessage } from '../api/client';

export const Landing: React.FC = () => {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [registerEmail, setRegisterEmail] = useState('');
  const [registerUsername, setRegisterUsername] = useState('');
  const [registerPassword, setRegisterPassword] = useState('');
  const [loginUsername, setLoginUsername] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  const { actions } = useGame();
  const { startSession } = actions;
  const navigate = useNavigate();

  const handleCreatePlayer = async (e: React.FormEvent) => {
    e.preventDefault();

    // Frontend validation
    if (!registerEmail.trim()) {
      setError('Please provide an email address.');
      return;
    }
    if (!registerUsername.trim()) {
      setError('Please provide a username.');
      return;
    }
    // Basic email validation
    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailPattern.test(registerEmail)) {
      setError('Please enter a valid email address.');
      return;
    }
    if (registerPassword.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.createPlayer({
        username: registerUsername,
        email: registerEmail,
        password: registerPassword,
      });

      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to create account. Please try again.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!loginUsername.trim()) {
      setError('Please provide a username.');
      return;
    }
    if (!loginPassword.trim()) {
      setError('Please provide a password.');
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.login({
        username: loginUsername,
        password: loginPassword,
      });

      startSession(response.username, response);
      navigate('/dashboard');
    } catch (err) {
      const message = extractErrorMessage(err) || 'Login failed. Please check your credentials and try again.';
      setError(message);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSuggestUsername = async () => {
    try {
      const response = await apiClient.suggestUsername();
      setRegisterUsername(response.suggested_username);
    } catch (err) {
      // Silent fail - username suggestion is optional
      console.warn('Failed to suggest username:', err);
    }
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern flex items-center justify-center p-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-display font-bold text-quip-navy mb-2">
            Welcome to Quipflip
          </h1>
          <p className="text-quip-teal">The word game where creativity meets competition</p>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
            {error}
          </div>
        )}

        <div className="bg-white rounded-lg shadow-lg p-6 space-y-6">
          {/* Registration Form */}
          <form onSubmit={handleCreatePlayer} className="space-y-4">
            <h2 className="text-xl font-semibold text-gray-900">Create Account</h2>
            
            <div>
              <label htmlFor="register-email" className="block text-sm font-medium text-gray-700">
                Email
              </label>
              <input
                id="register-email"
                type="email"
                value={registerEmail}
                onChange={(e) => setRegisterEmail(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-quip-teal focus:border-quip-teal"
                required
              />
            </div>

            <div>
              <label htmlFor="register-username" className="block text-sm font-medium text-gray-700">
                Username
              </label>
              <div className="mt-1 flex rounded-md shadow-sm">
                <input
                  id="register-username"
                  type="text"
                  value={registerUsername}
                  onChange={(e) => setRegisterUsername(e.target.value)}
                  className="flex-1 block w-full px-3 py-2 border border-gray-300 rounded-l-md focus:outline-none focus:ring-quip-teal focus:border-quip-teal"
                  required
                />
                <button
                  type="button"
                  onClick={handleSuggestUsername}
                  className="inline-flex items-center px-3 py-2 border border-l-0 border-gray-300 rounded-r-md bg-gray-50 text-gray-500 text-sm hover:bg-gray-100"
                >
                  Suggest
                </button>
              </div>
            </div>

            <div>
              <label htmlFor="register-password" className="block text-sm font-medium text-gray-700">
                Password
              </label>
              <input
                id="register-password"
                type="password"
                value={registerPassword}
                onChange={(e) => setRegisterPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-quip-teal focus:border-quip-teal"
                required
                minLength={8}
              />
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-quip-navy hover:bg-quip-teal disabled:bg-gray-300 text-white font-bold py-2 px-4 rounded-lg transition-colors"
            >
              {isLoading ? 'Creating Account...' : 'Create Account'}
            </button>
          </form>

          <div className="border-t border-gray-200 pt-6">
            {/* Login Form */}
            <form onSubmit={handleLogin} className="space-y-4">
              <h2 className="text-xl font-semibold text-gray-900">Login</h2>
              
              <div>
                <label htmlFor="login-username" className="block text-sm font-medium text-gray-700">
                  Username
                </label>
                <input
                  id="login-username"
                  type="text"
                  value={loginUsername}
                  onChange={(e) => setLoginUsername(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-quip-teal focus:border-quip-teal"
                  required
                />
              </div>

              <div>
                <label htmlFor="login-password" className="block text-sm font-medium text-gray-700">
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  value={loginPassword}
                  onChange={(e) => setLoginPassword(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-quip-teal focus:border-quip-teal"
                  required
                />
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="w-full bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 text-white font-bold py-2 px-4 rounded-lg transition-colors"
              >
                {isLoading ? 'Logging In...' : 'Login'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
};
