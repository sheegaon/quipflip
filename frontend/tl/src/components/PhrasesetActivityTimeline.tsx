import React from 'react';

interface Activity {
  timestamp: string;
  description: string;
  type: 'guess' | 'strike' | 'completion';
}

interface PhrasesetActivityTimelineProps {
  activities?: Activity[];
}

export const PhrasesetActivityTimeline: React.FC<PhrasesetActivityTimelineProps> = ({
  activities = [],
}) => {
  if (!activities.length) {
    return (
      <div className="text-sm text-gray-500">
        No activity recorded.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {activities.map((activity, idx) => (
        <div key={idx} className="flex gap-3">
          <div className="flex-shrink-0">
            <div className={`h-8 w-8 rounded-full flex items-center justify-center text-xs font-semibold ${
              activity.type === 'guess' ? 'bg-blue-100 text-blue-700' :
              activity.type === 'strike' ? 'bg-red-100 text-red-700' :
              'bg-green-100 text-green-700'
            }`}>
              {activity.type === 'guess' ? '✓' : activity.type === 'strike' ? '✗' : '✓'}
            </div>
          </div>
          <div className="flex-1">
            <p className="text-sm text-gray-800">{activity.description}</p>
            <p className="text-xs text-gray-500 mt-1">
              {new Date(activity.timestamp).toLocaleTimeString()}
            </p>
          </div>
        </div>
      ))}
    </div>
  );
};
