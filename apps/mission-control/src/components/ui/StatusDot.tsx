export function StatusDot({ ok, size = 'md', pulse = true }: { ok: boolean; size?: 'sm'|'md'|'lg'; pulse?: boolean }) {
  const s = size === 'sm' ? 'w-1.5 h-1.5' : size === 'lg' ? 'w-3 h-3' : 'w-2 h-2';
  const color = ok ? 'bg-emerald-400' : 'bg-rose-400';
  const glow = ok ? 'shadow-[0_0_10px_rgba(52,211,153,0.5)]' : 'shadow-[0_0_10px_rgba(251,113,133,0.5)]';
  return (
    <span className={`inline-block rounded-full ${s} ${color} ${pulse ? glow : ''} ${pulse && ok ? 'animate-pulse' : ''}`} />
  );
}
