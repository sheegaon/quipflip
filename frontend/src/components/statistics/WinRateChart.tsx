import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import type { RoleStatistics } from '../../api/types';

interface WinRateChartProps {
  promptStats: RoleStatistics;
  copyStats: RoleStatistics;
  voterStats: RoleStatistics;
}

export default function WinRateChart({ promptStats, copyStats, voterStats }: WinRateChartProps) {
  const data = [
    {
      role: 'Prompt',
      winRate: promptStats.win_rate,
      rounds: promptStats.total_rounds,
    },
    {
      role: 'Copy',
      winRate: copyStats.win_rate,
      rounds: copyStats.total_rounds,
    },
    {
      role: 'Voter',
      winRate: voterStats.win_rate,
      rounds: voterStats.total_rounds,
    },
  ];

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
        <BarChart data={data} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="role" />
          <YAxis label={{ value: 'Win Rate (%)', angle: -90, position: 'insideLeft' }} />
          <Tooltip
            formatter={(value: number, name: string) => {
              if (name === 'winRate') return [`${value.toFixed(1)}%`, 'Win Rate'];
              if (name === 'rounds') return [value, 'Total Rounds'];
              return [value, name];
            }}
          />
          <Legend />
          <Bar dataKey="winRate" fill="#f97316" name="Win Rate (%)" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
