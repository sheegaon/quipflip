import type { PlayFrequency } from '../../api/types';

interface FrequencyChartProps {
  frequency: PlayFrequency;
}

export default function FrequencyChart({ frequency }: FrequencyChartProps) {

  return (
    <div className="w-full h-80">
      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="bg-orange-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">Total Rounds</div>
            <div className="text-2xl font-bold text-orange-500">{frequency.total_rounds_played}</div>
          </div>
          <div className="bg-turquoise-50 p-4 rounded-lg">
            <div className="text-sm text-gray-600">Days Active</div>
            <div className="text-2xl font-bold text-turquoise-500">{frequency.days_active}</div>
          </div>
        </div>
        <div className="bg-teal-50 p-4 rounded-lg">
          <div className="text-sm text-gray-600">Average Rounds per Day</div>
          <div className="text-3xl font-bold text-teal-600">{frequency.rounds_per_day.toFixed(1)}</div>
        </div>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <div className="text-gray-600">Member Since</div>
            <div className="font-medium text-gray-900">
              {new Date(frequency.member_since).toLocaleDateString()}
            </div>
          </div>
          <div>
            <div className="text-gray-600">Last Active</div>
            <div className="font-medium text-gray-900">
              {new Date(frequency.last_active).toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
