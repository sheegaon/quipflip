import React from 'react';
import { ThumbsDownIcon, ThumbsUpIcon } from './icons/EngagementIcons';

export type ThumbFeedbackButtonProps =
  | {
      type: 'like' | 'dislike';
      isActive?: boolean;
      onClick: () => void;
      disabled?: boolean;
      className?: string;
    }
  | {
      onLike: () => void;
      onDislike: () => void;
      className?: string;
      likeLabel?: string;
      dislikeLabel?: string;
      disabled?: boolean;
    };

const ThumbFeedbackButton: React.FC<ThumbFeedbackButtonProps> = (props) => {
  if ('type' in props) {
    const { type, isActive = false, onClick, disabled, className = '' } = props;
    const isLike = type === 'like';
    const ThumbIcon = isLike ? ThumbsUpIcon : ThumbsDownIcon;
    const ariaLabel = isLike ? 'Like prompt' : 'Dislike prompt';

    return (
      <button
        onClick={onClick}
        disabled={disabled}
        aria-label={ariaLabel}
        className={`btn btn-secondary flex items-center gap-2 ${
          isActive ? 'ring-2 ring-ccl-teal' : ''
        } ${className}`}
      >
        <ThumbIcon className="h-5 w-5" />
      </button>
    );
  }

  const { onLike, onDislike, className = '', likeLabel = 'Good', dislikeLabel = 'Needs work', disabled } = props;

  return (
    <div className={`flex gap-3 ${className}`}>
      <button onClick={onLike} disabled={disabled} className="btn btn-secondary flex items-center gap-2" aria-label="Mark prompt as good">
        <ThumbsUpIcon className="h-5 w-5" /> <span>{likeLabel}</span>
      </button>
      <button onClick={onDislike} disabled={disabled} className="btn btn-secondary flex items-center gap-2" aria-label="Mark prompt as needs work">
        <ThumbsDownIcon className="h-5 w-5" /> <span>{dislikeLabel}</span>
      </button>
    </div>
  );
};

export default ThumbFeedbackButton;
