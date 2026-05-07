export function Button({ children, onClick, variant = 'primary', className, disabled }: {
  children: React.ReactNode; onClick?: () => void; variant?: 'primary' | 'ghost' | 'danger'; className?: string; disabled?: boolean;
}) {
  const base = 'inline-flex items-center justify-center rounded-md px-3 py-1.5 text-sm font-medium transition-colors';
  const styles = {
    primary: 'bg-accent text-white hover:bg-accent/80',
    ghost: 'text-muted hover:text-text hover:bg-panel-2',
    danger: 'bg-red-500/15 text-red-400 hover:bg-red-500/25',
  };
  return (
    <button onClick={onClick} disabled={disabled} className={`${base} ${styles[variant]} ${disabled ? 'opacity-50 cursor-not-allowed' : ''} ${className || ''}`}>
      {children}
    </button>
  );
}
