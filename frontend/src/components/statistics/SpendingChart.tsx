import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend, PieLabelRenderProps } from 'recharts';
import type { EarningsBreakdown } from '../../api/types';

interface SpendingChartProps {
  earnings: EarningsBreakdown;
}

const COLORS = {
  prompts: '#0B2137',
  copies: '#10B4A4',
  votes: '#FF9A3D',
};

export default function SpendingChart({ earnings }: SpendingChartProps) {
  const data = [
    { name: 'Prompt Costs', value: earnings.prompt_costs, color: COLORS.prompts },
    { name: 'Copy Costs', value: earnings.copy_costs, color: COLORS.copies },
    { name: 'Vote Costs', value: earnings.vote_costs, color: COLORS.votes },
  ].filter((item) => item.value > 0); // Only show non-zero costs

  if (data.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center">
        <p className="text-gray-500">No costs yet. You haven't spent any coins on rounds!</p>
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
            formatter={(value: number) => [`${value} coins`, 'Spent']}
          />
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
