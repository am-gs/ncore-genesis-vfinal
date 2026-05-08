'use client';

import { Globe, Loader2 } from 'lucide-react';

export function BrowserView({ url }: { url: string }) {
  return (
    <div className="h-full flex flex-col bg-bg">
      {/* Browser Chrome */}
      <div className="flex items-center gap-2 px-3 py-2 bg-panel border-b border-line">
        <div className="flex items-center gap-1.5">
          <div className="w-2.5 h-2.5 rounded-full bg-bad" />
          <div className="w-2.5 h-2.5 rounded-full bg-warn" />
          <div className="w-2.5 h-2.5 rounded-full bg-ok" />
        </div>
        <div className="flex-1 flex items-center gap-2 bg-bg-2 rounded-md px-3 py-1.5 mx-2">
          <Globe className="h-3 w-3 text-text-tertiary" />
          <span className="text-xs text-text-secondary truncate">
            {url || 'about:blank'}
          </span>
        </div>
      </div>

      {/* Viewport */}
      <div className="flex-1 relative">
        {url ? (
          <iframe
            src={url}
            className="w-full h-full border-0"
            sandbox="allow-scripts allow-same-origin allow-popups"
            title="Browser View"
          />
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
            <Globe className="h-12 w-12 mb-3 opacity-20" />
            <p className="text-sm">No active browser session</p>
            <p className="text-xs mt-1">Browser automation will appear here</p>
          </div>
        )}
      </div>
    </div>
  );
}
