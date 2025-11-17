import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import Header from '../components/Header';
import { settingsAPI } from '../api/client';
import { getErrorMessage } from '../utils/errorHelpers';

const getErrorDetail = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  return (error as { detail?: string }).detail;
};

const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const formatDate = (dateString?: string | null) => {
  if (!dateString) return 'Not recorded';
  return new Date(dateString).toLocaleDateString();
};

const formatDateTime = (dateString?: string | null) => {
  if (!dateString) return 'Not recorded';
  return new Date(dateString).toLocaleString();
};

const Settings: React.FC = () => {
  const { player, logout, upgradeGuest, refreshDashboard } = useIRGame();
  const navigate = useNavigate();

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

  const [upgradeForm, setUpgradeForm] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
  });
  const [upgradeError, setUpgradeError] = useState<string | null>(null);
  const [upgradeSuccess, setUpgradeSuccess] = useState<string | null>(null);
  const [upgradeLoading, setUpgradeLoading] = useState(false);

  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [deletePassword, setDeletePassword] = useState('');
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  useEffect(() => {
    if (player?.email) {
      setEmailForm((prev) => ({ ...prev, newEmail: player.email ?? '' }));
    }
  }, [player?.email]);

  useEffect(() => {
    if (player?.username) {
      setUsernameForm((prev) => ({ ...prev, newUsername: player.username }));
    }
  }, [player?.username]);

  if (!player) {
    return (
      <div className="min-h-screen bg-ir-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center">Loading...</div>
        </div>
      </div>
    );
  }

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
      const response = await settingsAPI.changePassword({
        current_password: passwordForm.currentPassword,
        new_password: passwordForm.newPassword,
      });

      setPasswordSuccess(response.message || 'Password updated successfully.');
      setPasswordForm({ currentPassword: '', newPassword: '', confirmPassword: '' });
    } catch (err) {
      setPasswordError(getErrorMessage(err, 'Failed to update password'));
    } finally {
      setPasswordLoading(false);
    }
  };

  const handleUpgradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setUpgradeError(null);
    setUpgradeSuccess(null);

    if (!upgradeForm.username.trim()) {
      setUpgradeError('Please enter a username.');
      return;
    }

    if (!emailPattern.test(upgradeForm.email)) {
      setUpgradeError('Please enter a valid email address.');
      return;
    }

    if (!upgradeForm.password || upgradeForm.password.length < 8) {
      setUpgradeError('Password must be at least 8 characters long.');
      return;
    }

    if (upgradeForm.password !== upgradeForm.confirmPassword) {
      setUpgradeError('Passwords do not match.');
      return;
    }

    try {
      setUpgradeLoading(true);

      await upgradeGuest(upgradeForm.username.trim(), upgradeForm.email.trim(), upgradeForm.password);

      setUpgradeSuccess('Account upgraded successfully! You can now log in with your new credentials.');
      setUpgradeForm({ username: '', email: '', password: '', confirmPassword: '' });

      // Redirect to dashboard after a short delay
      setTimeout(() => {
        navigate('/dashboard');
      }, 2000);
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'not_a_guest') {
        setUpgradeError('This account is already a full account.');
      } else if (getErrorDetail(err) === 'email_taken') {
        setUpgradeError('That email address is already in use.');
      } else {
        setUpgradeError(getErrorMessage(err, 'Failed to upgrade account'));
      }
    } finally {
      setUpgradeLoading(false);
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
      const response = await settingsAPI.updateEmail({
        new_email: emailForm.newEmail,
        password: emailForm.password,
      });

      setEmailSuccess(`Email updated to ${response.email}`);
      setEmailForm({ newEmail: response.email, password: '' });
      await refreshDashboard();
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'email_taken') {
        setEmailError('That email address is already in use.');
      } else if (getErrorDetail(err) === 'invalid_email') {
        setEmailError('Please enter a valid email address.');
      } else {
        setEmailError(getErrorMessage(err, 'Failed to update email'));
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

    if (!usernameForm.password) {
      setUsernameError('Please confirm with your password.');
      return;
    }

    try {
      setUsernameLoading(true);
      const response = await settingsAPI.changeUsername({
        new_username: usernameForm.newUsername,
        password: usernameForm.password,
      });

      setUsernameSuccess(response.message);
      setUsernameForm({ newUsername: response.username, password: '' });
      await refreshDashboard();
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'username_taken') {
        setUsernameError('That username is already in use.');
      } else if (getErrorDetail(err) === 'invalid_username') {
        setUsernameError('Please enter a valid username.');
      } else {
        setUsernameError(getErrorMessage(err, 'Failed to update username'));
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
      await settingsAPI.deleteAccount({ password: deletePassword, confirmation: 'DELETE' });
      closeDeleteModal();
      await logout();
      navigate('/', { replace: true });
    } catch (err) {
      setDeleteError(getErrorMessage(err, 'Failed to delete account'));
    } finally {
      setDeleteLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-ir-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Header */}
        <div className="tile-card p-6 mb-6">
          <h1 className="text-3xl font-display font-bold text-ir-navy">Settings</h1>
          <p className="text-ir-teal mt-1">Manage your account and preferences</p>
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

        {/* Account Information */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">Account Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-semibold text-ir-teal mb-1">Username</label>
              <div className="bg-white border-2 border-ir-navy border-opacity-20 rounded-tile p-3 text-ir-navy">
                {player.username}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ir-teal mb-1">Email</label>
              <div className="bg-white border-2 border-ir-navy border-opacity-20 rounded-tile p-3 text-ir-navy">
                {player.email || 'Not available'}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ir-teal mb-1">Account Created</label>
              <div className="bg-white border-2 border-ir-navy border-opacity-20 rounded-tile p-3 text-ir-navy">
                {formatDate(player.created_at)}
              </div>
            </div>
            <div>
              <label className="block text-sm font-semibold text-ir-teal mb-1">Last Login</label>
              <div className="bg-white border-2 border-ir-navy border-opacity-20 rounded-tile p-3 text-ir-navy">
                {formatDateTime(player.last_login_date)}
              </div>
            </div>
          </div>
        </div>

        {/* Upgrade Guest Account */}
        {player.is_guest && (
          <div className="tile-card p-6 mb-6 bg-gradient-to-br from-orange-50 to-cyan-50 border-2 border-ir-orange">
            <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">
              Upgrade Your Guest Account
            </h2>
            <p className="text-ir-navy mb-4">
              You're currently using a guest account with limited access. Upgrade to a full account to:
            </p>
            <ul className="list-disc list-inside text-ir-navy mb-4 space-y-1">
              <li>Save your progress permanently</li>
              <li>Access your account from any device</li>
              <li>Never lose your InitCoins and stats</li>
              <li>Get higher rate limits for smoother gameplay</li>
            </ul>
            {upgradeError && <p className="text-red-600 mb-3">{upgradeError}</p>}
            {upgradeSuccess && <p className="text-green-600 mb-3">{upgradeSuccess}</p>}
            <form onSubmit={handleUpgradeSubmit} className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-ir-teal mb-2">Username</label>
                <input
                  type="text"
                  value={upgradeForm.username}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, username: e.target.value }))}
                  className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange bg-white"
                  placeholder="Choose a username"
                  disabled={upgradeLoading}
                  required
                />
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-ir-teal mb-2">Email Address</label>
                <input
                  type="email"
                  value={upgradeForm.email}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, email: e.target.value }))}
                  className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange bg-white"
                  placeholder="your@email.com"
                  disabled={upgradeLoading}
                  required
                />
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-ir-teal mb-2">Password</label>
                <input
                  type="password"
                  value={upgradeForm.password}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, password: e.target.value }))}
                  className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange bg-white"
                  placeholder="Min 8 characters"
                  disabled={upgradeLoading}
                  minLength={8}
                  required
                />
              </div>
              <div className="flex flex-col">
                <label className="text-sm font-semibold text-ir-teal mb-2">Confirm Password</label>
                <input
                  type="password"
                  value={upgradeForm.confirmPassword}
                  onChange={(e) => setUpgradeForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                  className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange bg-white"
                  placeholder="Re-enter password"
                  disabled={upgradeLoading}
                  minLength={8}
                  required
                />
              </div>
              <div className="md:col-span-4 flex justify-end">
                <button
                  type="submit"
                  disabled={upgradeLoading}
                  className="bg-ir-orange hover:bg-ir-orange-deep disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
                >
                  {upgradeLoading ? 'Upgrading...' : 'Upgrade Account'}
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Change Password */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">Change Password</h2>
          <p className="text-ir-teal mb-4">
            Update your password to keep your account secure.
          </p>
          {passwordError && <p className="text-red-600 mb-3">{passwordError}</p>}
          {passwordSuccess && <p className="text-green-600 mb-3">{passwordSuccess}</p>}
          <form onSubmit={handlePasswordSubmit} className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">Current Password</label>
              <input
                type="password"
                value={passwordForm.currentPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, currentPassword: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Enter current password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">New Password</label>
              <input
                type="password"
                value={passwordForm.newPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, newPassword: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Enter new password"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">Confirm New Password</label>
              <input
                type="password"
                value={passwordForm.confirmPassword}
                onChange={(e) => setPasswordForm((prev) => ({ ...prev, confirmPassword: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Re-enter new password"
              />
            </div>
            <div className="md:col-span-3 flex justify-end">
              <button
                type="submit"
                disabled={passwordLoading}
                className="bg-ir-turquoise hover:bg-ir-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {passwordLoading ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </form>
        </div>

        {/* Change Email */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">Change Email</h2>
          <p className="text-ir-teal mb-4">Enter a new email address and confirm with your current password.</p>
          {emailError && <p className="text-red-600 mb-3">{emailError}</p>}
          {emailSuccess && <p className="text-green-600 mb-3">{emailSuccess}</p>}
          <form onSubmit={handleEmailSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">New Email</label>
              <input
                type="email"
                value={emailForm.newEmail}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, newEmail: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="you@example.com"
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">Password</label>
              <input
                type="password"
                value={emailForm.password}
                onChange={(e) => setEmailForm((prev) => ({ ...prev, password: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Enter password"
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={emailLoading}
                className="bg-ir-turquoise hover:bg-ir-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {emailLoading ? 'Updating...' : 'Update Email'}
              </button>
            </div>
          </form>
        </div>

        {/* Change Username */}
        <div className="tile-card p-6 mb-6">
          <h2 className="text-2xl font-display font-bold text-ir-navy mb-4">Change Username</h2>
          <p className="text-ir-teal mb-4">Update your display name and confirm with your current password.</p>
          {usernameError && <p className="text-red-600 mb-3">{usernameError}</p>}
          {usernameSuccess && <p className="text-green-600 mb-3">{usernameSuccess}</p>}
          <form onSubmit={handleUsernameSubmit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">New Username</label>
              <input
                type="text"
                value={usernameForm.newUsername}
                onChange={(e) => setUsernameForm((prev) => ({ ...prev, newUsername: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Enter new username"
                minLength={3}
                maxLength={80}
              />
            </div>
            <div className="flex flex-col">
              <label className="text-sm font-semibold text-ir-teal mb-2">Password</label>
              <input
                type="password"
                value={usernameForm.password}
                onChange={(e) => setUsernameForm((prev) => ({ ...prev, password: e.target.value }))}
                className="border-2 border-ir-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-ir-orange"
                placeholder="Enter password"
              />
            </div>
            <div className="md:col-span-2 flex justify-end">
              <button
                type="submit"
                disabled={usernameLoading}
                className="bg-ir-turquoise hover:bg-ir-teal disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-6 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {usernameLoading ? 'Updating...' : 'Update Username'}
              </button>
            </div>
          </form>
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
      </div>

      {showDeleteModal && (
        <div className="fixed inset-0 bg-black bg-opacity-40 flex items-center justify-center z-50 px-4">
          <div className="tile-card max-w-lg w-full p-6">
            <h3 className="text-2xl font-display font-bold text-red-700 mb-4">Confirm Account Deletion</h3>
            <p className="text-ir-teal mb-4">
              This will permanently delete your account, wallet, vault, and all associated gameplay history. This action cannot be undone.
            </p>
            {deleteError && <p className="text-red-600 mb-3">{deleteError}</p>}
            <form onSubmit={handleDeleteAccount} className="space-y-4">
              <div>
                <label className="block text-sm font-semibold text-ir-teal mb-2">Password</label>
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
                <label className="block text-sm font-semibold text-ir-teal mb-2">Type DELETE to confirm</label>
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
