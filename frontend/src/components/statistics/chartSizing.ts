import type { CSSProperties } from 'react';

export const STATISTICS_CHART_ASPECT_RATIO = 3 / 2;
export const STATISTICS_CHART_MIN_WIDTH = 300;
export const STATISTICS_CHART_MIN_HEIGHT = 200;
export const STATISTICS_CHART_MAX_HEIGHT = 320;

export const statisticsChartContainerStyle: CSSProperties = {
  minWidth: STATISTICS_CHART_MIN_WIDTH,
  minHeight: STATISTICS_CHART_MIN_HEIGHT,
  maxHeight: STATISTICS_CHART_MAX_HEIGHT,
};

export const statisticsChartPlaceholderStyle: CSSProperties = {
  ...statisticsChartContainerStyle,
  height: STATISTICS_CHART_MAX_HEIGHT,
};

export const statisticsResponsiveContainerProps = {
  aspect: STATISTICS_CHART_ASPECT_RATIO,
  minWidth: STATISTICS_CHART_MIN_WIDTH,
  minHeight: STATISTICS_CHART_MIN_HEIGHT,
  maxHeight: STATISTICS_CHART_MAX_HEIGHT,
  initialDimension: {
    width: STATISTICS_CHART_MIN_WIDTH,
    height: STATISTICS_CHART_MIN_WIDTH / STATISTICS_CHART_ASPECT_RATIO,
  },
} as const;
