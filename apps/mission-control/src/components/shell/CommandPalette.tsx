'use client';
import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useAppStore } from '@/stores/app-store';
import {
  LayoutDashboard, Activity, Table, ScrollText, Shield, Bot, Brain,
  GitBranch, Settings, RefreshCw, Copy, X
} from 'lucide-react';

const commands = [
  { id: 'dash', label: 'Go to Dashboard', icon: LayoutDashboard, href: '/' },
  { id: 'svc', label: 'Go to Services', icon: Activity, href: '/services' },
  { id: 'runs', label: 'Go to Runs', icon: Table, href: '/runs' },
  { id: 'logs', label: 'Go to Logs', icon: ScrollText, href: '/logs' },
  { id: 'bifrost', label: 'Go to Bifrost', icon: Shield, href: '/bifrost' },
  { id: 'deer', label: 'Go to DeerFlow', icon: Bot, href: '/deerflow' },
  { id: 'mem0', label: 'Go to Mem0', icon: Brain, href: '/mem0' },
  { id: 'wf', label: 'Go to Workflow', icon: GitBranch, href: '/workflow' },
  { id: 'settings', label: 'Go to Settings', icon: Settings, href: '/settings' },
  { id: 'refresh', label: 'Refresh all data', icon: RefreshCw, action: () => window.location.reload() },
  { id: 'copy', label: 'Copy page URL', icon: Copy, action: () => navigator.clipboard.writeText(window.location.href) },
];

export default function CommandPalette() {
  const open = useAppStore((s) => s.commandOpen);
  const setOpen = useAppStore((s) => s.setCommandOpen);
  const [query, setQuery] = useState('');
  const [idx, setIdx] = useState(0);
  const router = useRouter();

  const filtered = commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()));

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(!open);
      }
      if (e.key === 'Escape') setOpen(false);
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, setOpen]);

  useEffect(() => setIdx(0), [query]);

  const run = useCallback((cmd: typeof commands[0]) => {
    setOpen(false);
    setQuery('');
    if (cmd.href) router.push(cmd.href);
    else if (cmd.action) cmd.action();
  }, [router, setOpen]);

  const onKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setIdx((i) => Math.min(i + 1, filtered.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setIdx((i) => Math.max(i - 1, 0)); }
    if (e.key === 'Enter' && filtered[idx]) run(filtered[idx]);
  }, [filtered, idx, run]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]" onClick={() => setOpen(false)}>
      <div className="w-full max-w-lg rounded-xl border border-line bg-panel shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-2 border-b border-line px-4 py-3">
          <SearchIcon />
          <input
            autoFocus
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Type a command..."
            className="flex-1 bg-transparent text-sm text-text placeholder-muted outline-none"
          />
          <button onClick={() => setOpen(false)} className="text-muted hover:text-text"><X className="h-4 w-4" /></button>
        </div>
        <div className="max-h-80 overflow-y-auto py-2">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              onClick={() => run(cmd)}
              onMouseEnter={() => setIdx(i)}
              className={`flex w-full items-center gap-3 px-4 py-2.5 text-sm transition-colors ${
                i === idx ? 'bg-accent/10 text-accent' : 'text-muted hover:text-text hover:bg-panel-2'
              }`}
            >
              <cmd.icon className="h-4 w-4" />
              {cmd.label}
            </button>
          ))}
          {filtered.length === 0 && <div className="px-4 py-6 text-center text-sm text-muted">No commands found</div>}
        </div>
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg className="h-4 w-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
    </svg>
  );
}
