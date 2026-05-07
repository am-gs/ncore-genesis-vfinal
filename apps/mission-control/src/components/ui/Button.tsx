export function Button({ children, onClick, variant = 'primary', className, disabled }: {
  children: React.ReactNode; onClick?: () => void; variant?: 'primary'|'ghost'|'danger'|'glass'; className?: string; disabled?: boolean;
}) {
  const base = 'inline-flex items-center justify-center rounded-lg px-3 py-2 text-xs font-semibold transition-all duration-200';
  const styles = {
    primary: 'bg-gradient-to-r from-violet-600 to-indigo-600 text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 hover:scale-[1.02] active:scale-[0.98]',
    ghost: 'text-muted hover:text-text hover:bg-white/5',
    danger: 'bg-rose-500/10 text-rose-400 hover:bg-rose-500/20',
    glass: 'bg-white/5 border border-white/10 text-text backdrop-blur-md hover:bg-white/10',
  };
  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${styles[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className || ''}`}>
      {children}
    </button>
  );
}
