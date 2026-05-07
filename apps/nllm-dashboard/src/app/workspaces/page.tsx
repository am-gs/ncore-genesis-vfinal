     1	// Workspaces page
     2	
     3	'use client';
     4	
     5	import { FileBrowser } from '@/app/components/file-browser';
     6	import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
     7	
     8	export default function WorkspacesPage() {
     9	  return (
    10	    <div className="h-full flex flex-col">
    11	      <div className="p-4 border-b border-line">
    12	        <h1 className="text-2xl font-bold">Workspaces</h1>
    13	        <p className="text-text-secondary">Browse and manage your workspace files</p>
    14	      </div>
    15	      
    16	      <div className="flex-1 overflow-auto p-4">
    17	        <Card className="h-full">
    18	          <CardContent className="p-0 h-full">
    19	            <FileBrowser />
    20	          </CardContent>
    21	        </Card>
    22	      </div>
    23	    </div>
    24	  );
    25	}