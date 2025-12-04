/* eslint-disable react-refresh/only-export-components */
import React from 'react';
import { createTutorialContext, TutorialLifecycleStatus } from '@crowdcraft/contexts/TutorialContext';
import type { TLTutorialStatus } from '@crowdcraft/api/types.ts';
import { tutorialConfig } from '../config/contexts/tutorialConfig';

const { TutorialProvider: SharedTutorialProvider, useTutorial } = createTutorialContext<TLTutorialStatus>();

export { useTutorial };
export type { TutorialLifecycleStatus };

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <SharedTutorialProvider config={tutorialConfig}>{children}</SharedTutorialProvider>
);
