import React, { useEffect, useState, useRef } from 'react';
import { useTutorial } from '../../contexts/TutorialContext';
import { getTutorialStep, getPreviousStep } from '../../config/tutorialSteps';
import './TutorialOverlay.css';

interface TutorialOverlayProps {
  onComplete?: () => void;
}

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
    // Parse bold (**text**) and italic (*text*) using a combined regex
    // Match **text** or *text* but not *** (which would be bold + italic start)
    const parts = line.split(/(\*\*[^*]+?\*\*|\*[^*]+?\*)/g);
    const parsedLine = parts.map((part, partIndex) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        // Bold text
        return <strong key={`${lineIndex}-${partIndex}`}>{part.slice(2, -2)}</strong>;
      } else if (part.startsWith('*') && part.endsWith('*') && !part.startsWith('**')) {
        // Italic text (single asterisk)
        return <em key={`${lineIndex}-${partIndex}`}>{part.slice(1, -1)}</em>;
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
  const { isActive, currentStep, advanceStep, skipTutorial, completeTutorial } = useTutorial();
  const [highlightRect, setHighlightRect] = useState<DOMRect | null>(null);
  const [isVisible, setIsVisible] = useState(false);
  const [cardDimensions, setCardDimensions] = useState({ width: CARD_DEFAULT_WIDTH, height: CARD_DEFAULT_HEIGHT });
  const cardRef = useRef<HTMLDivElement>(null);

  const step = getTutorialStep(currentStep);

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
