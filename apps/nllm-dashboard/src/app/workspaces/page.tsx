// Workspaces page

'use client';

import { FileBrowser } from '@/app/components/file-browser';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';

export default function WorkspacesPage() {
  return (
    <div className="h-full flex flex-col">
      <div className="p-4 border-b border-line">
        <h1 className="text-2xl font-bold">Workspaces</h1>
        <p className="text-text-secondary">Browse and manage your workspace files</p>
      </div>
      
      <div className="flex-1 overflow-auto p-4">
        <Card className="h-full">
          <CardContent className="p-0 h-full">
            <FileBrowser />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
