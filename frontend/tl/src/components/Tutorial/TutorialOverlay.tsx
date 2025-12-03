import React, { useEffect, useState, useRef } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { getTutorialStep, getPreviousStep } from '@/config/tutorialSteps';
import type { TutorialProgress } from '@/api/types';
import './TutorialOverlay.css';
import { CopyRoundIcon, LiveModeIcon, PracticeModeIcon, VoteRoundIcon } from '@crowdcraft/components/icons/RoundIcons.tsx';
import { ArrowLeftIcon, ArrowRightIcon } from '@crowdcraft/components/icons/ArrowIcons.tsx';
import { FlagIcon } from '@crowdcraft/components/icons/EngagementIcons.tsx';
import {
  QuestActivityIcon,
  QuestClaimableIcon,
  QuestMilestoneIcon,
  QuestOverviewIcon,
  QuestQualityIcon,
  QuestStreakIcon,
} from '@crowdcraft/components/icons/QuestIcons.tsx';
import { StateEmptyIcon, StateErrorIcon, StateFilterEmptyIcon, StateLoadingIcon } from '@crowdcraft/components/icons/StateIcons.tsx';

interface TutorialOverlayProps {
  onComplete?: () => void;
}

const tutorialIcons: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  copy: CopyRoundIcon,
  vote: VoteRoundIcon,
  live: LiveModeIcon,
  practice: PracticeModeIcon,
  quest_overview: QuestOverviewIcon,
  quest_claimable: QuestClaimableIcon,
  quest_activity: QuestActivityIcon,
  quest_quality: QuestQualityIcon,
  quest_milestone: QuestMilestoneIcon,
  quest_streak: QuestStreakIcon,
  arrow_left: ArrowLeftIcon,
  arrow_right: ArrowRightIcon,
  flag: FlagIcon,
  state_error: StateErrorIcon,
  state_loading: StateLoadingIcon,
  state_empty: StateEmptyIcon,
  state_filter_empty: StateFilterEmptyIcon,
};

// Position offset constants
const SPOTLIGHT_PADDING = 8; // Padding around highlighted element
const CARD_SPACING = 20; // Space between card and target element
const CARD_DEFAULT_WIDTH = 400; // Default card width (should match CSS)
const CARD_DEFAULT_HEIGHT = 200; // Approximate card height for vertical positioning

// Simple markdown parser for tutorial messages
const parseMarkdown = (text: string): React.ReactNode[] => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];

  lines.forEach((line, lineIndex) => {
    // Parse bold (**text**), italic (*text*), and icons ({{icon:name}}) using a combined regex
    // Match **text** or *text* or {{icon:name}}
    const parts = line.split(/(\*\*[^*]+?\*\*|\*[^*]+?\*|\{\{icon:[^}]+\}\})/g);
    const parsedLine = parts.map((part, partIndex) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        // Bold text
        return <strong key={`${lineIndex}-${partIndex}`}>{part.slice(2, -2)}</strong>;
      } else if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
        // Italic text (single asterisk)
        return <em key={`${lineIndex}-${partIndex}`}>{part.slice(1, -1)}</em>;
      } else if (part.startsWith('{{icon:') && part.endsWith('}}')) {
        // Icon syntax: {{icon:iconname}}
        const iconName = part.slice(7, -2);
        const IconComponent = tutorialIcons[iconName];
        if (IconComponent) {
          return (
            <IconComponent
              key={`${lineIndex}-${partIndex}`}
              className="inline-block w-5 h-5 mx-1 align-text-bottom"
              aria-hidden="true"
            />
          );
        }
        return null;
      }
      return part;
    });

    // Render line with appropriate spacing
    if (line.trim() === '') {
      // Empty line - add spacing between paragraphs
      elements.push(<div key={lineIndex} style={{ height: '0.75rem' }} />);
    } else if (line.trim().startsWith('•')) {
      // Bullet point
      elements.push(
        <div key={lineIndex} style={{ marginLeft: '1rem', marginBottom: '0.25rem' }}>
          {parsedLine}
        </div>
      );
    } else {
      // Regular paragraph
      elements.push(
        <div key={lineIndex} style={{ marginBottom: '0.25rem' }}>
          {parsedLine}
        </div>
      );
    }
  });

  return elements;
};

