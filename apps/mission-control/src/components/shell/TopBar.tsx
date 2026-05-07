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
    <header className="flex items-center justify-between h-16 px-6 border-b border-white/[0.06] bg-[rgba(10,15,28,0.6)] backdrop-blur-2xl z-10">
      <h1 className="text-sm font-semibold text-text tracking-tight">{titles[pathname] || 'Mission Control'}</h1>
      <div className="flex items-center gap-3">
        <button
          onClick={() => openCmd(true)}
          className="flex items-center gap-2 rounded-xl border border-white/[0.08] bg-white/[0.03] backdrop-blur-md px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] hover:border-white/[0.12] transition-all"
        >
          <Search className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Command</span>
          <kbd className="hidden sm:inline-flex ml-1 rounded-md bg-white/[0.06] px-1.5 py-0.5 text-[10px] font-mono border border-white/[0.08]">⌘K</kbd>
        </button>
        <button className="relative rounded-xl p-2.5 text-muted hover:text-text hover:bg-white/[0.04] transition-all border border-transparent hover:border-white/[0.08]">
          <Bell className="h-4 w-4" />
          <span className="absolute right-2 top-2 h-1.5 w-1.5 rounded-full bg-gradient-to-r from-violet-400 to-cyan-400 shadow-[0_0_8px_rgba(139,92,246,0.6)]" />
        </button>
      </div>
    </header>
  );
}
