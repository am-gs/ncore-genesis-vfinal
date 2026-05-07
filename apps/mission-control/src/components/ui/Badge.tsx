export function Badge({ children, color = 'accent', className }: { children: React.ReactNode; color?: 'ok'|'bad'|'warn'|'accent'|'cyan'|'muted'; className?: string }) {
  const map: Record<string, string> = {
    ok: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    bad: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
    warn: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    accent: 'bg-violet-500/10 text-violet-400 border-violet-500/20',
    cyan: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    muted: 'bg-white/5 text-muted border-white/10',
  };
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium tracking-wide uppercase ${map[color]} ${className || ''}`}>
      {children}
    </span>
  );
}
