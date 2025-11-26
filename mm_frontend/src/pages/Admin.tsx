import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '../api/client';
import { TrackingIcon } from '../components/icons/NavigationIcons';
import { VoteRoundIcon } from '../components/icons/RoundIcons';
import { EditableConfigField } from '../components/EditableConfigField';
import { adminLogger } from '../utils/logger';
import type { AdminPlayerSummary } from '../api/types';
import { formatDateTimeInUserZone } from '../utils/datetime';
import { PHRASE_VALIDATION_BOUNDS, PHRASE_VALIDATION_LIMITS } from '../config/phraseValidation';

const getErrorDetail = (error: unknown): string | undefined => {
  if (!error || typeof error !== 'object') {
    return undefined;
  }

  return (error as { detail?: string }).detail;
};

interface GameConfig {
  // Game Constants
  starting_balance: number;
  daily_bonus_amount: number;
  prompt_cost: number;
  copy_cost_normal: number;
  copy_cost_discount: number;
  vote_cost: number;
  vote_payout_correct: number;
  abandoned_penalty: number;
  prize_pool_base: number;
  max_outstanding_quips: number;
  copy_discount_threshold: number;

  // Timing
  prompt_round_seconds: number;
  copy_round_seconds: number;
  vote_round_seconds: number;
  grace_period_seconds: number;

  // Vote finalization thresholds
  vote_max_votes: number;
  vote_closing_threshold: number;
  vote_closing_window_minutes: number;
  vote_minimum_threshold: number;
  vote_minimum_window_minutes: number;

  // Phrase Validation
  phrase_min_words: number;
  phrase_max_words: number;
  phrase_max_length: number;
  phrase_min_char_per_word: number;
  phrase_max_char_per_word: number;
  significant_word_min_length: number;

  // AI Service (read-only for now)
  ai_provider: string;
  ai_openai_model: string;
  ai_gemini_model: string;
  ai_timeout_seconds: number;
  ai_backup_delay_minutes: number;
  ai_backup_batch_size: number;
  ai_backup_sleep_minutes: number;
  ai_stale_handler_enabled: boolean;
  ai_stale_threshold_days: number;
  ai_stale_check_interval_hours: number;
}

interface ValidationResult {
  is_valid: boolean;
  error_message: string | null;
  word_count: number;
  phrase_length: number;
  words: string[];
  prompt_relevance_score: number | null;
  similarity_to_original: number | null;
  similarity_to_other_copy: number | null;
  prompt_relevance_threshold: number | null;
  similarity_threshold: number | null;
  format_check_passed: boolean;
  dictionary_check_passed: boolean;
  word_conflicts: string[];
}

