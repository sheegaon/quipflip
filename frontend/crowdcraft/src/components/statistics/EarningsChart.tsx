import { PieChart, Pie, Cell, ResponsiveContainer, Legend, PieLabelRenderProps } from 'recharts';
import { useState, useEffect, useRef } from 'react';
import type { QFEarningsBreakdown } from '../../api/types';
import {
  statisticsChartContainerStyle,
  statisticsChartPlaceholderStyle,
  statisticsResponsiveContainerProps,
} from './chartSizing.ts';

interface EarningsChartProps {
  earnings: QFEarningsBreakdown;
}

const COLORS = {
  prompts: '#0B2137',
  copies: '#10B4A4',
  votes: '#FF9A3D',
  bonuses: '#FBBF24',
};

const LABELS = {
  PROMPT_EARNINGS: 'Prompt Earnings',
  COPY_EARNINGS: 'Copy Earnings',
  VOTE_EARNINGS: 'Vote Earnings',
  DAILY_BONUSES: 'Daily Bonuses',
} as const;

export default function EarningsChart({ earnings }: EarningsChartProps) {
  const [isReady, setIsReady] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const timer = setTimeout(() => {
      setIsReady(true);
    }, 100);

    return () => clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!containerRef.current) return;

    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width, height } = entry.contentRect;
        if (width > 0 && height > 0) {
          setIsReady(true);
        }
      }
    });

    resizeObserver.observe(containerRef.current);

    return () => {
      resizeObserver.disconnect();
    };
  }, []);

  const data = [
    { name: LABELS.PROMPT_EARNINGS, value: earnings.prompt_earnings, color: COLORS.prompts },
    { name: LABELS.COPY_EARNINGS, value: earnings.copy_earnings, color: COLORS.copies },
    { name: LABELS.VOTE_EARNINGS, value: earnings.vote_earnings, color: COLORS.votes },
    { name: LABELS.DAILY_BONUSES, value: earnings.daily_bonuses, color: COLORS.bonuses },
  ].filter((item) => item.value > 0); // Only show non-zero earnings

  if (data.length === 0) {
    return (
      <div className="w-full flex items-center justify-center" style={statisticsChartPlaceholderStyle}>
        <p className="text-gray-500">No earnings yet. Start playing to earn coins!</p>
      </div>
    );
  }

  const renderCustomLabel = (props: PieLabelRenderProps) => {
    const { cx, cy, midAngle, innerRadius, outerRadius, percent } = props;

    // Type guards to ensure we have the required numeric values
    if (
      typeof midAngle !== 'number' ||
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
    <div ref={containerRef} className="w-full" style={statisticsChartContainerStyle}>
      {isReady ? (
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
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-ccl-teal">Loading chart...</div>
        </div>
      )}
    </div>
  );
}
