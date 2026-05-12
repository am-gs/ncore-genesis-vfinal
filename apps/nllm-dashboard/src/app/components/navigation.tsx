// Navigation component

'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { 
  FileText, 
  BarChart3, 
  Settings,
  Play,
  Folder,
  Network
} from 'lucide-react';
import { cn } from '@/app/lib/utils';

const navigation = [
  { name: 'Dashboard', href: '/', icon: Play },
  { name: 'Swarm', href: '/swarm', icon: Network },
  { name: 'Sessions', href: '/sessions', icon: FileText },
  { name: 'Workspaces', href: '/workspaces', icon: Folder },
  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Navigation() {
  const pathname = usePathname();
  
  return (
    <nav className="flex-1 space-y-1 px-2">
      {navigation.map((item) => {
        const isActive = pathname === item.href;
        return (
          <Link
            key={item.name}
            href={item.href}
            className={cn(
              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
              isActive 
                ? 'bg-panel-3 text-text' 
                : 'text-text-secondary hover:bg-panel-2 hover:text-text'
            )}
          >
            <item.icon className="h-4 w-4" />
            {item.name}
          </Link>
        );
      })}
    </nav>
  );
}
