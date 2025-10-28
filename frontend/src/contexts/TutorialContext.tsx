import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { gameContextLogger } from '../utils/logger';

interface TutorialStep {
  id: string;
  title: string;
  description: string;
  completed: boolean;
  optional?: boolean;
}

interface TutorialState {
  currentStep: string | null;
  completedSteps: Set<string>;
  availableSteps: TutorialStep[];
  isActive: boolean;
  showHints: boolean;
  tutorialMode: 'guided' | 'discovery' | 'disabled';
}

interface TutorialActions {
  startTutorial: (mode?: 'guided' | 'discovery') => void;
  completeStep: (stepId: string) => void;
  skipStep: (stepId: string) => void;
  goToStep: (stepId: string) => void;
  nextStep: () => void;
  previousStep: () => void;
  endTutorial: () => void;
  resetTutorial: () => void;
  toggleHints: () => void;
  setTutorialMode: (mode: 'guided' | 'discovery' | 'disabled') => void;
  // Add aliases for backward compatibility with step parameters
  advanceStep: (stepId?: string) => void;
  skipTutorial: () => void;
  completeTutorial: () => void;
}

interface TutorialContextType {
  state: TutorialState;
  actions: TutorialActions;
  // Flatten some commonly used properties for easier access
  isActive: boolean;
  currentStep: string | null;
  tutorialStatus: string;
  startTutorial: (mode?: 'guided' | 'discovery') => void;
  advanceStep: (stepId?: string) => void;
  skipTutorial: () => void;
  completeTutorial: () => void;
  resetTutorial: () => void;
}

const TUTORIAL_STEPS: TutorialStep[] = [
  {
    id: 'welcome',
    title: 'Welcome to QuipFlip',
    description: 'Learn the basics of playing QuipFlip',
    completed: false,
  },
  {
    id: 'dashboard',
    title: 'Your Dashboard',
    description: 'Understand your game dashboard and status',
    completed: false,
  },
  {
    id: 'create-prompt',
    title: 'Create a Prompt',
    description: 'Learn how to create engaging prompts',
    completed: false,
  },
  {
    id: 'write-copy',
    title: 'Write Copy',
    description: 'Master the art of writing compelling copy',
    completed: false,
  },
  {
    id: 'vote-rounds',
    title: 'Vote on Phrases',
    description: 'Learn how voting works and earn rewards',
    completed: false,
  },
  {
    id: 'view-results',
    title: 'View Results',
    description: 'Check your performance and earnings',
    completed: false,
  },
  {
    id: 'quests',
    title: 'Complete Quests',
    description: 'Discover quests and bonus rewards',
    completed: false,
    optional: true,
  },
];

const TutorialContext = createContext<TutorialContextType | undefined>(undefined);

