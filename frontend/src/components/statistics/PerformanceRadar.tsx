import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts';
import { useState, useEffect, useRef } from 'react';
import type { RoleStatistics } from '../../api/types';

interface PerformanceRadarProps {
  promptStats: RoleStatistics;
  copyStats: RoleStatistics;
  voterStats: RoleStatistics;
}

export default function PerformanceRadar({ promptStats, copyStats, voterStats }: PerformanceRadarProps) {
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

  // Normalize each metric to 0-100 scale using its own maximum for balanced visualization
  const maxRounds = Math.max(
    promptStats.total_rounds,
    copyStats.total_rounds,
    voterStats.total_rounds,
    1
  );
  const maxAvgEarnings = Math.max(
    promptStats.average_earnings,
    copyStats.average_earnings,
    voterStats.average_earnings,
    1
  );
  const maxTotalEarnings = Math.max(
    promptStats.total_earnings,
    copyStats.total_earnings,
    voterStats.total_earnings,
    1
  );

  const data = [
    {
      metric: 'Total Rounds',
      Prompt: (promptStats.total_rounds / maxRounds) * 100,
      Copy: (copyStats.total_rounds / maxRounds) * 100,
      Voter: (voterStats.total_rounds / maxRounds) * 100,
    },
    {
      metric: 'Win Rate',
      Prompt: promptStats.win_rate,
      Copy: copyStats.win_rate,
      Voter: voterStats.win_rate,
    },
    {
      metric: 'Avg Earnings',
      Prompt: (promptStats.average_earnings / maxAvgEarnings) * 100,
      Copy: (copyStats.average_earnings / maxAvgEarnings) * 100,
      Voter: (voterStats.average_earnings / maxAvgEarnings) * 100,
    },
    {
      metric: 'Total Earnings',
      Prompt: (promptStats.total_earnings / maxTotalEarnings) * 100,
      Copy: (copyStats.total_earnings / maxTotalEarnings) * 100,
      Voter: (voterStats.total_earnings / maxTotalEarnings) * 100,
    },
  ];

  return (
    <div ref={containerRef} className="w-full h-80" style={{ minWidth: '300px', minHeight: '200px' }}>
      {isReady ? (
        <ResponsiveContainer width="100%" height="100%" minWidth={300} minHeight={200}>
          <RadarChart data={data}>
            <PolarGrid />
            <PolarAngleAxis dataKey="metric" />
            <PolarRadiusAxis angle={90} domain={[0, 100]} />
            <Radar name="Prompt" dataKey="Prompt" stroke="#f97316" fill="#f97316" fillOpacity={0.3} />
            <Radar name="Copy" dataKey="Copy" stroke="#14b8a6" fill="#14b8a6" fillOpacity={0.3} />
            <Radar name="Voter" dataKey="Voter" stroke="#0891b2" fill="#0891b2" fillOpacity={0.3} />
            <Legend />
            <Tooltip />
          </RadarChart>
        </ResponsiveContainer>
      ) : (
        <div className="w-full h-full flex items-center justify-center">
          <div className="text-quip-teal">Loading chart...</div>
        </div>
      )}
    </div>
  );
}
