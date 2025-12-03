import React from 'react';

interface PhraseRecapCardProps {
  prompt: string;
  coverage: number;
  payout: number;
  strikeCount: number;
  className?: string;
}

export const PhraseRecapCard: React.FC<PhraseRecapCardProps> = ({
  prompt,
  coverage,
  payout,
  strikeCount,
  className = '',
}) => {
  return (
    <div className={`bg-white rounded-lg border border-gray-200 p-4 ${className}`}>
      <h4 className="font-semibold text-gray-800 text-sm mb-3 line-clamp-2">
        {prompt}
      </h4>
      <div className="grid grid-cols-3 gap-2 text-xs">
        <div className="text-center">
          <p className="text-gray-600">Coverage</p>
          <p className="font-semibold text-ccl-navy">{(coverage * 100).toFixed(0)}%</p>
        </div>
        <div className="text-center">
          <p className="text-gray-600">Payout</p>
          <p className="font-semibold text-green-700">${payout.toFixed(2)}</p>
        </div>
        <div className="text-center">
          <p className="text-gray-600">Strikes</p>
          <p className="font-semibold text-red-700">{strikeCount}/3</p>
        </div>
      </div>
    </div>
  );
};
