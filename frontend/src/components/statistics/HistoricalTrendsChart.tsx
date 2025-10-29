import { useMemo } from 'react';
import {
  ResponsiveContainer,
  ComposedChart,
  CartesianGrid,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Area,
  Line,
} from 'recharts';
import type { HistoricalTrendPoint } from '../../api/types';

interface HistoricalTrendsChartProps {
  trends: HistoricalTrendPoint[];
}

function formatLabel(dateString: string | undefined, fallback: string): { label: string; tooltipLabel: string } {
  if (!dateString) {
    return { label: fallback, tooltipLabel: fallback };
  }

  const parsed = Date.parse(dateString);
  if (Number.isNaN(parsed)) {
    return { label: fallback, tooltipLabel: fallback };
  }

  const date = new Date(parsed);
  const shortFormatter = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
  });
  const longFormatter = new Intl.DateTimeFormat(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return { label: shortFormatter.format(date), tooltipLabel: longFormatter.format(date) };
}

export default function HistoricalTrendsChart({ trends }: HistoricalTrendsChartProps) {
  const chartData = useMemo(() => {
    if (!trends || trends.length === 0) {
      return [] as Array<{
        label: string;
        tooltipLabel: string;
        winRate: number;
        earnings: number;
        activity: number;
      }>;
    }

    return trends
      .map((point, index) => {
        const { label, tooltipLabel } = formatLabel(point.period, point.period || `Period ${index + 1}`);
        const parsed = Date.parse(point.period ?? '');
        const timestamp = Number.isNaN(parsed) ? index : parsed;

        return {
          label,
          tooltipLabel,
          winRate: point.win_rate,
          earnings: point.earnings,
          activity: point.rounds_played,
          timestamp,
        };
      })
      .sort((a, b) => a.timestamp - b.timestamp);
  }, [trends]);

  if (chartData.length === 0) {
    return (
      <div className="w-full h-80 flex items-center justify-center text-quip-teal text-center" style={{ minHeight: '200px' }}>
        Historical trend data will appear once you start playing more rounds.
      </div>
    );
  }

  return (
    <div className="w-full h-80" style={{ minWidth: '300px', minHeight: '200px' }}>
      <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
        <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis
            yAxisId="left"
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
            label={{ value: 'Win Rate (%)', angle: -90, position: 'insideLeft' }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={(value) => `${value}`}
            label={{ value: 'Earnings / Activity', angle: 90, position: 'insideRight' }}
          />
          <Tooltip
            labelFormatter={(_, items) => items?.[0]?.payload?.tooltipLabel ?? ''}
            formatter={(value: number, name: string) => {
              if (name === 'winRate') {
                return [`${value.toFixed(1)}%`, 'Win Rate'];
              }
              if (name === 'earnings') {
                return [`${value.toLocaleString()}`, 'Earnings'];
              }
              if (name === 'activity') {
                return [`${value.toLocaleString()}`, 'Rounds Played'];
              }
              return [value, name];
            }}
          />
          <Legend />
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="earnings"
            fill="#14b8a6"
            stroke="#0f766e"
            name="Earnings"
            fillOpacity={0.25}
            activeDot={{ r: 6 }}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="winRate"
            stroke="#f97316"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
            name="Win Rate"
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="activity"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
            name="Rounds Played"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
