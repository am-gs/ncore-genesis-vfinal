export function Sparkline({ data, color = '#8b5cf6', height = 40 }: { data: number[]; color?: string; height?: number }) {
  if (!data.length) return <div style={{ height }} className="flex items-center justify-center text-xs text-muted">No data</div>;
  const max = Math.max(...data, 1);
  const w = 200;
  const h = height;
  const points = data.map((v, i) => `${(i / Math.max(data.length - 1, 1)) * w},${h - (v / max) * h * 0.85 - 2}`).join(' ');
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" style={{ height }}>
      <defs>
        <linearGradient id="spark" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.3" />
          <stop offset="100%" stopColor={color} stopOpacity="0.02" />
        </linearGradient>
      </defs>
      <polygon points={`0,${h} ${points} ${w},${h}`} fill="url(#spark)" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={w} cy={h - (data[data.length-1] / max) * h * 0.85 - 2} r="2.5" fill={color} />
    </svg>
  );
}
