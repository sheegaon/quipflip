/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import { ResultsProvider as SharedResultsProvider, useResults } from '@crowdcraft/contexts/ResultsContext';
import { resultsConfig } from '../config/contexts/resultsConfig';

export { useResults };

export const ResultsProvider: React.FC<{ children: React.ReactNode; isAuthenticated: boolean }> = ({
  children,
  isAuthenticated,
}) => (
  <SharedResultsProvider isAuthenticated={isAuthenticated} config={resultsConfig}>
    {children}
  </SharedResultsProvider>
);