export const TutorialProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [tutorialState, setTutorialState] = useState<TutorialState>(() => {
    // Load tutorial state from localStorage
    if (typeof window === 'undefined') {
      return {
        currentStep: null,
        completedSteps: new Set(),
        availableSteps: TUTORIAL_STEPS,
        isActive: false,
        showHints: true,
        tutorialMode: 'guided',
      };
    }

    try {
      const stored = localStorage.getItem('tutorialState');
      if (stored) {
        const parsed = JSON.parse(stored);
        return {
          currentStep: parsed.currentStep || null,
          completedSteps: new Set(parsed.completedSteps || []),
          availableSteps: TUTORIAL_STEPS.map(step => ({
            ...step,
            completed: parsed.completedSteps?.includes(step.id) || false,
          })),
          isActive: parsed.isActive || false,
          showHints: parsed.showHints !== undefined ? parsed.showHints : true,
          tutorialMode: parsed.tutorialMode || 'guided',
        };
      }
    } catch (err) {
      gameContextLogger.warn('Failed to load tutorial state from localStorage:', err);
    }

    return {
      currentStep: null,
      completedSteps: new Set(),
      availableSteps: TUTORIAL_STEPS,
      isActive: false,
      showHints: true,
      tutorialMode: 'guided',
    };
  });

  // Persist tutorial state to localStorage
  useEffect(() => {
    if (typeof window === 'undefined') return;

    try {
      const stateToStore = {
        currentStep: tutorialState.currentStep,
        completedSteps: Array.from(tutorialState.completedSteps),
        isActive: tutorialState.isActive,
        showHints: tutorialState.showHints,
        tutorialMode: tutorialState.tutorialMode,
      };
      localStorage.setItem('tutorialState', JSON.stringify(stateToStore));
      gameContextLogger.debug('📚 Tutorial state persisted to localStorage');
    } catch (err) {
      gameContextLogger.warn('Failed to persist tutorial state:', err);
    }
  }, [tutorialState]);

  const startTutorial = useCallback((mode: 'guided' | 'discovery' = 'guided') => {
    gameContextLogger.debug('📚 Starting tutorial in mode:', mode);
    setTutorialState(prev => ({
      ...prev,
      isActive: true,
      tutorialMode: mode,
      currentStep: prev.completedSteps.has('welcome') ? null : 'welcome',
    }));
  }, []);

  const completeStep = useCallback((stepId: string) => {
    gameContextLogger.debug('✅ Completing tutorial step:', stepId);
    setTutorialState(prev => {
      const newCompletedSteps = new Set(prev.completedSteps);
      newCompletedSteps.add(stepId);
      
      const updatedSteps = prev.availableSteps.map(step =>
        step.id === stepId ? { ...step, completed: true } : step
      );

      // Auto-advance to next step in guided mode
      let nextStep = prev.currentStep;
      if (prev.tutorialMode === 'guided' && prev.currentStep === stepId) {
        const currentIndex = TUTORIAL_STEPS.findIndex(step => step.id === stepId);
        const nextIndex = currentIndex + 1;
        nextStep = nextIndex < TUTORIAL_STEPS.length ? TUTORIAL_STEPS[nextIndex].id : null;
        
        if (nextStep) {
          gameContextLogger.debug('🎯 Auto-advancing to next step:', nextStep);
        } else {
          gameContextLogger.debug('🎉 Tutorial completed!');
        }
      }

      return {
        ...prev,
        completedSteps: newCompletedSteps,
        availableSteps: updatedSteps,
        currentStep: nextStep,
        isActive: nextStep !== null,
      };
    });
  }, []);

  const skipStep = useCallback((stepId: string) => {
    gameContextLogger.debug('⏭️ Skipping tutorial step:', stepId);
    setTutorialState(prev => {
      if (prev.currentStep === stepId) {
        const currentIndex = TUTORIAL_STEPS.findIndex(step => step.id === stepId);
        const nextIndex = currentIndex + 1;
        const nextStep = nextIndex < TUTORIAL_STEPS.length ? TUTORIAL_STEPS[nextIndex].id : null;
        
        return {
          ...prev,
          currentStep: nextStep,
          isActive: nextStep !== null,
        };
      }
      return prev;
    });
  }, []);

  const goToStep = useCallback((stepId: string) => {
    gameContextLogger.debug('🎯 Going to tutorial step:', stepId);
    setTutorialState(prev => ({
      ...prev,
      currentStep: stepId,
      isActive: true,
    }));
  }, []);

  const nextStep = useCallback(() => {
    setTutorialState(prev => {
      if (!prev.currentStep) return prev;
      
      const currentIndex = TUTORIAL_STEPS.findIndex(step => step.id === prev.currentStep);
      const nextIndex = currentIndex + 1;
      const nextStepId = nextIndex < TUTORIAL_STEPS.length ? TUTORIAL_STEPS[nextIndex].id : null;
      
      gameContextLogger.debug('➡️ Moving to next tutorial step:', nextStepId);
      
      return {
        ...prev,
        currentStep: nextStepId,
        isActive: nextStepId !== null,
      };
    });
  }, []);

  const previousStep = useCallback(() => {
    setTutorialState(prev => {
      if (!prev.currentStep) return prev;
      
      const currentIndex = TUTORIAL_STEPS.findIndex(step => step.id === prev.currentStep);
      const previousIndex = currentIndex - 1;
      const previousStepId = previousIndex >= 0 ? TUTORIAL_STEPS[previousIndex].id : null;
      
      gameContextLogger.debug('⬅️ Moving to previous tutorial step:', previousStepId);
      
      return {
        ...prev,
        currentStep: previousStepId,
        isActive: true,
      };
    });
  }, []);

  const endTutorial = useCallback(() => {
    gameContextLogger.debug('🛑 Ending tutorial');
    setTutorialState(prev => ({
      ...prev,
      isActive: false,
      currentStep: null,
    }));
  }, []);

  const resetTutorial = useCallback(() => {
    gameContextLogger.debug('🔄 Resetting tutorial');
    setTutorialState({
      currentStep: null,
      completedSteps: new Set(),
      availableSteps: TUTORIAL_STEPS,
      isActive: false,
      showHints: true,
      tutorialMode: 'guided',
    });
  }, []);

  const toggleHints = useCallback(() => {
    setTutorialState(prev => {
      const newShowHints = !prev.showHints;
      gameContextLogger.debug('💡 Toggling tutorial hints:', newShowHints);
      return {
        ...prev,
        showHints: newShowHints,
      };
    });
  }, []);

  const setTutorialMode = useCallback((mode: 'guided' | 'discovery' | 'disabled') => {
    gameContextLogger.debug('📚 Setting tutorial mode:', mode);
    setTutorialState(prev => ({
      ...prev,
      tutorialMode: mode,
      isActive: mode !== 'disabled' && prev.isActive,
    }));
  }, []);

  const advanceStepWithParam = useCallback((stepId?: string) => {
    if (stepId) {
      goToStep(stepId);
    } else {
      nextStep();
    }
  }, [goToStep, nextStep]);

  const actions: TutorialActions = {
    startTutorial,
    completeStep,
    skipStep,
    goToStep,
    nextStep,
    previousStep,
    endTutorial,
    resetTutorial,
    toggleHints,
    setTutorialMode,
    // Add aliases for backward compatibility
    advanceStep: advanceStepWithParam,
    skipTutorial: endTutorial,
    completeTutorial: endTutorial,
  };

  const value: TutorialContextType = {
    state: tutorialState,
    actions,
    // Flatten commonly used properties
    isActive: tutorialState.isActive,
    currentStep: tutorialState.currentStep,
    tutorialStatus: tutorialState.isActive ? 'active' : 'inactive',
    startTutorial,
    advanceStep: advanceStepWithParam,
    skipTutorial: endTutorial,
    completeTutorial: endTutorial,
    resetTutorial,
  };

  return <TutorialContext.Provider value={value}>{children}</TutorialContext.Provider>;
};

export const useTutorial = (): TutorialContextType => {
  const context = useContext(TutorialContext);
  if (!context) {
    throw new Error('useTutorial must be used within a TutorialProvider');
  }
  return context;
};