const Admin: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<GameConfig | null>(null);
  const [activeTab, setActiveTab] = useState<'economics' | 'timing' | 'validation' | 'phrase_validator' | 'ai'>('economics');
  const [editMode, setEditMode] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [pendingFlagCount, setPendingFlagCount] = useState(0);

  // Phrase Validator state
  const [validationType, setValidationType] = useState<'basic' | 'prompt' | 'copy'>('basic');
  const [testPhrase, setTestPhrase] = useState('');
  const [promptText, setPromptText] = useState('');
  const [originalPhrase, setOriginalPhrase] = useState('');
  const [otherCopyPhrase, setOtherCopyPhrase] = useState('');
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null);
  const [validating, setValidating] = useState(false);
  type AdminDeleteIdentifier = 'email' | 'username';
  const [adminDeleteIdentifier, setAdminDeleteIdentifier] = useState<AdminDeleteIdentifier>('email');
  const [adminDeleteValue, setAdminDeleteValue] = useState('');
  const [adminDeleteLookup, setAdminDeleteLookup] = useState<AdminPlayerSummary | null>(null);
  const [adminDeleteLoading, setAdminDeleteLoading] = useState(false);
  const [adminDeleteActionLoading, setAdminDeleteActionLoading] = useState(false);
  const [adminDeleteError, setAdminDeleteError] = useState<string | null>(null);
  const [adminDeleteSuccess, setAdminDeleteSuccess] = useState<string | null>(null);
  const [adminDeleteConfirm, setAdminDeleteConfirm] = useState('');

  // Password Reset state
  type PasswordResetIdentifier = 'email' | 'username';
  const [passwordResetIdentifier, setPasswordResetIdentifier] = useState<PasswordResetIdentifier>('email');
  const [passwordResetValue, setPasswordResetValue] = useState('');
  const [passwordResetLookup, setPasswordResetLookup] = useState<AdminPlayerSummary | null>(null);
  const [passwordResetLoading, setPasswordResetLoading] = useState(false);
  const [passwordResetActionLoading, setPasswordResetActionLoading] = useState(false);
  const [passwordResetError, setPasswordResetError] = useState<string | null>(null);
  const [passwordResetSuccess, setPasswordResetSuccess] = useState<string | null>(null);
  const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);
        adminLogger.debug('Loading admin configuration');

        // Fetch actual configuration from backend
        const configData = await apiClient.getAdminConfig();
        setConfig(configData);
        adminLogger.info('Admin configuration loaded');
      } catch (err) {
        const message = extractErrorMessage(err) || 'Failed to load configuration';
        adminLogger.error('Failed to load admin configuration', err);
        setError(message);
      } finally {
        setLoading(false);
        adminLogger.debug('Admin configuration load completed');
      }
    };

    loadConfig();
  }, []);

  useEffect(() => {
    const loadPendingFlags = async () => {
      try {
        const response = await apiClient.getFlaggedPrompts('pending');
        setPendingFlagCount(response.flags.length);
      } catch (err) {
        adminLogger.error('Failed to load pending flagged prompts', err);
      }
    };

    loadPendingFlags();
  }, []);

  const handleSaveConfig = async (key: string, value: number | string) => {
    try {
      setSaveMessage(null);
      adminLogger.debug('Updating admin config value', { key, value });
      const result = await apiClient.updateAdminConfig(key, value);

      // Update local config state
      if (config) {
        setConfig({
          ...config,
          [key]: result.value
        });
      }

      // Show success message
      setSaveMessage(`Successfully updated ${key}`);
      setTimeout(() => setSaveMessage(null), 3000);
      adminLogger.info('Admin config updated', { key });
    } catch (err) {
      adminLogger.error('Failed to update admin config value', err);
      throw err; // Re-throw to let EditableConfigField handle it
    }
  };

  const handleTestPhrase = async () => {
    if (!testPhrase.trim()) {
      return;
    }

    try {
      setValidating(true);
      adminLogger.debug('Testing phrase validation', {
        validationType,
        hasPrompt: Boolean(promptText),
        hasOriginal: Boolean(originalPhrase),
        hasOtherCopy: Boolean(otherCopyPhrase),
      });
      const data = await apiClient.testPhraseValidation(
        testPhrase,
        validationType,
        validationType !== 'basic' ? promptText || null : null,
        validationType === 'copy' ? originalPhrase || null : null,
        validationType === 'copy' ? otherCopyPhrase || null : null
      );
      setValidationResult(data);
      adminLogger.info('Phrase validation test completed', {
        validationType,
        isValid: data.is_valid,
      });
    } catch (err) {
      const message = extractErrorMessage(err) || 'Failed to test phrase validation';
      adminLogger.error('Failed to test phrase validation', err);
      setError(message);
    } finally {
      setValidating(false);
      adminLogger.debug('Phrase validation test flow completed');
    }
  };

  // Password Reset handlers
  const handlePasswordResetSearch = async () => {
    const trimmed = passwordResetValue.trim();
    if (!trimmed) {
      setPasswordResetError('Enter a value to search.');
      setPasswordResetLookup(null);
      return;
    }

    try {
      setPasswordResetLoading(true);
      setPasswordResetError(null);
      setPasswordResetSuccess(null);
      setPasswordResetLookup(null);
      setGeneratedPassword(null);
      const params = passwordResetIdentifier === 'email' ? { email: trimmed } : { username: trimmed };
      const result = await apiClient.adminSearchPlayer(params);
      setPasswordResetLookup(result);
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'player_not_found') {
        setPasswordResetError('No account found with that identifier.');
      } else {
        setPasswordResetError(extractErrorMessage(err, 'admin-search-player') || 'Failed to find player');
      }
    } finally {
      setPasswordResetLoading(false);
    }
  };

  const handlePasswordResetClear = () => {
    setPasswordResetValue('');
    setPasswordResetLookup(null);
    setPasswordResetError(null);
    setPasswordResetSuccess(null);
    setGeneratedPassword(null);
  };

  const handlePasswordResetGenerate = async () => {
    if (!passwordResetLookup) {
      setPasswordResetError('Search for a player before resetting password.');
      return;
    }

    try {
      setPasswordResetActionLoading(true);
      setPasswordResetError(null);
      setPasswordResetSuccess(null);
      setGeneratedPassword(null);
      const result = await apiClient.adminResetPassword({
        player_id: passwordResetLookup.player_id,
      });
      setGeneratedPassword(result.generated_password);
      setPasswordResetSuccess(`Password reset for ${result.username} (${result.email}).`);
      // Clear search after successful reset
      setPasswordResetLookup(null);
      setPasswordResetValue('');
    } catch (err) {
      setPasswordResetError(extractErrorMessage(err, 'admin-reset-password') || 'Failed to reset password');
    } finally {
      setPasswordResetActionLoading(false);
    }
  };

  const handleCopyPassword = () => {
    if (generatedPassword) {
      navigator.clipboard.writeText(generatedPassword);
    }
  };

  useEffect(() => {
    if (!passwordResetSuccess) {
      return;
    }
    const timer = window.setTimeout(() => {
      setPasswordResetSuccess(null);
      setGeneratedPassword(null);
    }, 30000); // Clear after 30 seconds for security
    return () => window.clearTimeout(timer);
  }, [passwordResetSuccess]);

  const handleAdminDeleteSearch = async () => {
    const trimmed = adminDeleteValue.trim();
    if (!trimmed) {
      setAdminDeleteError('Enter a value to search.');
      setAdminDeleteLookup(null);
      return;
    }

    try {
      setAdminDeleteLoading(true);
      setAdminDeleteError(null);
      setAdminDeleteSuccess(null);
      setAdminDeleteLookup(null);
      const params = adminDeleteIdentifier === 'email' ? { email: trimmed } : { username: trimmed };
      const result = await apiClient.adminSearchPlayer(params);
      setAdminDeleteLookup(result);
      setAdminDeleteConfirm('');
    } catch (err: unknown) {
      if (getErrorDetail(err) === 'player_not_found') {
        setAdminDeleteError('No account found with that identifier.');
      } else {
        setAdminDeleteError(extractErrorMessage(err, 'admin-search-player') || 'Failed to find player');
      }
    } finally {
      setAdminDeleteLoading(false);
    }
  };

  const handleAdminDeleteClear = () => {
    setAdminDeleteValue('');
    setAdminDeleteLookup(null);
    setAdminDeleteError(null);
    setAdminDeleteSuccess(null);
    setAdminDeleteConfirm('');
  };

  useEffect(() => {
    if (!adminDeleteSuccess) {
      return;
    }
    const timer = window.setTimeout(() => setAdminDeleteSuccess(null), 4000);
    return () => window.clearTimeout(timer);
  }, [adminDeleteSuccess]);

  const handleAdminDeleteAccount = async () => {
    if (!adminDeleteLookup) {
      setAdminDeleteError('Search for a player before deleting.');
      return;
    }

    if (adminDeleteConfirm.trim().toUpperCase() !== 'DELETE') {
      setAdminDeleteError('Type DELETE to confirm.');
      return;
    }

    try {
      setAdminDeleteActionLoading(true);
      setAdminDeleteError(null);
      const result = await apiClient.adminDeletePlayer({
        player_id: adminDeleteLookup.player_id,
        confirmation: 'DELETE',
      });
      setAdminDeleteSuccess(`Deleted ${result.deleted_username} (${result.deleted_email}).`);
      setAdminDeleteLookup(null);
      setAdminDeleteValue('');
      setAdminDeleteConfirm('');
    } catch (err) {
      setAdminDeleteError(extractErrorMessage(err, 'admin-delete-player') || 'Failed to delete player');
    } finally {
      setAdminDeleteActionLoading(false);
    }
  };

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

  if (loading) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="text-center py-12">
            <div className="inline-block h-8 w-8 animate-spin rounded-full border-4 border-solid border-quip-orange border-r-transparent"></div>
            <p className="mt-4 text-quip-navy font-display">Loading admin panel...</p>
          </div>
        </div>
      </div>
    );
  }

  if (error || !config) {
    return (
      <div className="min-h-screen bg-quip-cream bg-pattern">
        <Header />
        <div className="container mx-auto px-4 py-8 max-w-4xl">
          <div className="tile-card p-8">
            <h1 className="text-2xl font-display font-bold text-quip-navy mb-4">Admin Panel</h1>
            <div className="text-red-600">{error || 'Failed to load configuration'}</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-quip-cream bg-pattern">
      <Header />
      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {/* Header */}
        <div className="tile-card p-6 mb-6 border-2 border-quip-orange">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-display font-bold text-quip-navy">Admin Panel</h1>
              <p className="text-quip-teal mt-1">View and manage game configuration</p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => navigate('/admin/flags')}
                className={`rounded-tile border-2 px-4 py-2 text-sm font-semibold transition ${
                  pendingFlagCount > 0
                    ? 'border-red-500 text-red-600 hover:bg-red-600 hover:text-white'
                    : 'border-quip-teal text-quip-teal hover:bg-quip-teal hover:text-white'
                }`}
              >
                Review flagged phrases
              </button>
              <label className="flex items-center gap-2 cursor-pointer">
                <span className="text-sm font-semibold text-quip-navy">Edit Mode</span>
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={editMode}
                    onChange={(e) => setEditMode(e.target.checked)}
                    className="sr-only"
                  />
                  <div className={`block w-14 h-8 rounded-full transition-colors ${editMode ? 'bg-green-600' : 'bg-gray-300'}`}></div>
                  <div className={`dot absolute left-1 top-1 bg-white w-6 h-6 rounded-full transition-transform ${editMode ? 'transform translate-x-6' : ''}`}></div>
                </div>
              </label>
            </div>
          </div>
        </div>

        <div className="tile-card p-6 mb-6 border-2 border-orange-200">
          <h2 className="text-2xl font-display font-bold text-quip-orange mb-2">Password Reset</h2>
          <p className="text-quip-teal mb-4">
            Search for a player and generate a new password. The generated password will be displayed once and should be sent securely to the user.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-2">Search by</label>
              <select
                value={passwordResetIdentifier}
                onChange={(e) => setPasswordResetIdentifier(e.target.value as PasswordResetIdentifier)}
                className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
              >
                <option value="email">Email</option>
                <option value="username">Username</option>
              </select>
            </div>
            <div className="lg:col-span-2">
              <label className="block text-sm font-semibold text-quip-teal mb-2">Identifier</label>
              <input
                type="text"
                value={passwordResetValue}
                onChange={(e) => setPasswordResetValue(e.target.value)}
                className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder={passwordResetIdentifier === 'email' ? 'player@example.com' : 'username'}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={handlePasswordResetSearch}
              className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              disabled={passwordResetLoading}
            >
              {passwordResetLoading ? 'Searching...' : 'Find Player'}
            </button>
            <button
              onClick={handlePasswordResetClear}
              className="bg-gray-200 hover:bg-gray-300 text-quip-navy font-bold py-2 px-4 rounded-tile transition-all"
              disabled={passwordResetLoading || passwordResetActionLoading}
            >
              Clear
            </button>
          </div>
          {passwordResetError && <p className="text-red-600 mb-3">{passwordResetError}</p>}
          {passwordResetSuccess && <p className="text-green-600 mb-3">{passwordResetSuccess}</p>}
          {generatedPassword && (
            <div className="bg-green-50 border-2 border-green-200 rounded-tile p-4 mb-4">
              <h3 className="text-lg font-display font-bold text-green-700 mb-2">Generated Password</h3>
              <div className="flex items-center gap-3 mb-2">
                <code className="bg-white border-2 border-green-300 rounded px-4 py-2 font-mono text-lg font-bold text-quip-navy flex-1">
                  {generatedPassword}
                </code>
                <button
                  onClick={handleCopyPassword}
                  className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm whitespace-nowrap"
                >
                  Copy
                </button>
              </div>
              <p className="text-sm text-quip-teal">
                This password will be cleared after 30 seconds for security. Make sure to send it to the user before then.
              </p>
            </div>
          )}
          {passwordResetLookup && (
            <div className="bg-orange-50 border-2 border-orange-200 rounded-tile p-4">
              <h3 className="text-lg font-display font-bold text-quip-orange mb-2">Player Overview</h3>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-quip-navy mb-4">
                <div>
                  <dt className="font-semibold">Username</dt>
                  <dd>{passwordResetLookup.username}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Email</dt>
                  <dd>{passwordResetLookup.email}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Wallet</dt>
                  <dd>{passwordResetLookup.wallet}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Outstanding Prompts</dt>
                  <dd>{passwordResetLookup.outstanding_prompts}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="font-semibold">Created</dt>
                  <dd>{formatDateTimeInUserZone(passwordResetLookup.created_at)}</dd>
                </div>
              </dl>
              <button
                onClick={handlePasswordResetGenerate}
                className="bg-quip-orange hover:bg-quip-orange-deep disabled:bg-orange-300 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
                disabled={passwordResetActionLoading}
              >
                {passwordResetActionLoading ? 'Generating...' : 'Generate New Password'}
              </button>
            </div>
          )}
        </div>

        <div className="tile-card p-6 mb-6 border-2 border-red-200">
          <h2 className="text-2xl font-display font-bold text-red-700 mb-2">Account Cleanup</h2>
          <p className="text-quip-teal mb-4">
            Search for a player and permanently delete their account. This action cannot be undone and will remove all related gameplay data.
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            <div>
              <label className="block text-sm font-semibold text-quip-teal mb-2">Search by</label>
              <select
                value={adminDeleteIdentifier}
                onChange={(e) => setAdminDeleteIdentifier(e.target.value as AdminDeleteIdentifier)}
                className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
              >
                <option value="email">Email</option>
                <option value="username">Username</option>
              </select>
            </div>
            <div className="lg:col-span-2">
              <label className="block text-sm font-semibold text-quip-teal mb-2">Identifier</label>
              <input
                type="text"
                value={adminDeleteValue}
                onChange={(e) => setAdminDeleteValue(e.target.value)}
                className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                placeholder={adminDeleteIdentifier === 'email' ? 'player@example.com' : 'username'}
              />
            </div>
          </div>
          <div className="flex flex-wrap gap-3 mb-4">
            <button
              onClick={handleAdminDeleteSearch}
              className="bg-quip-orange hover:bg-quip-orange-deep text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              disabled={adminDeleteLoading}
            >
              {adminDeleteLoading ? 'Searching...' : 'Find Player'}
            </button>
            <button
              onClick={handleAdminDeleteClear}
              className="bg-gray-200 hover:bg-gray-300 text-quip-navy font-bold py-2 px-4 rounded-tile transition-all"
              disabled={adminDeleteLoading || adminDeleteActionLoading}
            >
              Clear
            </button>
          </div>
          {adminDeleteError && <p className="text-red-600 mb-3">{adminDeleteError}</p>}
          {adminDeleteSuccess && <p className="text-green-600 mb-3">{adminDeleteSuccess}</p>}
          {adminDeleteLookup && (
            <div className="bg-red-50 border-2 border-red-200 rounded-tile p-4">
              <h3 className="text-lg font-display font-bold text-red-700 mb-2">Player Overview</h3>
              <dl className="grid grid-cols-1 md:grid-cols-2 gap-2 text-sm text-quip-navy mb-4">
                <div>
                  <dt className="font-semibold">Username</dt>
                  <dd>{adminDeleteLookup.username}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Email</dt>
                  <dd>{adminDeleteLookup.email}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Wallet</dt>
                  <dd>{adminDeleteLookup.wallet}</dd>
                </div>
                <div>
                  <dt className="font-semibold">Outstanding Prompts</dt>
                  <dd>{adminDeleteLookup.outstanding_prompts}</dd>
                </div>
                <div className="md:col-span-2">
                  <dt className="font-semibold">Created</dt>
                  <dd>{formatDateTimeInUserZone(adminDeleteLookup.created_at)}</dd>
                </div>
              </dl>
              <div className="space-y-3">
                <div>
                  <label className="block text-sm font-semibold text-quip-teal mb-2">Type DELETE to confirm</label>
                  <input
                    type="text"
                    value={adminDeleteConfirm}
                    onChange={(e) => setAdminDeleteConfirm(e.target.value)}
                    className="w-full border-2 border-red-300 rounded-tile p-3 focus:outline-none focus:border-red-500"
                    placeholder="DELETE"
                  />
                </div>
                <button
                  onClick={handleAdminDeleteAccount}
                  className="bg-red-600 hover:bg-red-700 disabled:bg-red-300 disabled:cursor-not-allowed text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
                  disabled={adminDeleteActionLoading || adminDeleteConfirm.trim().toUpperCase() !== 'DELETE'}
                >
                  {adminDeleteActionLoading ? 'Deleting...' : 'Delete Player'}
                </button>
              </div>
            </div>
          )}
        </div>

        {/* Success Message */}
        {saveMessage && (
          <div className="tile-card p-4 mb-6 bg-green-50 border-2 border-green-300">
            <div className="flex items-start gap-3">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-green-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-green-900 font-semibold">{saveMessage}</p>
            </div>
          </div>
        )}

        {/* Info Banner - only show when NOT in edit mode */}
        {!editMode && (
          <div className="tile-card p-4 mb-6 bg-blue-50 border-2 border-blue-300">
            <div className="flex items-start gap-3">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-6 w-6 text-blue-600 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <div>
                <p className="text-blue-900 font-semibold">Read-Only Mode</p>
                <p className="text-blue-700 text-sm mt-1">
                  Enable Edit Mode above to modify configuration values. Click on any value to edit it.
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Tab Navigation */}
        <div className="tile-card p-2 mb-6">
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => setActiveTab('economics')}
              className={`flex-1 min-w-[120px] py-3 px-4 rounded-tile font-bold transition-all ${
                activeTab === 'economics'
                  ? 'bg-quip-orange text-white shadow-tile-sm'
                  : 'bg-white text-quip-navy hover:bg-quip-orange hover:bg-opacity-10'
              }`}
            >
              Economics
            </button>
            <button
              onClick={() => setActiveTab('timing')}
              className={`flex-1 min-w-[120px] py-3 px-4 rounded-tile font-bold transition-all ${
                activeTab === 'timing'
                  ? 'bg-quip-turquoise text-white shadow-tile-sm'
                  : 'bg-white text-quip-navy hover:bg-quip-turquoise hover:bg-opacity-10'
              }`}
            >
              Timing
            </button>
            <button
              onClick={() => setActiveTab('validation')}
              className={`flex-1 min-w-[120px] py-3 px-4 rounded-tile font-bold transition-all ${
                activeTab === 'validation'
                  ? 'bg-quip-navy text-white shadow-tile-sm'
                  : 'bg-white text-quip-navy hover:bg-quip-navy hover:bg-opacity-10'
              }`}
            >
              Validation
            </button>
            <button
              onClick={() => setActiveTab('phrase_validator')}
              className={`flex-1 min-w-[100px] py-3 px-4 rounded-tile font-bold transition-all ${
                activeTab === 'phrase_validator'
                  ? 'bg-green-600 text-white shadow-tile-sm'
                  : 'bg-white text-quip-navy hover:bg-green-600 hover:bg-opacity-10'
              }`}
            >
              Phrase Tester
            </button>
            <button
              onClick={() => setActiveTab('ai')}
              className={`flex-1 min-w-[120px] py-3 px-4 rounded-tile font-bold transition-all ${
                activeTab === 'ai'
                  ? 'bg-purple-600 text-white shadow-tile-sm'
                  : 'bg-white text-quip-navy hover:bg-purple-600 hover:bg-opacity-10'
              }`}
            >
              AI Service
            </button>
          </div>
        </div>

        {/* Economics Tab */}
        {activeTab === 'economics' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4 flex items-center gap-2">
                <img src="/flipcoin.png" alt="MemeCoins" className="w-6 h-6" />
                Player Balances
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Starting Balance"
                  value={config.starting_balance}
                  configKey="starting_balance"
                  unit="MemeCoins"
                  description="Initial balance for new players"
                  type="number"
                  min={1000}
                  max={10000}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Daily Bonus Amount"
                  value={config.daily_bonus_amount}
                  configKey="daily_bonus_amount"
                  unit="MemeCoins"
                  description="Daily login bonus reward"
                  type="number"
                  min={50}
                  max={500}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4 flex items-center gap-2">
                <TrackingIcon className="w-6 h-6" />
                Round Costs
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Prompt Cost"
                  value={config.prompt_cost}
                  configKey="prompt_cost"
                  unit="MemeCoins"
                  description="Cost to start a prompt round"
                  type="number"
                  min={50}
                  max={500}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Cost (Normal)"
                  value={config.copy_cost_normal}
                  configKey="copy_cost_normal"
                  unit="MemeCoins"
                  description="Standard cost to start a copy round"
                  type="number"
                  min={25}
                  max={250}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Cost (Discount)"
                  value={config.copy_cost_discount}
                  configKey="copy_cost_discount"
                  unit="MemeCoins"
                  description="Discounted cost when many prompts waiting"
                
                  type="number"
                  min={20}
                  max={200}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Discount Threshold"
                  value={config.copy_discount_threshold}
                  configKey="copy_discount_threshold"
                  unit="prompts"
                  description="Prompts needed to activate discount"
                
                  type="number"
                  min={5}
                  max={30}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Vote Cost"
                  value={config.vote_cost}
                  configKey="vote_cost"
                  unit="MemeCoins"
                  description="Cost to start a vote round"
                
                  type="number"
                  min={5}
                  max={50}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4 flex items-center gap-2">
                <VoteRoundIcon className="w-6 h-6" aria-hidden="true" />
                Payouts & Penalties
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Vote Payout (Correct)"
                  value={config.vote_payout_correct}
                  configKey="vote_payout_correct"
                  unit="MemeCoins"
                  description="Reward for voting correctly"
                
                  type="number"
                  min={10}
                  max={100}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Prize Pool Base"
                  value={config.prize_pool_base}
                  configKey="prize_pool_base"
                  unit="MemeCoins"
                  description="Base prize pool for phrasesets"
                
                  type="number"
                  min={100}
                  max={1000}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Abandoned Penalty"
                  value={config.abandoned_penalty}
                  configKey="abandoned_penalty"
                  unit="MemeCoins"
                  description="Penalty for abandoned rounds"
                
                  type="number"
                  min={0}
                  max={50}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Game Limits</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Max Outstanding Prompts"
                  value={config.max_outstanding_quips}
                  configKey="max_outstanding_quips"
                  unit="prompts"
                  description="Maximum concurrent prompts per player"
                
                  type="number"
                  min={3}
                  max={50}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>
          </div>
        )}

        {/* Timing Tab */}
        {activeTab === 'timing' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Round Durations</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Prompt Round Duration"
                  value={config.prompt_round_seconds}
                  configKey="prompt_round_seconds"
                  unit="seconds"
                  description="Time to submit a prompt"
                
                  type="number"
                  min={60}
                  max={600}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Round Duration"
                  value={config.copy_round_seconds}
                  configKey="copy_round_seconds"
                  unit="seconds"
                  description="Time to submit a copy"
                
                  type="number"
                  min={60}
                  max={600}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Vote Round Duration"
                  value={config.vote_round_seconds}
                  configKey="vote_round_seconds"
                  unit="seconds"
                  description="Time to submit a vote"
                
                  type="number"
                  min={30}
                  max={300}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Grace Period"
                  value={config.grace_period_seconds}
                  configKey="grace_period_seconds"
                  unit="seconds"
                  description="Extra time after expiration"
                
                  type="number"
                  min={0}
                  max={30}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Vote Finalization</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Maximum Votes"
                  value={config.vote_max_votes}
                  configKey="vote_max_votes"
                  unit="votes"
                  description="Auto-finalize after this many votes"
                
                  type="number"
                  min={10}
                  max={100}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Closing Threshold"
                  value={config.vote_closing_threshold}
                  configKey="vote_closing_threshold"
                  unit="votes"
                  description="Votes to enter closing window"
                
                  type="number"
                  min={3}
                  max={20}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Closing Window"
                  value={config.vote_closing_window_minutes}
                  configKey="vote_closing_window_minutes"
                  unit="minutes"
                  description="Time to get more votes before closing"

                  type="number"
                  min={1}
                  max={10}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Minimum Threshold"
                  value={config.vote_minimum_threshold}
                  configKey="vote_minimum_threshold"
                  unit="votes"
                  description="Minimum votes to start timeout"
                
                  type="number"
                  min={2}
                  max={10}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Minimum Window"
                  value={config.vote_minimum_window_minutes}
                  configKey="vote_minimum_window_minutes"
                  unit="minutes"
                  description="Max time before auto-finalizing"

                  type="number"
                  min={5}
                  max={60}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>
          </div>
        )}

        {/* Validation Tab */}
        {activeTab === 'validation' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Word Limits</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Minimum Words"
                  value={config.phrase_min_words}
                  configKey="phrase_min_words"
                  unit="words"
                  description="Fewest words allowed in a phrase"
                 
                  type="number"
                  min={PHRASE_VALIDATION_BOUNDS.minWords.min}
                  max={PHRASE_VALIDATION_BOUNDS.minWords.max}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Maximum Words"
                  value={config.phrase_max_words}
                  configKey="phrase_max_words"
                  unit="words"
                  description="Most words allowed in a phrase"
                 
                  type="number"
                  min={PHRASE_VALIDATION_BOUNDS.maxWords.min}
                  max={PHRASE_VALIDATION_BOUNDS.maxWords.max}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Significant Word Min Length"
                  value={config.significant_word_min_length}
                  configKey="significant_word_min_length"
                  unit="chars"
                  description="Min chars for content words"
                
                  type="number"
                  min={3}
                  max={6}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Character Limits</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Max Phrase Length"
                  value={config.phrase_max_length}
                  configKey="phrase_max_length"
                  unit="chars"
                  description="Total character limit"
                 
                  type="number"
                  min={PHRASE_VALIDATION_BOUNDS.maxLength.min}
                  max={PHRASE_VALIDATION_BOUNDS.maxLength.max}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Min Characters Per Word"
                  value={config.phrase_min_char_per_word}
                  configKey="phrase_min_char_per_word"
                  unit="chars"
                  description="Minimum characters per word"
                 
                  type="number"
                  min={PHRASE_VALIDATION_BOUNDS.minCharsPerWord.min}
                  max={PHRASE_VALIDATION_BOUNDS.minCharsPerWord.max}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Max Characters Per Word"
                  value={config.phrase_max_char_per_word}
                  configKey="phrase_max_char_per_word"
                  unit="chars"
                  description="Maximum characters per word"
                 
                  type="number"
                  min={PHRASE_VALIDATION_BOUNDS.maxCharsPerWord.min}
                  max={PHRASE_VALIDATION_BOUNDS.maxCharsPerWord.max}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>
          </div>
        )}

        {/* Phrase Validator Tab */}
        {activeTab === 'phrase_validator' && (
          <div className="space-y-6">
            <div className="tile-card p-6">
              <h2 className="text-2xl font-display font-bold text-quip-navy mb-4">Phrase Validation Tester</h2>
              <p className="text-quip-teal mb-6">
                Test phrase validation as if submitting to a prompt or copy round. See similarity scores and validation details.
              </p>

              {/* Validation Type Selector */}
              <div className="mb-6">
                <label className="block text-sm font-semibold text-quip-navy mb-2">Validation Type</label>
                <div className="flex gap-3">
                  <button
                    onClick={() => setValidationType('basic')}
                    className={`px-4 py-2 rounded-tile font-bold transition-all ${
                      validationType === 'basic'
                        ? 'bg-quip-navy text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    Basic Format
                  </button>
                  <button
                    onClick={() => setValidationType('prompt')}
                    className={`px-4 py-2 rounded-tile font-bold transition-all ${
                      validationType === 'prompt'
                        ? 'bg-quip-navy text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    Prompt Round
                  </button>
                  <button
                    onClick={() => setValidationType('copy')}
                    className={`px-4 py-2 rounded-tile font-bold transition-all ${
                      validationType === 'copy'
                        ? 'bg-quip-turquoise text-white'
                        : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                    }`}
                  >
                    Copy Round
                  </button>
                </div>
              </div>

              {/* Test Phrase Input */}
              <div className="mb-4">
                <label className="block text-sm font-semibold text-quip-navy mb-2">Test Phrase</label>
                <input
                  type="text"
                  value={testPhrase}
                  onChange={(e) => setTestPhrase(e.target.value)}
                  className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                  placeholder="Enter phrase to validate..."
                />
              </div>

              {/* Prompt Text (for prompt and copy validation) */}
              {validationType !== 'basic' && (
                <div className="mb-4">
                  <label className="block text-sm font-semibold text-quip-navy mb-2">Prompt Text</label>
                  <input
                    type="text"
                    value={promptText}
                    onChange={(e) => setPromptText(e.target.value)}
                    className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                    placeholder="Enter the original prompt..."
                  />
                </div>
              )}

              {/* Copy-specific fields */}
              {validationType === 'copy' && (
                <>
                  <div className="mb-4">
                    <label className="block text-sm font-semibold text-quip-navy mb-2">Original Phrase (Required for Copy)</label>
                    <input
                      type="text"
                      value={originalPhrase}
                      onChange={(e) => setOriginalPhrase(e.target.value)}
                      className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                      placeholder="Enter the original prompt phrase..."
                    />
                  </div>
                  <div className="mb-4">
                    <label className="block text-sm font-semibold text-quip-navy mb-2">Other Fake Phrase (Optional)</label>
                    <input
                      type="text"
                      value={otherCopyPhrase}
                      onChange={(e) => setOtherCopyPhrase(e.target.value)}
                      className="w-full border-2 border-quip-navy border-opacity-30 rounded-tile p-3 focus:outline-none focus:border-quip-orange"
                      placeholder="Enter the other fake phrase if it exists..."
                    />
                  </div>
                </>
              )}

              {/* Submit Button */}
              <button
                onClick={handleTestPhrase}
                disabled={validating || !testPhrase.trim()}
                className="w-full bg-green-600 hover:bg-green-700 disabled:bg-gray-300 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                {validating ? 'Validating...' : 'Test Validation'}
              </button>
            </div>

            {/* Validation Results */}
            {validationResult && (
              <div className="tile-card p-6">
                <h3 className="text-xl font-display font-bold text-quip-navy mb-4">Validation Results</h3>

                {/* Overall Status */}
                <div className={`p-4 rounded-tile mb-6 ${validationResult.is_valid ? 'bg-green-100 border-2 border-green-500' : 'bg-red-100 border-2 border-red-500'}`}>
                  <div className="flex items-center gap-3">
                    {validationResult.is_valid ? (
                      <svg className="w-8 h-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    ) : (
                      <svg className="w-8 h-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                      </svg>
                    )}
                    <div className="flex-1">
                      <p className={`font-bold text-lg ${validationResult.is_valid ? 'text-green-800' : 'text-red-800'}`}>
                        {validationResult.is_valid ? 'Valid Phrase' : 'Invalid Phrase'}
                      </p>
                      {validationResult.error_message && (
                        <p className="text-red-700 text-sm mt-1">{validationResult.error_message}</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Basic Details */}
                <div className="grid grid-cols-2 gap-4 mb-6">
                  <div className="bg-gray-50 border-2 border-gray-200 rounded-tile p-4">
                    <p className="text-sm text-quip-teal mb-1">Word Count</p>
                    <p className="text-2xl font-bold text-quip-navy">{validationResult.word_count}</p>
                    <p className="text-xs text-quip-teal mt-1">Limit: {(config.phrase_min_words ?? PHRASE_VALIDATION_LIMITS.minWordsDefault)}-{(config.phrase_max_words ?? PHRASE_VALIDATION_LIMITS.maxWordsDefault)}</p>
                  </div>
                  <div className="bg-gray-50 border-2 border-gray-200 rounded-tile p-4">
                    <p className="text-sm text-quip-teal mb-1">Character Count</p>
                    <p className="text-2xl font-bold text-quip-navy">{validationResult.phrase_length}</p>
                    <p className="text-xs text-quip-teal mt-1">Max: {config.phrase_max_length ?? PHRASE_VALIDATION_LIMITS.maxLengthDefault}</p>
                  </div>
                </div>

                {/* Words */}
                <div className="mb-6">
                  <p className="text-sm font-semibold text-quip-navy mb-2">Words Detected</p>
                  <div className="flex flex-wrap gap-2">
                    {validationResult.words.map((word, idx) => (
                      <span key={idx} className="bg-quip-navy bg-opacity-10 text-quip-navy px-3 py-1 rounded-full text-sm font-semibold">
                        {word}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Similarity Scores */}
                {(validationResult.prompt_relevance_score !== null ||
                  validationResult.similarity_to_original !== null ||
                  validationResult.similarity_to_other_copy !== null) && (
                  <div className="space-y-4 mb-6">
                    <h4 className="text-lg font-display font-bold text-quip-navy">Similarity Scores</h4>

                    {validationResult.prompt_relevance_score !== null && (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-quip-teal">Prompt Relevance</span>
                          <span className="font-bold text-quip-navy">{validationResult.prompt_relevance_score.toFixed(4)}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-4">
                          <div
                            className={`h-4 rounded-full ${
                              validationResult.prompt_relevance_score >= (validationResult.prompt_relevance_threshold || 0.05)
                                ? 'bg-green-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${Math.min(validationResult.prompt_relevance_score * 100, 100)}%` }}
                          ></div>
                        </div>
                        <p className="text-xs text-quip-teal mt-1">
                          Threshold: {validationResult.prompt_relevance_threshold?.toFixed(2)} (minimum required)
                        </p>
                      </div>
                    )}

                    {validationResult.similarity_to_original !== null && (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-quip-teal">Similarity to Original</span>
                          <span className="font-bold text-quip-navy">{validationResult.similarity_to_original.toFixed(4)}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-4">
                          <div
                            className={`h-4 rounded-full ${
                              validationResult.similarity_to_original < (validationResult.similarity_threshold || 0.8)
                                ? 'bg-green-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${validationResult.similarity_to_original * 100}%` }}
                          ></div>
                        </div>
                        <p className="text-xs text-quip-teal mt-1">
                          Threshold: {validationResult.similarity_threshold?.toFixed(2)} (maximum allowed)
                        </p>
                      </div>
                    )}

                    {validationResult.similarity_to_other_copy !== null && (
                      <div>
                        <div className="flex justify-between text-sm mb-1">
                          <span className="text-quip-teal">Similarity to Other Fake</span>
                          <span className="font-bold text-quip-navy">{validationResult.similarity_to_other_copy.toFixed(4)}</span>
                        </div>
                        <div className="w-full bg-gray-200 rounded-full h-4">
                          <div
                            className={`h-4 rounded-full ${
                              validationResult.similarity_to_other_copy < (validationResult.similarity_threshold || 0.8)
                                ? 'bg-green-500'
                                : 'bg-red-500'
                            }`}
                            style={{ width: `${validationResult.similarity_to_other_copy * 100}%` }}
                          ></div>
                        </div>
                        <p className="text-xs text-quip-teal mt-1">
                          Threshold: {validationResult.similarity_threshold?.toFixed(2)} (maximum allowed)
                        </p>
                      </div>
                    )}
                  </div>
                )}

                {/* Word Conflicts */}
                {validationResult.word_conflicts.length > 0 && (
                  <div className="mb-6">
                    <p className="text-sm font-semibold text-quip-navy mb-2">Word Conflicts</p>
                    <div className="flex flex-wrap gap-2">
                      {validationResult.word_conflicts.map((word, idx) => (
                        <span key={idx} className="bg-red-100 text-red-700 px-3 py-1 rounded-full text-sm font-semibold border-2 border-red-300">
                          {word}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Validation Checks */}
                <div className="grid grid-cols-2 gap-4">
                  <div className={`p-3 rounded-tile border-2 ${
                    validationResult.format_check_passed
                      ? 'bg-green-50 border-green-300'
                      : 'bg-red-50 border-red-300'
                  }`}>
                    <p className="text-sm font-semibold">Format Check</p>
                    <p className={`text-lg font-bold ${
                      validationResult.format_check_passed ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {validationResult.format_check_passed ? 'Passed' : 'Failed'}
                    </p>
                  </div>
                  <div className={`p-3 rounded-tile border-2 ${
                    validationResult.dictionary_check_passed
                      ? 'bg-green-50 border-green-300'
                      : 'bg-red-50 border-red-300'
                  }`}>
                    <p className="text-sm font-semibold">Dictionary Check</p>
                    <p className={`text-lg font-bold ${
                      validationResult.dictionary_check_passed ? 'text-green-700' : 'text-red-700'
                    }`}>
                      {validationResult.dictionary_check_passed ? 'Passed' : 'Failed'}
                    </p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* AI Service Tab */}
        {activeTab === 'ai' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">AI Provider Settings</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Active Provider"
                  value={config.ai_provider}
                  description="Current AI service provider"
                configKey="ai_provider"
                  type="select"
                  options={["openai", "gemini"]}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="OpenAI Model"
                  value={config.ai_openai_model}
                  description="Model used for OpenAI requests"
                configKey="ai_openai_model"
                  type="text"
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Gemini Model"
                  value={config.ai_gemini_model}
                  description="Model used for Gemini requests"
                configKey="ai_gemini_model"
                  type="text"
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">AI Backup System</h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Backup Delay"
                  value={config.ai_backup_delay_minutes}
                  configKey="ai_backup_delay_minutes"
                  unit="minutes"
                  description="Wait time before AI provides backups"

                  type="number"
                  min={5}
                  max={60}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Backup Batch Size"
                  value={config.ai_backup_batch_size}
                  configKey="ai_backup_batch_size"
                  unit="rounds"
                  description="Maximum rounds processed per cycle"

                  type="number"
                  min={1}
                  max={50}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="API Timeout"
                  value={config.ai_timeout_seconds}
                  configKey="ai_timeout_seconds"
                  unit="seconds"
                  description="Timeout for AI API calls"

                  type="number"
                  min={10}
                  max={120}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Backup Sleep"
                  value={config.ai_backup_sleep_minutes}
                  configKey="ai_backup_sleep_minutes"
                  unit="minutes"
                  description="Sleep between backup cycles"

                  type="number"
                  min={5}
                  max={120}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>

            <div className="tile-card p-6">
              <h2 className="text-xl font-display font-bold text-quip-navy mb-4">Stale AI Handler</h2>
              <p className="text-sm text-gray-600 mb-4">
                Handles abandoned content (3+ days old). Processes all stale content every 12 hours by default.
              </p>
              <div className="space-y-2">
                <EditableConfigField
                  label="Stale Handler Enabled"
                  value={config.ai_stale_handler_enabled ? "true" : "false"}
                  configKey="ai_stale_handler_enabled"
                  description="Enable stale content handler"

                  type="select"
                  options={["true", "false"]}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Stale Threshold"
                  value={config.ai_stale_threshold_days}
                  configKey="ai_stale_threshold_days"
                  unit="days"
                  description="Age before content is considered stale (min 3 days)"

                  type="number"
                  min={3}
                  max={30}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Check Interval"
                  value={config.ai_stale_check_interval_hours}
                  configKey="ai_stale_check_interval_hours"
                  unit="hours"
                  description="Hours between stale content checks"

                  type="number"
                  min={1}
                  max={72}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Admin;
