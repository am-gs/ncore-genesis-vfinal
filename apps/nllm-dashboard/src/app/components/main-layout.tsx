     1	// Main layout with navigation
     2	
     3	'use client';
     4	
     5	import { Navigation } from '@/app/components/navigation';
     6	import { 
     7	  FileText, 
     8	  BarChart3, 
     9	  Settings,
    10	  Play,
    11	  Folder,
    12	  Circle,
    13	  CheckCircle,
    14	  AlertCircle,
    15	  Clock
    16	} from 'lucide-react';
    17	import { useWebSocket } from '@/app/contexts/websocket';
    18	import { Badge } from '@/app/components/ui/badge';
    19	
    20	export default function MainLayout({
    21	  children,
    22	}: {
    23	  children: React.ReactNode;
    24	}) {
    25	  const { isConnected } = useWebSocket();
    26	  
    27	  return (
    28	    <div className="flex h-full bg-bg">
    29	      {/* Sidebar */}
    30	      <div className="w-64 bg-panel border-r border-line flex flex-col">
    31	        <div className="p-4 border-b border-line">
    32	          <h1 className="text-xl font-display font-bold text-gradient">NLLM.ING</h1>
    33	          <p className="text-xs text-text-secondary mt-1">Never-Refusing AI. Costs Pennies.</p>
    34	        </div>
    35	        
    36	        <div className="flex-1 flex flex-col">
    37	          <Navigation />
    38	        </div>
    39	        
    40	        <div className="p-4 border-t border-line">
    41	          <div className="flex items-center justify-between">
    42	            <span className="text-sm text-text-secondary">Status</span>
    43	            <Badge variant={isConnected ? "default" : "destructive"}>
    44	              {isConnected ? 'Connected' : 'Disconnected'}
    45	            </Badge>
    46	          </div>
    47	        </div>
    48	      </div>
    49	      
    50	      {/* Main Content */}
    51	      <div className="flex-1 flex flex-col">
    52	        {children}
    53	      </div>
    54	    </div>
    55	  );
    56	}