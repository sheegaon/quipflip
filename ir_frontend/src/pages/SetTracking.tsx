import React, { useState, useEffect, useRef } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useIRGame } from '../contexts/IRGameContext';
import { gameAPI } from '../api/client';
import Header from '../components/Header';
import Timer from '../components/Timer';
import type { BackronymSet } from '../api/types';

const SetTracking: React.FC = () => {
  const navigate = useNavigate();
  const { setId } = useParams<{ setId: string }>();
  const { player, checkSetStatus, activeSet } = useIRGame();

  const [set, setSet] = useState<BackronymSet | null>(activeSet);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pollingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const hasNavigatedRef = useRef(false);

  // Fetch set status
  const fetchSetStatus = async () => {
    if (!setId || hasNavigatedRef.current) return;

    try {
      setLoading(true);
      const response = await gameAPI.getSetStatus(setId);
      setSet(response.set);
      setError(null);

      // Auto-navigate to voting when status changes to voting
      if (response.set.status === 'voting' && !hasNavigatedRef.current) {
        hasNavigatedRef.current = true;
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
        // Small delay to show the "Moving to voting..." message
        setTimeout(() => {
          navigate(`/voting/${setId}`);
        }, 1500);
      }

      // Auto-navigate to results if finalized (shouldn't happen but handle it)
      if (response.set.status === 'finalized' && !hasNavigatedRef.current) {
        hasNavigatedRef.current = true;
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
        navigate(`/results/${setId}`);
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || err.message || 'Failed to fetch set status');
      setLoading(false);
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch on mount
  useEffect(() => {
    if (setId) {
      fetchSetStatus();
    }
  }, [setId]);

  // Start polling every 2 seconds
  useEffect(() => {
    if (setId && !hasNavigatedRef.current) {
      pollingIntervalRef.current = setInterval(() => {
        fetchSetStatus();
      }, 2000); // Poll every 2 seconds

      return () => {
        if (pollingIntervalRef.current) {
          clearInterval(pollingIntervalRef.current);
        }
      };
    }
  }, [setId]);

  // Redirect if no setId
  useEffect(() => {
    if (!setId) {
      navigate('/dashboard');
    }
  }, [setId, navigate]);

  if (!set || !player) {
    return (
      <div className="min-h-screen bg-gray-100">
        <Header />
        <div className="container mx-auto px-4 py-8">
          <div className="max-w-2xl mx-auto bg-white rounded-lg shadow-lg p-8 text-center">
            <div className="text-gray-600">Loading set status...</div>
          </div>
        </div>
      </div>
    );
  }

  const requiredEntries = 5;
  const currentEntries = set.entry_count;
  const progress = (currentEntries / requiredEntries) * 100;
  const entriesRemaining = requiredEntries - currentEntries;

  // Check if transitioning to voting
  const isTransitioning = set.status === 'voting' || hasNavigatedRef.current;

  return (
    <div className="min-h-screen bg-gray-100">
      <Header />
      <div className="container mx-auto px-4 py-8">
        <div className="max-w-2xl mx-auto">
          {/* Header */}
          <div className="text-center mb-6">
            <h1 className="text-3xl font-bold text-gray-800 mb-2">Waiting for Players...</h1>
            <p className="text-gray-600">
              Your backronym has been submitted for word: <strong className="text-blue-600">{set.word.toUpperCase()}</strong>
            </p>
          </div>

          {/* Main Card */}
          <div className="bg-white rounded-lg shadow-lg p-8">
            {/* Transitioning Message */}
            {isTransitioning && (
              <div className="mb-6 p-6 bg-green-100 border-2 border-green-500 rounded-lg text-center">
                <div className="text-2xl font-bold text-green-700 mb-2">
                  ✓ All Entries Received!
                </div>
                <p className="text-green-600">Moving to voting phase...</p>
              </div>
            )}

            {/* Error Message */}
            {error && !isTransitioning && (
              <div className="mb-6 p-4 bg-red-100 border border-red-400 text-red-700 rounded">
                {error}
              </div>
            )}

            {/* Progress Section */}
            {!isTransitioning && (
              <>
                <div className="mb-8">
                  <div className="flex items-center justify-between mb-3">
                    <h2 className="text-xl font-bold text-gray-800">
                      Backronym Submissions
                    </h2>
                    <span className="text-2xl font-bold text-blue-600">
                      {currentEntries} / {requiredEntries}
                    </span>
                  </div>

                  {/* Progress Bar */}
                  <div className="w-full bg-gray-200 rounded-full h-6 overflow-hidden">
                    <div
                      className="bg-blue-600 h-6 rounded-full transition-all duration-500 ease-out flex items-center justify-center"
                      style={{ width: `${progress}%` }}
                    >
                      {progress > 20 && (
                        <span className="text-white text-sm font-semibold">
                          {Math.round(progress)}%
                        </span>
                      )}
                    </div>
                  </div>

                  <p className="text-sm text-gray-600 mt-2 text-center">
                    {entriesRemaining > 0
                      ? `Waiting for ${entriesRemaining} more ${entriesRemaining === 1 ? 'entry' : 'entries'}...`
                      : 'All entries received!'}
                  </p>
                </div>

                {/* Timer Section */}
                {set.transitions_to_voting_at && (
                  <div className="mb-8 text-center">
                    <p className="text-sm text-gray-600 mb-2">Time remaining:</p>
                    <Timer
                      targetTime={set.transitions_to_voting_at}
                      className="text-4xl font-bold text-blue-600"
                      onExpire={() => {
                        // Timer expired, AI will fill remaining slots
                        // Continue polling to detect when set moves to voting
                      }}
                    />
                    <p className="text-xs text-gray-500 mt-2">
                      AI players will fill remaining slots when time expires
                    </p>
                  </div>
                )}

                {/* Status Info */}
                <div className="border-t border-gray-200 pt-6">
                  <div className="bg-blue-50 border-l-4 border-blue-500 p-4">
                    <p className="text-sm text-gray-700">
                      <strong>What's happening:</strong> We're waiting for {requiredEntries} players to submit their backronyms.
                      Once we have enough entries, you'll automatically move to the voting phase where you can vote for your favorite!
                    </p>
                  </div>
                </div>

                {/* Loading Indicator */}
                {loading && (
                  <div className="mt-4 text-center">
                    <div className="inline-flex items-center text-sm text-gray-500">
                      <svg className="animate-spin h-4 w-4 mr-2" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                      </svg>
                      Checking for updates...
                    </div>
                  </div>
                )}
              </>
            )}

            {/* Back to Dashboard Button */}
            <button
              onClick={() => navigate('/dashboard')}
              className="w-full mt-6 flex items-center justify-center gap-2 text-gray-600 hover:text-gray-800 py-2 font-medium transition-colors"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6" />
              </svg>
              <span>Back to Dashboard</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SetTracking;
