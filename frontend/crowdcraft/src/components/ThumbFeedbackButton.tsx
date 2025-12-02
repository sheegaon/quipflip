import React from 'react';

export interface ThumbFeedbackButtonProps {
  onLike: () => void;
  onDislike: () => void;
  className?: string;
  likeLabel?: string;
  dislikeLabel?: string;
}

const ThumbFeedbackButton: React.FC<ThumbFeedbackButtonProps> = ({
  onLike,
  onDislike,
  className = '',
  likeLabel = 'Good',
  dislikeLabel = 'Needs work',
}) => {
  return (
    <div className={`flex gap-3 ${className}`}>
      <button
        onClick={onLike}
        className="btn btn-secondary flex items-center gap-2"
      >
        👍 <span>{likeLabel}</span>
      </button>
      <button
        onClick={onDislike}
        className="btn btn-secondary flex items-center gap-2"
      >
        👎 <span>{dislikeLabel}</span>
      </button>
    </div>
  );
};

export default ThumbFeedbackButton;
