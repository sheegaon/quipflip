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
import type { RoleStatistics } from '../../api/types';

interface PerformanceRadarProps {
  promptStats: RoleStatistics;
  copyStats: RoleStatistics;
  voterStats: RoleStatistics;
}

export default function PerformanceRadar({ promptStats, copyStats, voterStats }: PerformanceRadarProps) {
  // Normalize metrics to 0-100 scale for radar chart
  const maxRounds = Math.max(
    promptStats.total_rounds,
    copyStats.total_rounds,
    voterStats.total_rounds,
    1
  );
  const maxEarnings = Math.max(
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
      Prompt: (promptStats.average_earnings / maxEarnings) * 100,
      Copy: (copyStats.average_earnings / maxEarnings) * 100,
      Voter: (voterStats.average_earnings / maxEarnings) * 100,
    },
    {
      metric: 'Total Earnings',
      Prompt: (promptStats.total_earnings / maxEarnings) * 100,
      Copy: (copyStats.total_earnings / maxEarnings) * 100,
      Voter: (voterStats.total_earnings / maxEarnings) * 100,
    },
  ];

  return (
    <div className="w-full h-80">
      <ResponsiveContainer width="100%" height="100%">
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
    </div>
  );
}
