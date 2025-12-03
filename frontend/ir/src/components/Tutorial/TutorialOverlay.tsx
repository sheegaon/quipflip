import React, { useEffect, useState, useRef } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { getTutorialStep, getPreviousStep } from '@/config/tutorialSteps';
import type { IRTutorialProgress } from '@crowdcraft/api/types.ts';
import './TutorialOverlay.css';
import { ArrowLeftIcon, ArrowRightIcon } from '../icons/ArrowIcons';
import { FlagIcon } from '../icons/EngagementIcons';

interface TutorialOverlayProps {
  onComplete?: () => void;
}

const tutorialIcons: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement>>> = {
  arrow_left: ArrowLeftIcon,
  arrow_right: ArrowRightIcon,
  flag: FlagIcon,
};

const SPOTLIGHT_PADDING = 8;
const CARD_SPACING = 20;
const CARD_DEFAULT_WIDTH = 400;
const CARD_DEFAULT_HEIGHT = 200;

const parseMarkdown = (text: string): React.ReactNode[] => {
  const lines = text.split('\n');
  const elements: React.ReactNode[] = [];

  lines.forEach((line, lineIndex) => {
    const parts = line.split(/(\*\*[^*]+?\*\*|\*[^*]+?\*|\{\{icon:[^}]+\}\})/g);
    const parsedLine = parts.map((part, partIndex) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={`${lineIndex}-${partIndex}`}>{part.slice(2, -2)}</strong>;
      } else if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
        return <em key={`${lineIndex}-${partIndex}`}>{part.slice(1, -1)}</em>;
      } else if (part.startsWith('{{icon:') && part.endsWith('}}')) {
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

    if (line.trim() === '') {
      elements.push(<div key={lineIndex} style={{ height: '0.75rem' }} />);
    } else if (line.trim().startsWith('•')) {
      elements.push(
        <div key={lineIndex} style={{ marginLeft: '1rem', marginBottom: '0.25rem' }}>
          {parsedLine}
        </div>
      );
    } else {
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
  const { isActive, currentStep, advanceStep, skipTutorial, completeTutorial } = useTutorial();
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [cardDimensions, setCardDimensions] = useState({ width: CARD_DEFAULT_WIDTH, height: CARD_DEFAULT_HEIGHT });
  const [isNavigating, setIsNavigating] = useState(false);
  const cardRef = useRef<HTMLDivElement>(null);

  const step = currentStep ? getTutorialStep(currentStep as IRTutorialProgress) : null;

  useEffect(() => {
    if (cardRef.current) {
      const rect = cardRef.current.getBoundingClientRect();
      setCardDimensions({ width: rect.width, height: rect.height });
    }
  }, [step]);

  useEffect(() => {
    if (isActive && step) {
      setIsVisible(true);

      if (step.target) {
        const targetElement = document.querySelector(step.target);
        if (targetElement) {
          const rect = targetElement.getBoundingClientRect();
          setHighlightRect(rect);
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
      if (step?.nextStep) {
        await advanceStep(step.nextStep);
      } else {
        await completeTutorial();
        onComplete?.();
      }
    } finally {
      setIsNavigating(false);
    }
  };

  const handleBack = async () => {
    if (isNavigating || !currentStep) return;
    setIsNavigating(true);
    try {
      const prevStep = getPreviousStep(currentStep as IRTutorialProgress);
      if (prevStep) {
        await advanceStep(prevStep);
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
