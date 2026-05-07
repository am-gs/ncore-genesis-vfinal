     1	// Navigation component
     2	
     3	'use client';
     4	
     5	import Link from 'next/link';
     6	import { usePathname } from 'next/navigation';
     7	import { 
     8	  FileText, 
     9	  BarChart3, 
    10	  Settings,
    11	  Play,
    12	  Folder
    13	} from 'lucide-react';
    14	import { cn } from '@/app/lib/utils';
    15	
    16	const navigation = [
    17	  { name: 'Dashboard', href: '/', icon: Play },
    18	  { name: 'Sessions', href: '/sessions', icon: FileText },
    19	  { name: 'Workspaces', href: '/workspaces', icon: Folder },
    20	  { name: 'Analytics', href: '/analytics', icon: BarChart3 },
    21	  { name: 'Settings', href: '/settings', icon: Settings },
    22	];
    23	
    24	export function Navigation() {
    25	  const pathname = usePathname();
    26	  
    27	  return (
    28	    <nav className="flex-1 space-y-1 px-2">
    29	      {navigation.map((item) => {
    30	        const isActive = pathname === item.href;
    31	        return (
    32	          <Link
    33	            key={item.name}
    34	            href={item.href}
    35	            className={cn(
    36	              'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
    37	              isActive 
    38	                ? 'bg-panel-3 text-text' 
    39	                : 'text-text-secondary hover:bg-panel-2 hover:text-text'
    40	            )}
    41	          >
    42	            <item.icon className="h-4 w-4" />
    43	            {item.name}
    44	          </Link>
    45	        );
    46	      })}
    47	    </nav>
    48	  );
    49	}