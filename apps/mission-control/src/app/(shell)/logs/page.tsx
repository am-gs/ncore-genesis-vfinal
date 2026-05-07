'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { fetchLogs } from '@/lib/api';
import { useAppStore } from '@/stores/app-store';
import { Copy, RotateCcw, FileText } from 'lucide-react';

const logTabs = [
  { key: 'watchdog', label: 'Watchdog' },
  { key: 'bifrost', label: 'Bifrost' },
  { key: 'regression', label: 'Regression' },
];

export default function LogsPage() {
  const activeLog = useAppStore((s) => s.activeLog);
  const setActiveLog = useAppStore((s) => s.setActiveLog);
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const text = await fetchLogs(activeLog);
      setContent(text);
    } catch (e) {
      setContent(e instanceof Error ? e.message : 'Failed to load logs');
    } finally {
      setLoading(false);
    }
  }, [activeLog]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex gap-1">
          {logTabs.map((tab) => (
            <button
              key={tab.key}
              onClick={() => setActiveLog(tab.key)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                activeLog === tab.key ? 'bg-accent/15 text-accent' : 'text-muted hover:text-text hover:bg-panel-2'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => navigator.clipboard.writeText(content)}><Copy className="h-4 w-4 mr-1" /> Copy</Button>
          <Button variant="ghost" onClick={load}><RotateCcw className="h-4 w-4 mr-1" /> Refresh</Button>
        </div>
      </div>
      <Card>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="h-3 animate-pulse rounded bg-panel-2" />
              ))}
            </div>
          ) : (
            <pre className="max-h-[70vh] overflow-auto p-4 text-xs font-mono leading-relaxed text-text-secondary whitespace-pre-wrap">
              {content || <span className="text-muted italic">No logs available</span>}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
