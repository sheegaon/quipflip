import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '../api/client';

const validatePasswordStrength = (password: string): string | null => {
  if (password.length < 8) {
    return 'Password must be at least 8 characters long.';
  }

  if (!/[A-Z]/.test(password) || !/[a-z]/.test(password)) {
    return 'Password must include both uppercase and lowercase letters.';
  }

  if (!/[0-9]/.test(password)) {
    return 'Password must include at least one number.';
  }

  return null;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const formatDate = (dateString?: string | null) => {
  if (!dateString) {
    return 'Not recorded';
  }

  return new Date(dateString).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

const Settings: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { refreshBalance, logout } = actions;
  const { resetTutorial } = useTutorial();
  const navigate = useNavigate();

  const [resettingTutorial, setResettingTutorial] = useState(false);
  const [tutorialResetSuccess, setTutorialResetSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAdminPasswordPrompt, setShowAdminPasswordPrompt] = useState(false);
  const [adminPassword, setAdminPassword] = useState('');
  const [adminPasswordError, setAdminPasswordError] = useState<string | null>(null);

  const [passwordForm, setPasswordForm] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [passwordSuccess, setPasswordSuccess] = useState<string | null>(null);
  const [passwordLoading, setPasswordLoading] = useState(false);

  const [emailForm, setEmailForm] = useState({
    newEmail: player?.email ?? '',
    password: '',
  });
  const [emailError, setEmailError] = useState<string | null>(null);
  const [emailSuccess, setEmailSuccess] = useState<string | null>(null);
  const [emailLoading, setEmailLoading] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (player?.email) {
      setEmailForm((prev) => ({ ...prev, newEmail: player.email }));
    }
  }, [player?.email]);

  if (!player) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    );
  }

  const handleResetTutorial = async () => {
    try {
      setResettingTutorial(true);
      setError(null);
      setTutorialResetSuccess(false);
      resetTutorial();
      setTutorialResetSuccess(true);
      setTimeout(() => setTutorialResetSuccess(false), 3000);
    } catch (err) {
      setError(extractErrorMessage(err) || 'Failed to reset tutorial');
    } finally {
      setResettingTutorial(false);
    }
  };

  const handleAdminAccess = () => {
    setShowAdminPasswordPrompt(true);
    setAdminPassword('');
    setAdminPasswordError(null);
  };

  const handleAdminPasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setAdminPasswordError(null);

    // Validate the password against the backend secret_key
    try {
      const result = await apiClient.validateAdminPassword(adminPassword);

      if (result.valid) {
        // Password is correct, navigate to admin
        navigate('/admin');
      } else {
        setAdminPasswordError('Incorrect admin password');
      }
    } catch (err) {
      setAdminPasswordError(extractErrorMessage(err) || 'Failed to verify password');
    }
  };

  const handlePasswordSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setPasswordError(null);
    setPasswordSuccess(null);

    if (!passwordForm.currentPassword || !passwordForm.newPassword) {
      setPasswordError('Please provide both your current and new passwords.');
      return;
    }

    if (passwordForm.newPassword !== passwordForm.confirmPassword) {
      setPasswordError('New passwords do not match.');
      return;
    }

    const strengthError = validatePasswordStrength(passwordForm.newPassword);
    if (strengthError) {
      setPasswordError(strengthError);
      return;
    }

    try {
      setPasswordLoading(true);
      const response = await apiClient.changePassword({
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });

      setPasswordSuccess(response.message || 'Password updated successfully.');
      setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (err) {
      setPasswordError(extractErrorMessage(err, 'change-password') || 'Failed to update password');
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setEmailError(null);
    setEmailSuccess(null);

    if (!emailPattern.test(emailForm.newEmail)) {
      setEmailError('Please enter a valid email address.');
      return;
    }

    if (!emailForm.password) {
      setEmailError('Please confirm with your password.');
      return;
    }

    try {
      setEmailLoading(true);
      const response = await apiClient.updateEmail({
        new_email: emailForm.newEmail,
        password: emailForm.password,
      });

      setEmailSuccess(`Email updated to ${response.email}`);
      setEmailForm({ newEmail: response.email, password: '' });
      await refreshBalance();
    } catch (err: any) {
      if (err?.detail === 'email_taken') {
        setEmailError('That email address is already in use.');
      } else if (err?.detail === 'invalid_email') {
        setEmailError('Please enter a valid email address.');
      } else {
        setEmailError(extractErrorMessage(err, 'change-email') || 'Failed to update email');
      }
    } finally {
      setEmailLoading(false);
    }
  };

  const openDeleteModal = () => {
    setDeletePassword('');
    setDeleteConfirmation('');
    setDeleteError(null);
    setShowDeleteModal(true);
  };

  const closeDeleteModal = () => {
    setShowDeleteModal(false);
    setDeletePassword('');
    setDeleteConfirmation('');
    setDeleteError(null);
  };

  const handleDeleteAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    setDeleteError(null);

    if (deleteConfirmation.trim().toUpperCase() !== 'DELETE') {
      setDeleteError('Type DELETE in all caps to confirm.');
      return;
    }

    if (!deletePassword) {
      setDeleteError('Password is required to delete your account.');
      return;
    }

    try {
      setDeleteLoading(true);
      await apiClient.deleteAccount({ password: deletePassword, confirmation: 'DELETE' });
      closeDeleteModal();
      await logout();
      navigate('/', { replace: true });
    } catch (err) {
      setDeleteError(extractErrorMessage(err, 'delete-account') || 'Failed to delete account');
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <h1 className="text-3xl font-display font-bold text-quip-navy">Settings</h1>
          <p className="text-quip-teal mt-1">Manage your account and preferences</p>
        </div>

        {/* Error/Success Messages */}
        {error && (
          <div className="tile-card p-4 mb-6 bg-red-100 border-2 border-red-400">
            <div className="flex justify-between items-start">
              <span className="text-red-700">{error}</span>
              <button
                onClick={() => setError(null)}
                className="ml-2 text-red-900 hover:text-red-700"
                aria-label="Dismiss error"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {tutorialResetSuccess && (
          <div className="tile-card p-4 mb-6 bg-green-100 border-2 border-green-400">
            <div className="flex justify-between items-start">
              <span className="text-green-700">Tutorial reset successfully!</span>
              <button
                onClick={() => setTutorialResetSuccess(false)}
                className="ml-2 text-green-900 hover:text-green-700"
                aria-label="Dismiss"
              >
                ✕
              </button>
            </div>
          </div>
        )}

        {/* Account Information */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Account Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Username</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {player.username}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Email</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {player.email}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Anonymous Pseudonym</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {player.pseudonym}
              </div>
              <p className="text-xs text-quip-teal mt-1">This is how other players see you in results</p>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Account Created</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {formatDate(player.created_at)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Last Login</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {formatDate(player.last_login_date)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Outstanding Prompts</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                {player.outstanding_prompts} / 10
              </div>
              <p className="text-xs text-quip-teal mt-1">Active prompts waiting for copies</p>
            </div>
          </div>
        </div>

        {/* Balance Information */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Balance Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Current Balance</label>
              <div className="bg-white border-2 border-quip-orange border-opacity-30 rounded-tile p-3">
                <div className="flex items-center gap-2">
                  <img src="/flipcoin.png" alt="Flipcoin" className="w-6 h-6" />
                  <span className="text-2xl font-bold text-quip-orange">{player.balance}</span>
                </div>
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-1">Starting Balance</label>
              <div className="bg-white border-2 border-quip-navy border-opacity-20 rounded-tile p-3 text-quip-navy">
                <div className="flex items-center gap-2">
                  <img src="/flipcoin.png" alt="Flipcoin" className="w-6 h-6" />
                  <span className="text-2xl font-bold text-quip-orange">{player.starting_balance}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Change Password */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Change Password</h2>
          <p className="text-quip-teal mb-4">
            Update your password to keep your account secure. Passwords must include upper and lowercase letters and at least one number.
          </p>
          {passwordError && <p className="text-red-600 mb-3">{passwordError}</p>}
          {passwordSuccess && <p className="text-green-600 mb-3">{passwordSuccess}</p>}
          <form onSubmit={handlePasswordSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-quip-teal mb-2">Current Password</label>
              <input
                type="password"
                value={passwordForm.currentPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder="Enter current password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-quip-teal mb-2">New Password</label>
              <input
                type="password"
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder="Enter new password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-quip-teal mb-2">Confirm New Password</label>
              <input
                type="password"
                value={passwordForm.confirmPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder="Re-enter new password"
              />
            </div>
            <div className="md:col-span-3 flex justify-end">
              <button
                type="submit"
                disabled={passwordLoading}
                className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {passwordLoading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>

        {/* Change Email */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Change Email</h2>
          <p className="text-quip-teal mb-4">Enter a new email address and confirm with your current password.</p>
          {emailError && <p className="text-red-600 mb-3">{emailError}</p>}
          {emailSuccess && <p className="text-green-600 mb-3">{emailSuccess}</p>}
          <form onSubmit={handleEmailSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-quip-teal mb-2">New Email</label>
              <input
                type="email"
                value={emailForm.newEmail}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, newEmail: e.target.value }))}
                className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder="you@example.com"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-quip-teal mb-2">Password</label>
              <input
                type="password"
                value={emailForm.password}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, password: e.target.value }))}
                className="border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder="Enter password"
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={emailLoading}
                className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {emailLoading ? 'Updating...' : 'Update Email'}
              </button>
            </div>
          </form>
        </div>

        {/* Tutorial Management */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Tutorial</h2>
          <p className="text-quip-teal mb-4">Reset the tutorial to see the introduction and walkthrough again.</p>
          <button
            onClick={handleResetTutorial}
            disabled={resettingTutorial}
            className="bg-quip-turquoise hover:bg-quip-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
          >
            {resettingTutorial ? 'Resetting...' : 'Reset Tutorial'}
          </button>
        </div>

        {/* Admin Access */}
        <div className="tile-card p-6 mb-6 border-2 border-quip-orange border-opacity-30">
          <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Admin Access</h2>
          <p className="text-quip-teal mb-4">
            Access administrative settings and configuration. Requires the application admin password (secret key).
          </p>

          {!showAdminPasswordPrompt ? (
            <button
              onClick={handleAdminAccess}
              className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Access Admin Panel
            </button>
          ) : (
            <form onSubmit={handleAdminPasswordSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-2">Enter admin password (secret key)</label>
                <input
                  type="password"
                  value={adminPassword}
                  onChange={(e) => setAdminPassword(e.target.value)}
                  className="w-full md:w-96 border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                  placeholder="Admin password"
                  autoFocus
                />
                {adminPasswordError && <p className="text-red-600 text-sm mt-1">{adminPasswordError}</p>}
              </div>
              <div className="flex gap-3">
                <button
                  type="submit"
                  className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  Continue
                </button>
                <button
                  type="button"
                  onClick={() => {
                    setShowAdminPasswordPrompt(false);
                    setAdminPassword('');
                    setAdminPasswordError(null);
                  }}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-700 font-bold py-3 px-6 rounded-tile transition-all"
                >
                  Cancel
                </button>
              </div>
            </form>
          )}
        </div>

        {/* Delete Account */}
        <div className="tile-card p-6 mb-6 bg-red-50 border-2 border-red-300">
          <h2 className="text-2xl font-display font-bold text-red-700 mb-4">Delete Account</h2>
          <p className="text-red-700 mb-4">
            Permanently delete your account and all associated data. This action cannot be undone.
          </p>
          <button
            onClick={openDeleteModal}
            className="bg-red-600 hover:bg-red-700 text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
          >
            Delete My Account
          </button>
        </div>

        {/* Future Features (Placeholder) */}
        <div className="tile-card p-6 mb-6 bg-gray-50 border-2 border-gray-300 opacity-60">
          <h2 className="text-2xl font-display font-bold text-gray-600 mb-4">Coming Soon</h2>
          <ul className="space-y-2 text-gray-600">
            <li className="flex items-center gap-2">
              <span className="text-gray-400">📊</span>
              Export Account Data
            </li>
            <li className="flex items-center gap-2">
              <span className="text-gray-400">🔔</span>
              Notification Preferences
            </li>
          </ul>
        </div>
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 px-4">
          <div className="tile-card max-w-lg w-full p-6">
            <h3 className="text-2xl font-display font-bold text-red-700 mb-4">Confirm Account Deletion</h3>
            <p className="text-quip-teal mb-4">
              This will permanently delete your account, balances, quests, and all associated gameplay history. This action cannot be undone.
            </p>
            {deleteError && <p className="text-red-600 mb-3">{deleteError}</p>}
            <form onSubmit={handleDeleteAccount} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-2">Password</label>
                <input
                  type="password"
                  value={deletePassword}
                  onChange={(e) => setDeletePassword(e.target.value)}
                  className="w-full border-2 border-red-300 rounded-tile p-3 focus:outline-none focus:border-red-500"
                  placeholder="Enter your password"
                  autoFocus
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-quip-teal mb-2">Type DELETE to confirm</label>
                <input
                  type="text"
                  value={deleteConfirmation}
                  onChange={(e) => setDeleteConfirmation(e.target.value)}
                  className="w-full border-2 border-red-300 rounded-tile p-3 focus:outline-none focus:border-red-500"
                  placeholder="DELETE"
                />
              </div>
              <div className="flex justify-end gap-3">
                <button
                  type="button"
                  onClick={closeDeleteModal}
                  className="bg-gray-300 hover:bg-gray-400 text-gray-700 font-bold py-3 px-6 rounded-tile transition-all"
                  disabled={deleteLoading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={deleteLoading}
                  className="bg-red-600 hover:bg-red-700 disabled:bg-red-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  {deleteLoading ? 'Deleting...' : 'Confirm Delete'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default Settings;
