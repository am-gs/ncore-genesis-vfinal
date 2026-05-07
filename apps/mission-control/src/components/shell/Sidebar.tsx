'use client';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { useAppStore } from '@/stores/app-store';
import {
  LayoutDashboard, Activity, Table, ScrollText, Shield, Bot, Brain,
  GitBranch, Settings, ChevronLeft, ChevronRight, Zap
} from 'lucide-react';

const items = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/services', label: 'Services', icon: Activity },
  { href: '/runs', label: 'Runs', icon: Table },
  { href: '/logs', label: 'Logs', icon: ScrollText },
  { href: '/bifrost', label: 'Bifrost', icon: Shield },
  { href: '/deerflow', label: 'DeerFlow', icon: Bot },
  { href: '/mem0', label: 'Mem0', icon: Brain },
  { href: '/workflow', label: 'Workflow', icon: GitBranch },
  { href: '/settings', label: 'Settings', icon: Settings },
];

export default function Sidebar() {
  const collapsed = useAppStore((s) => s.sidebarCollapsed);
  const toggle = useAppStore((s) => s.toggleSidebar);
  const pathname = usePathname();

  return (
    <aside className={`flex flex-col border-r border-line bg-panel transition-[width] duration-300 ${collapsed ? 'w-16' : 'w-56'}`}>
      <div className="flex items-center gap-3 px-4 h-14 border-b border-line">
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-violet-600 to-indigo-600">
          <Zap className="h-4 w-4 text-white" />
        </div>
        {!collapsed && (
          <div className="overflow-hidden">
            <div className="font-display text-sm font-bold text-text truncate">Sovereign</div>
            <div className="text-[10px] uppercase tracking-wider text-muted">Mission Control</div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-2">
        {items.map((item) => {
          const active = item.href === '/' ? pathname === '/' : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 mx-2 px-3 py-2 rounded-md text-sm transition-colors ${
                active ? 'bg-accent/10 text-accent' : 'text-muted hover:bg-panel-2 hover:text-text'
              }`}
              title={collapsed ? item.label : undefined}
            >
              <item.icon className="h-4 w-4 shrink-0" />
              {!collapsed && <span className="truncate">{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <div className="border-t border-line p-3">
        <button onClick={toggle} className="flex w-full items-center justify-center rounded-md p-1.5 text-muted hover:bg-panel-2 hover:text-text transition-colors">
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
        {!collapsed && <div className="mt-2 text-[10px] text-muted text-center">v1.0.0-beta</div>}
      </div>
    </aside>
  );
}
