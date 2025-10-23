import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { useState, useEffect, useRef } from 'react';
import type { RoleStatistics } from '../../api/types';

interface WinRateChartProps {
  promptStats: RoleStatistics;
  copyStats: RoleStatistics;
  voterStats: RoleStatistics;
}

export default function WinRateChart({ promptStats, copyStats, voterStats }: WinRateChartProps) {
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
    <div ref={containerRef} className="w-full h-80" style={{ minWidth: '300px', minHeight: '200px' }}>
      {isReady ? (
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
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-quip-teal">Loading chart...</div>
        </div>
      )}
    </div>
  );
}
