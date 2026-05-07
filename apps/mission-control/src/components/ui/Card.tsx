export function Card({ children, className, glow = false }: { children?: React.ReactNode; className?: string; glow?: boolean }) {
  return (
    <div className={`rounded-xl ${glow ? 'glow-border' : 'border border-white/[0.06]'} bg-[rgba(15,23,42,0.55)] backdrop-blur-xl ${className || ''}`}>
      {children}
    </div>
  );
}
export function CardHeader({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <div className={`px-5 pt-5 ${className || ''}`}>{children}</div>;
}
export function CardTitle({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <h3 className={`text-sm font-semibold text-text tracking-tight ${className || ''}`}>{children}</h3>;
}
export function CardContent({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <div className={`px-5 pb-5 ${className || ''}`}>{children}</div>;
}
