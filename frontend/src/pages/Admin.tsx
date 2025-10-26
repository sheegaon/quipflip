import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useGame } from '../contexts/GameContext';
import { Header } from '../components/Header';
import apiClient, { extractErrorMessage } from '../api/client';
import { EditableConfigField } from '../components/EditableConfigField';

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
  vote_closing_window_seconds: number;
  vote_minimum_threshold: number;
  vote_minimum_window_seconds: number;

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
}

const Admin: React.FC = () => {
  const { state } = useGame();
  const { player } = state;
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [config, setConfig] = useState<GameConfig | null>(null);
  const [activeTab, setActiveTab] = useState<'economics' | 'timing' | 'validation' | 'ai'>('economics');
  const [editMode, setEditMode] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  useEffect(() => {
    const loadConfig = async () => {
      try {
        setLoading(true);
        setError(null);

        // Fetch actual configuration from backend
        const configData = await apiClient.getAdminConfig();
        setConfig(configData);
      } catch (err) {
        setError(extractErrorMessage(err) || 'Failed to load configuration');
      } finally {
        setLoading(false);
      }
    };

    loadConfig();
  }, []);

  const handleSaveConfig = async (key: string, value: number | string) => {
    try {
      setSaveMessage(null);
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
    } catch (err) {
      throw err; // Re-throw to let EditableConfigField handle it
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
            <button
              onClick={() => navigate('/settings')}
              className="mt-4 bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-4 rounded-tile transition-all"
            >
              Back to Settings
            </button>
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
              <button
                onClick={() => navigate('/settings')}
                className="bg-quip-navy hover:bg-quip-teal text-white font-bold py-2 px-4 rounded-tile transition-all hover:shadow-tile-sm"
              >
                Back to Settings
              </button>
            </div>
          </div>
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
                <img src="/flipcoin.png" alt="" className="w-6 h-6" />
                Player Balances
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Starting Balance"
                  value={config.starting_balance}
                  configKey="starting_balance"
                  unit="flipcoins"
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
                  unit="flipcoins"
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
                <img src="/icon_prompt.svg" alt="" className="w-6 h-6" />
                Round Costs
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Prompt Cost"
                  value={config.prompt_cost}
                  unit="flipcoins"
                  description="Cost to start a prompt round"
                configKey="prompt_cost"
                  type="number"
                  min={50}
                  max={500}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Cost (Normal)"
                  value={config.copy_cost_normal}
                  unit="flipcoins"
                  description="Standard cost to start a copy round"
                configKey="copy_cost_normal"
                  type="number"
                  min={25}
                  max={250}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Cost (Discount)"
                  value={config.copy_cost_discount}
                  unit="flipcoins"
                  description="Discounted cost when many prompts waiting"
                configKey="copy_cost_discount"
                  type="number"
                  min={20}
                  max={200}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Discount Threshold"
                  value={config.copy_discount_threshold}
                  unit="prompts"
                  description="Prompts needed to activate discount"
                configKey="copy_discount_threshold"
                  type="number"
                  min={5}
                  max={30}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Vote Cost"
                  value={config.vote_cost}
                  unit="flipcoins"
                  description="Cost to start a vote round"
                configKey="vote_cost"
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
                <img src="/icon_vote.svg" alt="" className="w-6 h-6" />
                Payouts & Penalties
              </h2>
              <div className="space-y-2">
                <EditableConfigField
                  label="Vote Payout (Correct)"
                  value={config.vote_payout_correct}
                  unit="flipcoins"
                  description="Reward for voting correctly"
                configKey="vote_payout_correct"
                  type="number"
                  min={10}
                  max={100}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Prize Pool Base"
                  value={config.prize_pool_base}
                  unit="flipcoins"
                  description="Base prize pool for phrasesets"
                configKey="prize_pool_base"
                  type="number"
                  min={100}
                  max={1000}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Abandoned Penalty"
                  value={config.abandoned_penalty}
                  unit="flipcoins"
                  description="Penalty for abandoned rounds"
                configKey="abandoned_penalty"
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
                  unit="prompts"
                  description="Maximum concurrent prompts per player"
                configKey="max_outstanding_quips"
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
                  unit="seconds"
                  description="Time to submit a prompt"
                configKey="prompt_round_seconds"
                  type="number"
                  min={60}
                  max={600}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Copy Round Duration"
                  value={config.copy_round_seconds}
                  unit="seconds"
                  description="Time to submit a copy"
                configKey="copy_round_seconds"
                  type="number"
                  min={60}
                  max={600}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Vote Round Duration"
                  value={config.vote_round_seconds}
                  unit="seconds"
                  description="Time to submit a vote"
                configKey="vote_round_seconds"
                  type="number"
                  min={30}
                  max={300}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Grace Period"
                  value={config.grace_period_seconds}
                  unit="seconds"
                  description="Extra time after expiration"
                configKey="grace_period_seconds"
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
                  unit="votes"
                  description="Auto-finalize after this many votes"
                configKey="vote_max_votes"
                  type="number"
                  min={10}
                  max={100}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Closing Threshold"
                  value={config.vote_closing_threshold}
                  unit="votes"
                  description="Votes to enter closing window"
                configKey="vote_closing_threshold"
                  type="number"
                  min={3}
                  max={20}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Closing Window"
                  value={config.vote_closing_window_seconds}
                  unit="seconds"
                  description="Time to get more votes before closing"
                configKey="vote_closing_window_seconds"
                  type="number"
                  min={30}
                  max={300}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Minimum Threshold"
                  value={config.vote_minimum_threshold}
                  unit="votes"
                  description="Minimum votes to start timeout"
                configKey="vote_minimum_threshold"
                  type="number"
                  min={2}
                  max={10}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Minimum Window"
                  value={config.vote_minimum_window_seconds}
                  unit="seconds"
                  description="Max time before auto-finalizing"
                configKey="vote_minimum_window_seconds"
                  type="number"
                  min={300}
                  max={3600}
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
                  unit="words"
                  description="Fewest words allowed in a phrase"
                configKey="phrase_min_words"
                  type="number"
                  min={1}
                  max={5}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Maximum Words"
                  value={config.phrase_max_words}
                  unit="words"
                  description="Most words allowed in a phrase"
                configKey="phrase_max_words"
                  type="number"
                  min={3}
                  max={10}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Significant Word Min Length"
                  value={config.significant_word_min_length}
                  unit="chars"
                  description="Min chars for content words"
                configKey="significant_word_min_length"
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
                  unit="chars"
                  description="Total character limit"
                configKey="phrase_max_length"
                  type="number"
                  min={50}
                  max={200}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Min Characters Per Word"
                  value={config.phrase_min_char_per_word}
                  unit="chars"
                  description="Minimum characters per word"
                configKey="phrase_min_char_per_word"
                  type="number"
                  min={1}
                  max={5}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="Max Characters Per Word"
                  value={config.phrase_max_char_per_word}
                  unit="chars"
                  description="Maximum characters per word"
                configKey="phrase_max_char_per_word"
                  type="number"
                  min={10}
                  max={30}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
              </div>
            </div>
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
                  unit="minutes"
                  description="Wait time before AI provides backups"
                configKey="ai_backup_delay_minutes"
                  type="number"
                  min={5}
                  max={60}
                  onSave={handleSaveConfig}
                  disabled={!editMode}
                />
                <EditableConfigField
                  label="API Timeout"
                  value={config.ai_timeout_seconds}
                  unit="seconds"
                  description="Timeout for AI API calls"
                configKey="ai_timeout_seconds"
                  type="number"
                  min={10}
                  max={120}
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