const TutorialOverlay: React.FC<TutorialOverlayProps> = ({ onComplete }) => {
  const {
    state: { isActive, currentStep },
    actions: { advanceStep, skipTutorial, completeTutorial },
  } = useTutorial();
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [cardDimensions, setCardDimensions] = useState({ width: CARD_DEFAULT_WIDTH, height: CARD_DEFAULT_HEIGHT });
  const [isNavigating, setIsNavigating] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const step = currentStep ? getTutorialStep(currentStep as any) : null;

  // Measure card dimensions dynamically
  useEffect(() => {
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      setCardDimensions({ width: rect.width, height: rect.height });
    }
  }, [step]);

  useEffect(() => {
    if (isActive && step) {
      setIsVisible(true);

      // Find and highlight target element if specified
      if (step.target) {
        const targetElement = document.querySelector(step.target);
        if (targetElement) {
          const rect = targetElement.getBoundingClientRect();
          setHighlightRect(rect);

          // Scroll element into view
          targetElement.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
          setHighlightRect(null);
        }
      } else {
        setHighlightRect(null);
      }
    } else {
      setIsVisible(false);
      setHighlightRect(null);
    }
  }, [isActive, currentStep, step]);

  const handleNext = async () => {
    if (isNavigating) return;
    setIsNavigating(true);
    try {
      // Regular tutorial progression
      if (step?.nextStep) {
        advanceStep(step.nextStep as any);
      } else {
        completeTutorial();
      }
    } finally {
      setIsNavigating(false);
    }
  };

  const handleBack = async () => {
    if (isNavigating) return;
    setIsNavigating(true);
    try {
      if (currentStep) {
        const prevStep = getPreviousStep(currentStep as any);
        if (prevStep) {
          advanceStep(prevStep as any);
        }
      }
    } finally {
      setIsNavigating(false);
    }
  };

  const handleSkip = async () => {
    if (isNavigating) return;
    setIsNavigating(true);
    try {
      await skipTutorial();
      onComplete?.();
    } finally {
      setIsNavigating(false);
    }
  };

  if (!isVisible || !step) {
    return null;
  }

  return (
    <div className="tutorial-overlay">
      {/* Backdrop with spotlight effect */}
      <div className="tutorial-backdrop">
        {highlightRect && (
          <div
            className="tutorial-spotlight"
            style={{
              top: highlightRect.top - SPOTLIGHT_PADDING,
              left: highlightRect.left - SPOTLIGHT_PADDING,
              width: highlightRect.width + SPOTLIGHT_PADDING * 2,
              height: highlightRect.height + SPOTLIGHT_PADDING * 2,
            }}
          />
        )}
      </div>

      {/* Tutorial card */}
      <div
        ref={cardRef}
        className={`tutorial-card tutorial-card-${step.position || 'bottom'}`}
        style={highlightRect ? {
          top: step.position === 'top'
            ? highlightRect.top - cardDimensions.height - CARD_SPACING
            : step.position === 'bottom'
            ? highlightRect.bottom + CARD_SPACING
            : highlightRect.top,
          left: step.position === 'left'
            ? highlightRect.left - cardDimensions.width - CARD_SPACING
            : step.position === 'right'
            ? highlightRect.right + CARD_SPACING
            : highlightRect.left + highlightRect.width / 2 - cardDimensions.width / 2,
        } : undefined}
      >
        <button
          onClick={handleSkip}
          disabled={isNavigating}
          className="tutorial-close"
          aria-label="Skip tutorial"
          title="Skip tutorial"
        >
          <svg className="h-6 w-6" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="12" cy="12" r="10" fill="currentColor" opacity="0.1" />
            <path
              d="M8 8L16 16M16 8L8 16"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        </button>

        <div className="tutorial-card-content">
          <h2 className="tutorial-title">{step.title}</h2>
          <div className="tutorial-message">{parseMarkdown(step.message)}</div>
        </div>

        <div className="tutorial-actions">
          {step.showBack && (
            <button
              onClick={handleBack}
              className="tutorial-btn tutorial-btn-secondary"
            >
              Back
            </button>
          )}

          {/* Only show Next/End button if action is not 'wait' */}
          {step.action !== 'wait' && (
            <div className={!step.showBack ? 'tutorial-actions-right' : ''}>
              <button
                onClick={handleNext}
                disabled={isNavigating}
                className="tutorial-btn tutorial-btn-primary"
              >
                {isNavigating ? 'Loading...' : (step.nextStep ? 'Next' : 'End Tutorial')}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default TutorialOverlay;
