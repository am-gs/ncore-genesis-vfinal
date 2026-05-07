export function Card({ children, className }: { children?: React.ReactNode; className?: string }) {
  return (
    <div className={`rounded-lg border border-[var(--color-line)] bg-[var(--color-panel)] ${className || ''}`}>
      {children}
    </div>
  );
}
export function CardHeader({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <div className={`px-4 pt-4 ${className || ''}`}>{children}</div>;
}
export function CardTitle({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <h3 className={`text-sm font-semibold text-text ${className || ''}`}>{children}</h3>;
}
export function CardContent({ children, className }: { children?: React.ReactNode; className?: string }) {
  return <div className={`px-4 pb-4 ${className || ''}`}>{children}</div>;
}
