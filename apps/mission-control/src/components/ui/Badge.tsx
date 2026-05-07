export function Badge({ children, color = 'accent' }: { children: React.ReactNode; color?: 'ok' | 'bad' | 'warn' | 'accent' | 'muted' }) {
  const map: Record<string, string> = {
    ok: 'bg-green-500/15 text-green-400 border-green-500/25',
    bad: 'bg-red-500/15 text-red-400 border-red-500/25',
    warn: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
    accent: 'bg-violet-500/15 text-violet-400 border-violet-500/25',
    muted: 'bg-[#1e293b] text-muted border-[#1e293b]',
  };
  return (
    <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium ${map[color]}`}>
      {children}
    </span>
  );
}
