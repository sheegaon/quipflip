import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, PieLabelRenderProps } from 'recharts';
import type { EarningsBreakdown } from '../../api/types';

interface EarningsChartProps {
  earnings: EarningsBreakdown;
}

const COLORS = {
  prompts: '#f97316', // orange-500
  copies: '#14b8a6', // turquoise-500
  votes: '#0891b2', // teal-600
  bonuses: '#fb923c', // orange-400
};

export default function EarningsChart({ earnings }: EarningsChartProps) {
  const data = [
    { name: 'Prompt Earnings', value: earnings.prompt_earnings, color: COLORS.prompts },
    { name: 'Copy Earnings', value: earnings.copy_earnings, color: COLORS.copies },
    { name: 'Vote Earnings', value: earnings.vote_earnings, color: COLORS.votes },
    { name: 'Daily Bonuses', value: earnings.daily_bonuses, color: COLORS.bonuses },
  ].filter((item) => item.value > 0); // Only show non-zero earnings

  if (data.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center">
        <p className="text-gray-500">No earnings yet. Start playing to earn coins!</p>
      </div>
    );
  }

  const renderCustomLabel = (props: PieLabelRenderProps) => {
    const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;

    // Type guards to ensure we have the required numeric values
    if (
      typeof cx !== 'number' ||
      typeof cy !== 'number' ||
      typeof midAngle !== 'number' ||
      typeof innerRadius !== 'number' ||
      typeof outerRadius !== 'number' ||
      typeof percent !== 'number'
    ) {
      return null;
    }

    const RADIAN = Math.PI / 180;
    const radius = innerRadius + (outerRadius - innerRadius) * 0.5;
    const x = cx + radius * Math.cos(-midAngle * RADIAN);
    const y = cy + radius * Math.sin(-midAngle * RADIAN);

    return (
      <text
        x={x}
        y={y}
        fill="white"
        textAnchor={x > cx ? 'start' : 'end'}
        dominantBaseline="central"
        className="text-sm font-bold"
      >
        {`${(percent * 100).toFixed(0)}%`}
      </text>
    );
  };

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomLabel}
            outerRadius={100}
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value: number) => [`${value} coins`, 'Earned']}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
