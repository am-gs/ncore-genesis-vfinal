export function StatusDot({ ok, size = 'md' }: { ok: boolean; size?: 'sm' | 'md' | 'lg' }) {
  const s = size === 'sm' ? 'w-2 h-2' : size === 'lg' ? 'w-4 h-4' : 'w-2.5 h-2.5';
  return (
    <span className={`inline-block rounded-full ${s} ${ok ? 'bg-[var(--color-ok)] shadow-[0_0_8px_rgba(34,197,94,0.4)]' : 'bg-[var(--color-bad)] shadow-[0_0_8px_rgba(239,68,68,0.4)]'}`} />
  );
}
