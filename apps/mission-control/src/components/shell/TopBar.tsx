'use client';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/stores/app-store';
import { Bell, Search } from 'lucide-react';

const titles: Record<string, string> = {
  '/': 'Dashboard',
  '/services': 'Services',
  '/runs': 'Task Runs',
  '/logs': 'System Logs',
  '/bifrost': 'Bifrost Gateway',
  '/deerflow': 'DeerFlow Chat',
  '/mem0': 'Mem0 Memory',
  '/workflow': 'Workflow Builder',
  '/settings': 'Settings',
};

export default function TopBar() {
  const pathname = usePathname();
  const openCmd = useAppStore((s) => s.setCommandOpen);

  return (
    <header className="flex items-center justify-between h-14 px-6 border-b border-line bg-panel">
      <h1 className="text-sm font-semibold text-text">{titles[pathname] || 'Mission Control'}</h1>
      <div className="flex items-center gap-2">
        <button
          onClick={() => openCmd(true)}
          className="flex items-center gap-2 rounded-md border border-line bg-panel-2 px-3 py-1.5 text-xs text-muted hover:text-text transition-colors"
        >
          <Search className="h-3.5 w-3.5" />
          <span>Command</span>
          <kbd className="ml-1 rounded bg-panel-3 px-1.5 py-0.5 text-[10px] font-mono">⌘K</kbd>
        </button>
        <button className="relative rounded-md p-2 text-muted hover:text-text hover:bg-panel-2 transition-colors">
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-accent" />
        </button>
      </div>
    </header>
  );
}
