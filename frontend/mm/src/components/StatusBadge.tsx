import React from 'react';
import type { PhrasesetStatus } from '../api/types';

interface StatusConfig {
  label: string;
  className: string;
}

const STATUS_STYLES: Record<PhrasesetStatus, StatusConfig> = {
  waiting_copies: {
    label: 'Waiting for Copies',
    className: 'bg-gray-100 text-gray-700 border border-gray-200',
  },
  waiting_copy1: {
    label: 'Waiting for Final Copy',
    className: 'bg-amber-100 text-amber-800 border border-amber-200',
  },
  active: {
    label: 'Voting Active',
    className: 'bg-blue-100 text-blue-800 border border-blue-200',
  },
  voting: {
    label: 'Voting Active',
    className: 'bg-blue-100 text-blue-800 border border-blue-200',
  },
  closing: {
    label: 'Closing Soon',
    className: 'bg-purple-100 text-purple-800 border border-purple-200',
  },
  finalized: {
    label: 'Finalized',
    className: 'bg-green-100 text-green-800 border border-green-200',
  },
  abandoned: {
    label: 'Abandoned',
    className: 'bg-red-100 text-red-700 border border-red-200',
  },
};

interface StatusBadgeProps {
  status: PhrasesetStatus;
  className?: string;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status, className }) => {
  const config = STATUS_STYLES[status] ?? STATUS_STYLES.waiting_copies;
  return (
    <span
      className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-semibold ${config.className} ${
        className ?? ''
      }`}
    >
      {config.label}
    </span>
  );
};
