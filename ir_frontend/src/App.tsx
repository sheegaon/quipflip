import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
import { AppProviders } from './contexts/AppProviders';
import { useIRGame } from './contexts/IRGameContext';
import Landing from './pages/Landing';
import Dashboard from './pages/Dashboard';
import BackronymCreate from './pages/BackronymCreate';
import SetTracking from './pages/SetTracking';
import Voting from './pages/Voting';
import Results from './pages/Results';
import Settings from './pages/Settings';
import './App.css';

// Suppress some logging messages
if (typeof window !== 'undefined') {
  const originalConsoleLog = console.log;
  console.log = (...args) => {
    const message = args.join(' ');
    // Vercel analytics warnings when blocked by ad blockers
    if (
      message.includes('[Vercel Web Analytics]') ||
      message.includes('[Vercel Speed Insights]') ||
      message.includes('va.vercel-scripts.com')
    ) {
      // Silently ignore Vercel analytics warnings
      return;
    }
    originalConsoleLog.apply(console, args);
  };
}

// Protected route wrapper
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useIRGame();
  return isAuthenticated ? <>{children}</> : <Navigate to="/" replace />;
};

const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public route */}
      <Route path="/" element={<Landing />} />

      {/* Protected routes */}
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/create"
        element={
          <ProtectedRoute>
            <BackronymCreate />
          </ProtectedRoute>
        }
      />
      <Route
        path="/tracking/:setId"
        element={
          <ProtectedRoute>
            <SetTracking />
          </ProtectedRoute>
        }
      />
      <Route
        path="/voting/:setId"
        element={
          <ProtectedRoute>
            <Voting />
          </ProtectedRoute>
        }
      />
      <Route
        path="/results/:setId"
        element={
          <ProtectedRoute>
            <Results />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <Settings />
          </ProtectedRoute>
        }
      />

      {/* Fallback route */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <Router>
        <AppProviders>
          <AppRoutes />
          <Analytics />
          <SpeedInsights />
        </AppProviders>
    </Router>
  );
};

export default App;
