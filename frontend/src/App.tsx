import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { GameProvider, useGame } from './contexts/GameContext';
import { Landing } from './pages/Landing';
import { Dashboard } from './pages/Dashboard';
import { PromptRound } from './pages/PromptRound';
import { CopyRound } from './pages/CopyRound';
import { VoteRound } from './pages/VoteRound';
import { Results } from './pages/Results';
import { PhrasesetTracking } from './pages/PhrasesetTracking';
import { ErrorNotification } from './components/ErrorNotification';

// Protected Route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useGame();

  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

// App Routes
const AppRoutes: React.FC = () => {
  const { isAuthenticated } = useGame();

  return (
    <>
      <ErrorNotification />
      <Routes>
        <Route path="/" element={isAuthenticated ? <Navigate to="/dashboard" replace /> : <Landing />} />
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
          path="/phrasesets"
          element={
            <ProtectedRoute>
              <PhrasesetTracking />
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
        <AppRoutes />
        <Analytics />
      </GameProvider>
    </Router>
  );
}

export default App;
