import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { useTutorial } from '../contexts/TutorialContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '@crowdcraft/api/client.ts';
import { settingsLogger } from '@crowdcraft/utils/logger.ts';
import { formatDateInUserZone, formatDateTimeInUserZone } from '@crowdcraft/utils/datetime.ts';

const getErrorDetail = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  return (error as { detail?: string }).detail;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const formatDate = (dateString?: string | null) =>
  formatDateInUserZone(dateString, { fallback: 'Not recorded' });

const formatDateTime = (dateString?: string | null) =>
  formatDateTimeInUserZone(dateString, { fallback: 'Not recorded' });

const Settings: React.FC = () => {
  const { state, actions } = useGame();
  const { player } = state;
  const { refreshBalance, logout } = actions;
  const {
    actions: { resetTutorial },
  } = useTutorial();
  const navigate = useNavigate();

  const [resettingTutorial, setResettingTutorial] = useState(false);
  const [tutorialResetSuccess, setTutorialResetSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const [usernameForm, setUsernameForm] = useState({
    newUsername: player?.username ?? '',
    password: '',
  });
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [usernameSuccess, setUsernameSuccess] = useState<string | null>(null);
  const [usernameLoading, setUsernameLoading] = useState(false);

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

  useEffect(() => {
    if (player?.username) {
      setUsernameForm((prev) => ({ ...prev, newUsername: player.username }));
    }
  }, [player?.username]);


  if (!player) {
    return (
      <div className="min-h-screen bg-ccl-cream bg-pattern">
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
      settingsLogger.debug('Resetting tutorial progress');
      await resetTutorial();
      setTutorialResetSuccess(true);
      settingsLogger.info('Tutorial progress reset');
      setTimeout(() => setTutorialResetSuccess(false), 3000);
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to reset tutorial';
      settingsLogger.error('Failed to reset tutorial', err);
      setError(message);
    } finally {
      setResettingTutorial(false);
      settingsLogger.debug('Reset tutorial flow completed');
    }
  };

  const handleAdminAccess = () => {
    // Simply navigate to admin - the backend will check if the user has admin email
    settingsLogger.debug('Navigating to admin panel');
    navigate('/admin');
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
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'email_taken') {
        setEmailError('That email address is already in use.');
      } else if (getErrorDetail(err) === 'invalid_email') {
        setEmailError('Please enter a valid email address.');
      } else {
        setEmailError(extractErrorMessage(err, 'change-email') || 'Failed to update email');
      }
    } finally {
      setEmailLoading(false);
    }
  };

  const handleUsernameSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUsernameError(null);
    setUsernameSuccess(null);

    if (!usernameForm.newUsername || usernameForm.newUsername.trim().length < 3) {
      setUsernameError('Username must be at least 3 characters long.');
      return;
    }

    // Validate that username only contains alphanumeric characters and spaces
    const usernamePattern = /^[a-zA-Z0-9\s]+$/;
    if (!usernamePattern.test(usernameForm.newUsername.trim())) {
      setUsernameError('Username can only contain letters, numbers, and spaces.');
      return;
    }

    if (!usernameForm.password) {
      setUsernameError('Please confirm with your password.');
      return;
    }

    try {
      setUsernameLoading(true);
      const response = await apiClient.changeUsername({
        new_username: usernameForm.newUsername,
        password: usernameForm.password,
      });

      setUsernameSuccess(response.message);
      setUsernameForm({ newUsername: response.username, password: '' });
      await refreshBalance();
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'username_taken') {
        setUsernameError('That username is already in use.');
      } else if (getErrorDetail(err) === 'invalid_username') {
        setUsernameError('Please enter a valid username (only letters, numbers, and spaces).');
      } else {
        setUsernameError(extractErrorMessage(err, 'change-username') || 'Failed to update username');
      }
    } finally {
      setUsernameLoading(false);
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
    <div className="min-h-screen bg-ccl-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <h1 className="text-3xl font-display font-bold text-ccl-navy">Settings</h1>
          <p className="text-ccl-teal mt-1">Manage your account and preferences</p>
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
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Account Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-ccl-teal mb-1">Username</label>
              <div className="bg-white border-2 border-ccl-navy border-opacity-20 rounded-tile p-3 text-ccl-navy">
                {player.username}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ccl-teal mb-1">Email</label>
              <div className="bg-white border-2 border-ccl-navy border-opacity-20 rounded-tile p-3 text-ccl-navy">
                {player.email || 'Not available'}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ccl-teal mb-1">Account Created</label>
              <div className="bg-white border-2 border-ccl-navy border-opacity-20 rounded-tile p-3 text-ccl-navy">
                {formatDate(player.created_at)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ccl-teal mb-1">Last Login</label>
              <div className="bg-white border-2 border-ccl-navy border-opacity-20 rounded-tile p-3 text-ccl-navy">
                {formatDateTime(player.last_login_date)}
              </div>
            </div>
          </div>
        </div>

        {/* Change Password */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Change Password</h2>
          <p className="text-ccl-teal mb-4">
            Update your password to keep your account secure.
          </p>
          {passwordError && <p className="text-red-600 mb-3">{passwordError}</p>}
          {passwordSuccess && <p className="text-green-600 mb-3">{passwordSuccess}</p>}
          <form onSubmit={handlePasswordSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">Current Password</label>
              <input
                type="password"
                value={passwordForm.currentPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Enter current password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">New Password</label>
              <input
                type="password"
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Enter new password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">Confirm New Password</label>
              <input
                type="password"
                value={passwordForm.confirmPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Re-enter new password"
              />
            </div>
            <div className="md:col-span-3 flex justify-end">
              <button
                type="submit"
                disabled={passwordLoading}
                className="bg-ccl-turquoise hover:bg-ccl-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {passwordLoading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>

        {/* Change Email */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Change Email</h2>
          <p className="text-ccl-teal mb-4">Enter a new email address and confirm with your current password.</p>
          {emailError && <p className="text-red-600 mb-3">{emailError}</p>}
          {emailSuccess && <p className="text-green-600 mb-3">{emailSuccess}</p>}
          <form onSubmit={handleEmailSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">New Email</label>
              <input
                type="email"
                value={emailForm.newEmail}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, newEmail: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="you@example.com"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">Password</label>
              <input
                type="password"
                value={emailForm.password}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, password: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Enter password"
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={emailLoading}
                className="bg-ccl-turquoise hover:bg-ccl-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {emailLoading ? 'Updating...' : 'Update Email'}
              </button>
            </div>
          </form>
        </div>

        {/* Change Username */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Change Username</h2>
          <p className="text-ccl-teal mb-4">Update your display name and confirm with your current password.</p>
          {usernameError && <p className="text-red-600 mb-3">{usernameError}</p>}
          {usernameSuccess && <p className="text-green-600 mb-3">{usernameSuccess}</p>}
          <form onSubmit={handleUsernameSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">New Username</label>
              <input
                type="text"
                value={usernameForm.newUsername}
                onChange={(e) => setUsernameForm((prev) => ({ ...prev, newUsername: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Enter new username"
                minLength={3}
                maxLength={80}
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ccl-teal mb-2">Password</label>
              <input
                type="password"
                value={usernameForm.password}
                onChange={(e) => setUsernameForm((prev) => ({ ...prev, password: e.target.value }))}
                className="border-2 border-ccl-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ccl-orange"
                placeholder="Enter password"
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={usernameLoading}
                className="bg-ccl-turquoise hover:bg-ccl-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {usernameLoading ? 'Updating...' : 'Update Username'}
              </button>
            </div>
          </form>
        </div>

        {/* Tutorial Management */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Tutorial</h2>
          <p className="text-ccl-teal mb-4">Reset the tutorial to see the introduction and walkthrough again.</p>
          <button
            onClick={handleResetTutorial}
            disabled={resettingTutorial}
            className="bg-ccl-turquoise hover:bg-ccl-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
          >
            {resettingTutorial ? 'Resetting...' : 'Reset Tutorial'}
          </button>
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

        {/* Admin Access */}
        {player.is_admin && (
          <div className="tile-card p-6 mb-6 border-2 border-ccl-orange border-opacity-30">
            <h2 className="text-2xl font-display font-bold text-ccl-navy mb-4">Admin Access</h2>
            <p className="text-ccl-teal mb-4">
              Access administrative settings and configuration. Only available to users with admin email addresses.
            </p>

            <button
              onClick={handleAdminAccess}
              className="bg-ccl-orange hover:bg-ccl-orange-deep text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
            >
              Access Admin Panel
            </button>
          </div>
        )}
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 px-4">
          <div className="tile-card max-w-lg w-full p-6">
            <h3 className="text-2xl font-display font-bold text-red-700 mb-4">Confirm Account Deletion</h3>
            <p className="text-ccl-teal mb-4">
              This will permanently delete your account, wallet, vault, quests, and all associated gameplay history. This action cannot be undone.
            </p>
            {deleteError && <p className="text-red-600 mb-3">{deleteError}</p>}
            <form onSubmit={handleDeleteAccount} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-ccl-teal mb-2">Password</label>
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
                <label className="block text-sm font-semibold text-ccl-teal mb-2">Type DELETE to confirm</label>
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
                  disabled={deleteLoading || deleteConfirmation.trim().toUpperCase() !== 'DELETE'}
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
export { Settings };
