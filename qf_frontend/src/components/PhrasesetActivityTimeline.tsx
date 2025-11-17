/**
 * Phraseset activity timeline component.
 *
 * Displays a chronological timeline of lifecycle events for a phraseset
 * (prompt submission, copy submissions, votes, finalization, etc.).
 *
 * This is distinct from the "Who's Online" feature (OnlineUsers page), which shows
 * real-time user activity.
 */
import React from 'react';
import type { PhrasesetActivityEntry } from '../api/types';
import { formatDateTimeInUserZone } from '../utils/datetime';

interface ActivityTimelineProps {
  activities: PhrasesetActivityEntry[];
}

const ACTIVITY_MAP: Record<string, { icon: string; title: string }> = {
  prompt_submitted: { icon: '🎯', title: 'Prompt Submitted' },
  prompt_created: { icon: '🎯', title: 'Prompt Submitted' },
  copy1_submitted: { icon: '📝', title: 'First Copy Submitted' },
  copy2_submitted: { icon: '📝', title: 'Second Copy Submitted' },
  vote_submitted: { icon: '🗳️', title: 'Vote Received' },
  third_vote_reached: { icon: '3️⃣', title: 'Reached 3 Votes' },
  fifth_vote_reached: { icon: '5️⃣', title: 'Reached 5 Votes' },
  finalized: { icon: '✅', title: 'Phraseset Finalized' },
};

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({ activities }) => {
  if (!activities.length) {
    return (
      <div className="text-sm text-gray-500">No activity yet. Check back soon!</div>
    );
  }

  return (
    <ol className="relative border-l border-gray-200 pl-4">
      {activities.map((activity) => {
        const config = ACTIVITY_MAP[activity.activity_type] ?? {
          icon: '📌',
          title: activity.activity_type.replace(/_/g, ' ').replace(/\b\w/g, char => char.toUpperCase()),
        };

        const metadataEntries = Object.entries(activity.metadata || {});

        return (
          <li key={activity.activity_id} className="mb-6 ml-4">
            <span className="absolute -left-2 flex h-4 w-4 items-center justify-center rounded-full bg-white border border-gray-300">
              <span className="text-xs" aria-hidden>{config.icon}</span>
            </span>
            <div className="bg-gray-50 border border-gray-200 rounded-lg p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-gray-800">{config.title}</p>
                <span className="text-xs text-gray-500">
                  {formatDateTimeInUserZone(activity.created_at)}
                </span>
              </div>
              {(activity.player_username || activity.player_id) && (
                <p className="text-xs text-gray-600 mt-1">
                  {activity.player_username || activity.player_id}
                </p>
              )}
              {metadataEntries.length > 0 && (
                <dl className="mt-2 text-xs text-gray-600 grid gap-1">
                  {metadataEntries.map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <dt className="capitalize mr-2">{key.replace(/_/g, ' ')}:</dt>
                      <dd className="text-right font-medium text-gray-700">
                        {typeof value === 'boolean'
                          ? value ? 'Yes' : 'No'
                          : Array.isArray(value)
                            ? value.join(', ')
                            : String(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
};
