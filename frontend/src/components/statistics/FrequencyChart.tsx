import type { PlayFrequency } from '../../api/types';

interface FrequencyChartProps {
  frequency: PlayFrequency;
}

export default function FrequencyChart({ frequency }: FrequencyChartProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-quip-orange bg-opacity-10 p-4 rounded-tile border-2 border-quip-orange">
          <div className="text-sm text-quip-teal">Total Rounds</div>
          <div className="text-2xl font-bold text-quip-orange">{frequency.total_rounds_played}</div>
        </div>
        <div className="bg-quip-turquoise bg-opacity-10 p-4 rounded-tile border-2 border-quip-turquoise">
          <div className="text-sm text-quip-teal">Days Active</div>
          <div className="text-2xl font-bold text-quip-turquoise">{frequency.days_active}</div>
        </div>
      </div>
      <div className="bg-quip-teal bg-opacity-10 p-4 rounded-tile border-2 border-quip-teal">
        <div className="text-sm text-quip-teal">Average Rounds per Day</div>
        <div className="text-3xl font-bold text-quip-teal">{frequency.rounds_per_day.toFixed(1)}</div>
      </div>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-quip-teal">Member Since</div>
          <div className="font-medium text-quip-navy">
            {new Date(frequency.member_since).toLocaleDateString()}
          </div>
        </div>
        <div>
          <div className="text-quip-teal">Last Active</div>
          <div className="font-medium text-quip-navy">
            {new Date(frequency.last_active).toLocaleDateString()}
          </div>
        </div>
      </div>
    </div>
  );
}
