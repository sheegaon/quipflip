import { PieChart, Pie, Cell, ResponsiveContainer, Legend, PieLabelRenderProps } from 'recharts';
import type { EarningsBreakdown } from '../../api/types.ts';
import {
  statisticsChartContainerStyle,
  statisticsChartPlaceholderStyle,
  statisticsResponsiveContainerProps,
} from './chartSizing.ts';

interface SpendingChartProps {
  earnings: EarningsBreakdown;
}

const COLORS = {
  prompts: '#0B2137',
  copies: '#10B4A4',
  votes: '#FF9A3D',
};

const LABELS = {
  PROMPT_SPENDING: 'Prompt Spending',
  COPY_SPENDING: 'Copy Spending',
  VOTE_SPENDING: 'Vote Spending',
} as const;

export default function SpendingChart({ earnings }: SpendingChartProps) {
  const data = [
    { name: LABELS.PROMPT_SPENDING, value: earnings.prompt_spending, color: COLORS.prompts },
    { name: LABELS.COPY_SPENDING, value: earnings.copy_spending, color: COLORS.copies },
    { name: LABELS.VOTE_SPENDING, value: earnings.vote_spending, color: COLORS.votes },
  ].filter((item) => item.value > 0); // Only show non-zero costs

  if (data.length === 0) {
    return (
      <div className="w-full flex items-center justify-center" style={statisticsChartPlaceholderStyle}>
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
    <div className="w-full" style={statisticsChartContainerStyle}>
      <ResponsiveContainer width="100%" {...statisticsResponsiveContainerProps}>
        <PieChart>
          <Pie
            data={data}
            cx="50%"
            cy="50%"
            labelLine={false}
            label={renderCustomLabel}
            outerRadius="90%"
            fill="#8884d8"
            dataKey="value"
          >
            {data.map((entry, index) => (
              <Cell key={`cell-${index}`} fill={entry.color} />
            ))}
          </Pie>
          <Legend />
        </PieChart>
      </ResponsiveContainer>
    </div>
  );
}
