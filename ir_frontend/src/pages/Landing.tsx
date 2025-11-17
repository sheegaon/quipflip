import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';

const AUTO_GUEST_LOGIN_KEY = 'ir_auto_guest_login';

type AuthMode = 'welcome' | 'login' | 'register';

const Landing: React.FC = () => {
  const navigate = useNavigate();
  const { isAuthenticated, loginAsGuest, login, register, error, loading } = useIRGame();
  const [mode, setMode] = useState<AuthMode>('welcome');
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [autoLoginTriggered, setAutoLoginTriggered] = useState(false);

  const autoLoginEnabled = useMemo(() => {
    if (typeof window === 'undefined') return true;
    const storedPreference = localStorage.getItem(AUTO_GUEST_LOGIN_KEY);
    return storedPreference === null ? true : storedPreference === 'true';
  }, []);

  useEffect(() => {
    if (isAuthenticated || loading || autoLoginTriggered || !autoLoginEnabled) {
      return;
    }

    setAutoLoginTriggered(true);
    handleGuestLogin(true);
  }, [autoLoginEnabled, autoLoginTriggered, isAuthenticated, loading]);

  const handleGuestLogin = async (isAuto = false) => {
    try {
      await loginAsGuest();
      localStorage.setItem(AUTO_GUEST_LOGIN_KEY, 'true');
      navigate('/dashboard');
    } catch (err) {
      if (isAuto) {
        setAutoLoginTriggered(false);
      }
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
      await register(username, email, password);
      navigate('/dashboard');
    } catch (err) {
      console.error('Registration failed:', err);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-ir-orange to-ir-orange-deep flex items-center justify-center p-4 bg-pattern">
      <div className="max-w-xl w-full tile-card p-8">
        {/* Logo/Title */}
        <div className="text-center mb-6">
          <h1 className="text-4xl font-display font-bold text-ir-navy mb-2">Initial Reaction</h1>
          <p className="text-ir-teal text-lg">Create clever backronyms and win InitCoins!</p>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-4 p-4 bg-red-100 border border-red-400 text-red-700 rounded-tile">
            {error}
          </div>
        )}

        {/* Welcome Mode */}
        {mode === 'welcome' && (
          <div className="space-y-4">
            <button
              onClick={() => handleGuestLogin()}
              disabled={loading}
              className="w-full py-4 px-4 bg-gradient-to-r from-ir-turquoise to-ir-teal text-white font-semibold rounded-tile hover:shadow-tile-sm transition-all disabled:opacity-50 text-lg"
            >
              {loading ? 'Creating Account...' : 'Play as Guest'}
            </button>

            {autoLoginEnabled && !autoLoginTriggered && (
              <p className="text-center text-sm text-ir-teal">
                Auto-login is enabled for guests on this device. We’ll sign you in automatically next time.
              </p>
            )}

            <div className="relative">
              <div className="absolute inset-0 flex items-center">
                <div className="w-full border-t border-ir-navy border-opacity-10"></div>
              </div>
              <div className="relative flex justify-center text-sm">
                <span className="px-2 bg-ir-teal-light text-ir-teal">or</span>
              </div>
            </div>

            <button
              onClick={() => setMode('login')}
              className="w-full py-3 px-4 bg-white border-2 border-ir-navy text-ir-navy font-semibold rounded-tile hover:bg-ir-cream transition-all"
            >
              Login with Email
            </button>

            <button
              onClick={() => setMode('register')}
              className="w-full py-3 px-4 bg-white border-2 border-ir-orange text-ir-orange font-semibold rounded-tile hover:bg-ir-cream transition-all"
            >
              Create Account
            </button>
          </div>
        )}

        {/* Login Mode */}
        {mode === 'login' && (
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-ir-teal mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 border-2 border-ir-navy border-opacity-20 rounded-tile focus:ring-2 focus:ring-ir-turquoise focus:border-transparent"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-ir-teal mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-2 border-2 border-ir-navy border-opacity-20 rounded-tile focus:ring-2 focus:ring-ir-turquoise focus:border-transparent"
                placeholder="••••••••"
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-ir-navy text-white font-semibold rounded-tile hover:bg-ir-teal transition-all shadow-tile-sm disabled:opacity-50"
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
              <label className="block text-sm font-medium text-ir-teal mb-2">Username</label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                className="w-full px-4 py-2 border-2 border-ir-navy border-opacity-20 rounded-tile focus:ring-2 focus:ring-ir-turquoise focus:border-transparent"
                placeholder="choose-a-username"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-ir-teal mb-2">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-4 py-2 border-2 border-ir-navy border-opacity-20 rounded-tile focus:ring-2 focus:ring-ir-turquoise focus:border-transparent"
                placeholder="your@email.com"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-ir-teal mb-2">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="w-full px-4 py-2 border-2 border-ir-navy border-opacity-20 rounded-tile focus:ring-2 focus:ring-ir-turquoise focus:border-transparent"
                placeholder="••••••••"
              />
              <p className="text-xs text-ir-teal mt-1">At least 6 characters</p>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 px-4 bg-ir-orange text-white font-semibold rounded-tile hover:bg-ir-orange-deep transition-all shadow-tile-sm disabled:opacity-50"
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
        <div className="mt-8 text-center text-sm text-ir-teal">
          <p className="font-display font-semibold mb-2 text-ir-navy">How to Play:</p>
          <p className="text-ir-turquoise">1. Submit clever phrases for prompts</p>
          <p className="text-ir-turquoise">2. Copy phrases without seeing the prompt</p>
          <p className="text-ir-turquoise">3. Vote to identify the original phrase</p>
          <p className="text-xs text-ir-teal mt-3">Guest accounts are created automatically so you can start playing right away.</p>
        </div>
      </div>
    </div>
  );
};

export default Landing;
