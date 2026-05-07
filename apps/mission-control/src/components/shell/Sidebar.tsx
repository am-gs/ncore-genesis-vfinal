'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/stores/app-store';
import {
  LayoutDashboard, Activity, Table, ScrollText, Shield, Bot, Brain,
  GitBranch, Settings, ChevronLeft, ChevronRight, Zap, Code, Workflow,
  Cpu
} from 'lucide-react';

const items = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/tasks/', label: 'Tasks', icon: GitBranch },
  { href: '/deep-agents/', label: 'Deep Agents', icon: Cpu },
  { href: '/workspace/', label: 'Workspace', icon: Code },
  { href: '/services/', label: 'Services', icon: Activity },
  { href: '/runs/', label: 'Runs', icon: Table },
  { href: '/logs/', label: 'Logs', icon: ScrollText },
  { href: '/bifrost/', label: 'Bifrost', icon: Shield },
  { href: '/deerflow/', label: 'DeerFlow', icon: Bot },
  { href: '/mem0/', label: 'Mem0', icon: Brain },
  { href: '/workflow/', label: 'Workflow', icon: Workflow },
  { href: '/settings/', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggle = useAppStore((s) => s.toggleSidebar);
  const pathname = usePathname();

  return (
    <aside className={`flex flex-col border-r border-white/[0.06] bg-[rgba(10,15,28,0.8)] backdrop-blur-2xl transition-[width] duration-300 z-20 ${collapsed ? 'w-16' : 'w-60'}`}>
      <div className="flex items-center gap-3 px-4 h-16 border-b border-white/[0.06]">
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 via-indigo-600 to-cyan-500 shadow-lg shadow-violet-500/20">
          <Zap className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <div className="text-[15px] font-bold text-gradient truncate tracking-tight">Sovereign</div>
            <div className="text-[10px] uppercase tracking-[0.12em] text-muted font-medium">Mission Control</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3">
        {items.map((item) => {
          const active = item.href === '/' ? pathname === '/' || pathname === '' : pathname.startsWith(item.href.replace(/\/$/, ''));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 mx-2 px-3 py-2.5 rounded-xl text-[13px] font-medium transition-all duration-200 ${
                active
                  ? 'bg-gradient-to-r from-violet-500/15 to-indigo-500/10 text-violet-300 border border-violet-500/20'
                  : 'text-muted hover:bg-white/[0.04] hover:text-text'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-[18px] w-[18px] shrink-0" strokeWidth={active ? 2.5 : 1.5} />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-white/[0.06] p-3">
        <button onClick={toggle} className="flex w-full items-center justify-center rounded-lg p-2 text-muted hover:bg-white/[0.04] hover:text-text transition-all">
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
        {!collapsed && <div className="mt-2 text-[10px] text-muted/60 text-center tracking-wider">v1.0.0-beta</div>}
      </div>
    </aside>
  );
}
