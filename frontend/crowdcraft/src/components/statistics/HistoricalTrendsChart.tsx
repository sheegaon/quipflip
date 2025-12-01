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
import type { HistoricalTrendPoint } from '../../api/types.ts';
import {
  STATISTICS_CHART_MIN_WIDTH,
  statisticsChartContainerStyle,
  statisticsChartPlaceholderStyle,
  statisticsResponsiveContainerProps,
} from './chartSizing.ts';

const HISTORICAL_TRENDS_ASPECT = 3 / 4;
const HISTORICAL_TRENDS_MAX_HEIGHT = 450;

const historicalChartContainerStyle = {
  ...statisticsChartContainerStyle,
  maxHeight: HISTORICAL_TRENDS_MAX_HEIGHT,
};

const historicalChartPlaceholderStyle = {
  ...statisticsChartPlaceholderStyle,
  maxHeight: HISTORICAL_TRENDS_MAX_HEIGHT,
  height: HISTORICAL_TRENDS_MAX_HEIGHT,
};

const historicalResponsiveContainerProps = {
  ...statisticsResponsiveContainerProps,
  aspect: HISTORICAL_TRENDS_ASPECT,
  maxHeight: HISTORICAL_TRENDS_MAX_HEIGHT,
  initialDimension: {
    width: STATISTICS_CHART_MIN_WIDTH,
    height: STATISTICS_CHART_MIN_WIDTH / HISTORICAL_TRENDS_ASPECT,
  },
};

interface HistoricalTrendsChartProps {
  trends: HistoricalTrendPoint[];
}

const LABELS = {
  WIN_RATE_AXIS: 'Win Rate (%)',
  WIN_RATE: 'Win Rate',
  EARNINGS_PER_DAY: 'Earnings per Day',
  ROUNDS_PER_DAY: 'Rounds per Day',
  SECONDARY_AXIS: 'Earnings / Rounds per Day',
} as const;

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
        earningsPerDay: number;
        roundsPerDay: number;
      }>;
    }

    return trends
      .map((point, index) => {
        const { label, tooltipLabel } = formatLabel(point.period, point.period || `Day ${index + 1}`);
        const parsed = Date.parse(point.period ?? '');
        const timestamp = Number.isNaN(parsed) ? index : parsed;

        return {
          label,
          tooltipLabel,
          winRate: point.win_rate,
          earningsPerDay: Math.round(point.earnings),
          roundsPerDay: Math.round(point.rounds_played),
          timestamp,
        };
      })
      .sort((a, b) => a.timestamp - b.timestamp)
      .map(({ label, tooltipLabel, winRate, earningsPerDay, roundsPerDay }) => ({
        label,
        tooltipLabel,
        winRate,
        earningsPerDay,
        roundsPerDay,
      }));
  }, [trends]);

  if (chartData.length === 0) {
    return (
      <div
        className="w-full flex items-center justify-center text-ccl-teal text-center"
        style={historicalChartPlaceholderStyle}
      >
        Historical trend data will appear once you start playing more rounds.
      </div>
    );
  }

  return (
    <div className="w-full" style={historicalChartContainerStyle}>
      <ResponsiveContainer width="100%" {...historicalResponsiveContainerProps}>
        <ComposedChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis dataKey="label" />
          <YAxis
            yAxisId="left"
            domain={[0, 100]}
            tickFormatter={(value) => `${value}%`}
            label={{ value: LABELS.WIN_RATE_AXIS, angle: -90, position: 'insideLeft' }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tickFormatter={(value) => `${Math.round(value)}`}
            label={{ value: LABELS.SECONDARY_AXIS, angle: 90, position: 'insideRight' }}
          />
          <Tooltip
            labelFormatter={(_, items) => items?.[0]?.payload?.tooltipLabel ?? ''}
            formatter={(value: number, name: string) => {
              if (name === LABELS.WIN_RATE) {
                return [`${value.toFixed(1)}%`, LABELS.WIN_RATE];
              }
              if (name === LABELS.EARNINGS_PER_DAY) {
                return [`${Math.round(value).toLocaleString()}`, LABELS.EARNINGS_PER_DAY];
              }
              if (name === LABELS.ROUNDS_PER_DAY) {
                return [`${Math.round(value).toLocaleString()}`, LABELS.ROUNDS_PER_DAY];
              }
              return [value, name];
            }}
          />
          <Legend />
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="earningsPerDay"
            fill="#14b8a6"
            stroke="#0f766e"
            name={LABELS.EARNINGS_PER_DAY}
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
            name={LABELS.WIN_RATE}
          />
          <Line
            yAxisId="right"
            type="monotone"
            dataKey="roundsPerDay"
            stroke="#6366f1"
            strokeWidth={2}
            dot={{ r: 3 }}
            activeDot={{ r: 6 }}
            name={LABELS.ROUNDS_PER_DAY}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
