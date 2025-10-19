import React, { useEffect, useState } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { getTutorialStep, getPreviousStep } from '../../config/tutorialSteps';
import './TutorialOverlay.css';

interface TutorialOverlayProps {
  onComplete?: () => void;
}

const TutorialOverlay: React.FC<TutorialOverlayProps> = ({ onComplete }) => {
  const { isActive, currentStep, advanceStep, skipTutorial, completeTutorial } = useTutorial();
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  const step = getTutorialStep(currentStep);

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
    if (step?.nextStep) {
      await advanceStep(step.nextStep);
    } else {
      await completeTutorial();
      onComplete?.();
    }
  };

  const handleBack = async () => {
    const prevStep = getPreviousStep(currentStep);
    if (prevStep) {
      await advanceStep(prevStep);
    }
  };

  const handleSkip = async () => {
    await skipTutorial();
    onComplete?.();
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
              top: highlightRect.top - 8,
              left: highlightRect.left - 8,
              width: highlightRect.width + 16,
              height: highlightRect.height + 16,
            }}
          />
        )}
      </div>

      {/* Tutorial card */}
      <div
        className={`tutorial-card tutorial-card-${step.position || 'bottom'}`}
        style={highlightRect ? {
          top: step.position === 'top'
            ? highlightRect.top - 220
            : step.position === 'bottom'
            ? highlightRect.bottom + 20
            : highlightRect.top,
          left: step.position === 'left'
            ? highlightRect.left - 320
            : step.position === 'right'
            ? highlightRect.right + 20
            : highlightRect.left + highlightRect.width / 2 - 200,
        } : undefined}
      >
        <div className="tutorial-card-content">
          <h2 className="tutorial-title">{step.title}</h2>
          <p className="tutorial-message">{step.message}</p>
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

          <div className="tutorial-actions-right">
            {step.showSkip && (
              <button
                onClick={handleSkip}
                className="tutorial-btn tutorial-btn-text"
              >
                Skip Tutorial
              </button>
            )}

            <button
              onClick={handleNext}
              className="tutorial-btn tutorial-btn-primary"
            >
              {step.nextStep ? 'Next' : 'Finish'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TutorialOverlay;
