import React from 'react';

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
    return (
      <button
        onClick={onClick}
        disabled={disabled}
        className={`btn btn-secondary flex items-center gap-2 ${
          isActive ? 'ring-2 ring-ccl-teal' : ''
        } ${className}`}
      >
        {isLike ? '👍' : '👎'}
      </button>
    );
  }

  const { onLike, onDislike, className = '', likeLabel = 'Good', dislikeLabel = 'Needs work', disabled } = props;

  return (
    <div className={`flex gap-3 ${className}`}>
      <button onClick={onLike} disabled={disabled} className="btn btn-secondary flex items-center gap-2">
        👍 <span>{likeLabel}</span>
      </button>
      <button onClick={onDislike} disabled={disabled} className="btn btn-secondary flex items-center gap-2">
        👎 <span>{dislikeLabel}</span>
      </button>
    </div>
  );
};

export default ThumbFeedbackButton;
