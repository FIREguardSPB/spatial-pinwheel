import React from 'react';

type Datum = Record<string, unknown>;

interface SimpleAreaChartProps<T extends Datum> {
  data: T[];
  xKey: keyof T;
  yKey: keyof T;
  height?: number;
  color?: string;
  className?: string;
  emptyLabel?: string;
  formatValue?: (value: number) => string;
  formatLabel?: (label: unknown) => string;
  showGrid?: boolean;
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function SimpleAreaChart<T extends Datum>({
  data,
  xKey,
  yKey,
  height = 220,
  color = '#10b981',
  className = '',
  emptyLabel = 'нет данных',
  formatValue,
  formatLabel,
  showGrid = true,
}: SimpleAreaChartProps<T>) {
  const [hoverIndex, setHoverIndex] = React.useState<number | null>(null);

  const values = React.useMemo(
    () => data.map((item) => Number(item[yKey] ?? 0)).filter((value) => Number.isFinite(value)),
    [data, yKey],
  );

  const width = 1000;
  const chartHeight = height;
  const margin = { top: 12, right: 12, bottom: 20, left: 12 };
  const innerWidth = width - margin.left - margin.right;
  const innerHeight = chartHeight - margin.top - margin.bottom;

  if (values.length < 2) {
    return (
      <div className={`h-full min-h-[48px] flex items-center justify-center text-gray-700 text-xs ${className}`}>
        {emptyLabel}
      </div>
    );
  }

  const minValue = Math.min(...values);
  const maxValue = Math.max(...values);
  const valueRange = Math.max(maxValue - minValue, 1e-9);

  const points = data.map((item, index) => {
    const value = Number(item[yKey] ?? 0);
    const x = margin.left + (index / Math.max(data.length - 1, 1)) * innerWidth;
    const normalized = (value - minValue) / valueRange;
    const y = margin.top + (1 - normalized) * innerHeight;
    return { x, y, value, label: item[xKey] };
  });

  const linePath = points
    .map((point, index) => `${index === 0 ? 'M' : 'L'} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(' ');
  const areaPath = `${linePath} L ${points[points.length - 1].x.toFixed(2)} ${(chartHeight - margin.bottom).toFixed(2)} L ${points[0].x.toFixed(2)} ${(chartHeight - margin.bottom).toFixed(2)} Z`;

  const activeIndex = hoverIndex != null ? clamp(hoverIndex, 0, points.length - 1) : null;
  const activePoint = activeIndex != null ? points[activeIndex] : null;

  return (
    <div className={`relative w-full ${className}`}>
      <svg
        viewBox={`0 0 ${width} ${chartHeight}`}
        className="w-full"
        style={{ height }}
        preserveAspectRatio="none"
        onMouseLeave={() => setHoverIndex(null)}
        onMouseMove={(event) => {
          const rect = event.currentTarget.getBoundingClientRect();
          if (!rect.width) return;
          const relativeX = clamp((event.clientX - rect.left) / rect.width, 0, 1);
          const nextIndex = Math.round(relativeX * Math.max(points.length - 1, 0));
          setHoverIndex(nextIndex);
        }}
      >
        <defs>
          <linearGradient id="simple-area-gradient" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor={color} stopOpacity="0.28" />
            <stop offset="95%" stopColor={color} stopOpacity="0.03" />
          </linearGradient>
        </defs>

        {showGrid && [0.2, 0.4, 0.6, 0.8].map((fraction) => {
          const y = margin.top + innerHeight * fraction;
          return (
            <line
              key={fraction}
              x1={margin.left}
              x2={width - margin.right}
              y1={y}
              y2={y}
              stroke="#1f2937"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
          );
        })}

        <path d={areaPath} fill="url(#simple-area-gradient)" />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {activePoint ? (
          <>
            <line
              x1={activePoint.x}
              x2={activePoint.x}
              y1={margin.top}
              y2={chartHeight - margin.bottom}
              stroke="#6b7280"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
            <circle cx={activePoint.x} cy={activePoint.y} r="4" fill={color} stroke="#0b1220" strokeWidth="2" />
          </>
        ) : null}
      </svg>

      {activePoint ? (
        <div className="pointer-events-none absolute right-2 top-2 rounded-lg border border-gray-700 bg-gray-800/95 px-2 py-1 text-xs shadow-lg">
          <div className="text-gray-400">{formatLabel ? formatLabel(activePoint.label) : String(activePoint.label ?? '')}</div>
          <div className="font-bold text-white">{formatValue ? formatValue(activePoint.value) : String(activePoint.value)}</div>
        </div>
      ) : null}
    </div>
  );
}

export default SimpleAreaChart;
