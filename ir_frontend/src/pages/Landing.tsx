import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';

type AuthMode = 'welcome' | 'login' | 'register';

const Landing: React.FC = () => {
  const navigate = useNavigate();
  const { loginAsGuest, login, register, error, loading } = useIRGame();
  const [mode, setMode] = useState<AuthMode>('welcome');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const handleGuestLogin = async () => {
    try {
      await loginAsGuest();
      navigate('/dashboard');
    } catch (err) {
      console.error('Guest login failed:', err);
    }
  };

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login(email, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('Login failed:', err);
    }
  };

  const handleRegister = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await register(email, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('Registration failed:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-purple-600 via-indigo-600 to-blue-600 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-2xl p-8">
        {/* Logo/Title */}
        <div className="text-center mb-8">
          <h1 className="text-4xl font-bold text-indigo-600 mb-2">Initial Reaction</h1>
          <p className="text-gray-600">Create clever backronyms and win InitCoins!</p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-lg">
            {error}
          </div>
        )}

        {/* Welcome Mode */}
        {mode === 'welcome' && (
          <div className="space-y-4">
            <button
              onClick={handleGuestLogin}
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-purple-500 to-indigo-500 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-indigo-600 transition-all shadow-lg disabled:opacity-50"
            >
              {loading ? 'Creating Account...' : 'Play as Guest'}
            </button>

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-gray-300"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-white text-gray-500">or</span>
              </div>
            </div>

            <button
              onClick={() => setMode('login')}
              className="w-full py-3 px-4 bg-white border-2 border-indigo-500 text-indigo-600 font-semibold rounded-lg hover:bg-indigo-50 transition-all"
            >
              Login with Email
            </button>

            <button
              onClick={() => setMode('register')}
              className="w-full py-3 px-4 bg-white border-2 border-purple-500 text-purple-600 font-semibold rounded-lg hover:bg-purple-50 transition-all"
            >
              Create Account
            </button>
          </div>
        )}

        {/* Login Mode */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-indigo-500 to-blue-500 text-white font-semibold rounded-lg hover:from-indigo-600 hover:to-blue-600 transition-all shadow-lg disabled:opacity-50"
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>

            <button
              type="button"
              onClick={() => setMode('welcome')}
              className="w-full py-2 text-gray-600 hover:text-gray-800"
            >
              Back
            </button>
          </form>
        )}

        {/* Register Mode */}
        {mode === 'register' && (
          <form onSubmit={handleRegister} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                placeholder="••••••••"
              />
              <p className="text-xs text-gray-500 mt-1">At least 6 characters</p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-gradient-to-r from-purple-500 to-pink-500 text-white font-semibold rounded-lg hover:from-purple-600 hover:to-pink-600 transition-all shadow-lg disabled:opacity-50"
            >
              {loading ? 'Creating Account...' : 'Create Account'}
            </button>

            <button
              type="button"
              onClick={() => setMode('welcome')}
              className="w-full py-2 text-gray-600 hover:text-gray-800"
            >
              Back
            </button>
          </form>
        )}

        {/* Game Info */}
        <div className="mt-8 text-center text-sm text-gray-600">
          <p>💡 Create backronyms for random words</p>
          <p>🗳️ Vote for the best submissions</p>
          <p>💰 Win InitCoins and climb the leaderboard!</p>
        </div>
      </div>
    </div>
  );
};

export default Landing;
