import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { GameProvider, useGame } from './contexts/GameContext';
import { TutorialProvider } from './contexts/TutorialContext';
import { Landing } from './pages/Landing';
import { Dashboard } from './pages/Dashboard';
import { PromptRound } from './pages/PromptRound';
import { CopyRound } from './pages/CopyRound';
import { VoteRound } from './pages/VoteRound';
import { Results } from './pages/Results';
import { Tracking } from './pages/Tracking';
import Statistics from './pages/Statistics';
import { ErrorNotification } from './components/ErrorNotification';
import TutorialOverlay from './components/Tutorial/TutorialOverlay';

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { state } = useGame();

  if (!state.isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

// App Routes
const AppRoutes: React.FC = () => {
  const { state } = useGame();

  return (
    <>
      <ErrorNotification />
      <TutorialOverlay />
      <Routes>
        <Route path="/" element={state.isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
        <Route
          path="/prompt"
          element={
            <ProtectedRoute>
              <PromptRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/copy"
          element={
            <ProtectedRoute>
              <CopyRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/vote"
          element={
            <ProtectedRoute>
              <VoteRound />
            </ProtectedRoute>
          }
        />
        <Route
          path="/results"
          element={
            <ProtectedRoute>
              <Results />
            </ProtectedRoute>
          }
        />
        <Route
          path="/tracking"
          element={
            <ProtectedRoute>
              <Tracking />
            </ProtectedRoute>
          }
        />
        <Route
          path="/statistics"
          element={
            <ProtectedRoute>
              <Statistics />
            </ProtectedRoute>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  );
};

// Main App
function App() {
  return (
    <Router
      future={{
        v7_startTransition: true,
        v7_relativeSplatPath: true,
      }}
    >
      <GameProvider>
        <TutorialProvider>
          <AppRoutes />
          <Analytics />
          <SpeedInsights />
        </TutorialProvider>
      </GameProvider>
    </Router>
  );
}

export default App;
