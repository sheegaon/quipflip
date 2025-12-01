import type { PlayFrequency } from '../../api/types';
import { formatDateInUserZone } from '../../utils/datetime';

interface FrequencyChartProps {
  frequency: PlayFrequency;
}

export default function FrequencyChart({ frequency }: FrequencyChartProps) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-ccl-orange bg-opacity-10 p-4 rounded-tile border-2 border-ccl-orange">
          <div className="text-sm text-ccl-teal">Total Rounds</div>
          <div className="text-2xl font-bold text-ccl-orange">{frequency.total_rounds_played}</div>
        </div>
        <div className="bg-ccl-turquoise bg-opacity-10 p-4 rounded-tile border-2 border-ccl-turquoise">
          <div className="text-sm text-ccl-teal">Days Active</div>
          <div className="text-2xl font-bold text-ccl-turquoise">{frequency.days_active}</div>
        </div>
      </div>
      <div className="bg-ccl-teal bg-opacity-10 p-4 rounded-tile border-2 border-ccl-teal">
        <div className="text-sm text-ccl-teal">Average Rounds per Day</div>
        <div className="text-3xl font-bold text-ccl-teal">{frequency.rounds_per_day.toFixed(1)}</div>
      </div>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-ccl-teal">Member Since</div>
          <div className="font-medium text-ccl-navy">
            {formatDateInUserZone(frequency.member_since)}
          </div>
        </div>
        <div>
          <div className="text-ccl-teal">Last Active</div>
          <div className="font-medium text-ccl-navy">
            {formatDateInUserZone(frequency.last_active)}
          </div>
        </div>
      </div>
    </div>
  );
}
