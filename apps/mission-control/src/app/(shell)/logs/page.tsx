'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { fetchLogs } from '@/lib/api';
import { useAppStore } from '@/stores/app-store';
import { Copy, RotateCcw, ScrollText } from 'lucide-react';

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
    try { setContent(await fetchLogs(activeLog)); }
    catch (e) { setContent(e instanceof Error ? e.message : 'Failed'); }
    finally { setLoading(false); }
  }, [activeLog]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScrollText className="h-5 w-5 text-accent" />
          <h2 className="text-sm font-semibold text-text tracking-tight">System Logs</h2>
        </div>
        <div className="flex gap-2">
          <button onClick={() => navigator.clipboard.writeText(content)} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
            <Copy className="h-3.5 w-3.5" /> Copy
          </button>
          <button onClick={load} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
            <RotateCcw className="h-3.5 w-3.5" /> Refresh
          </button>
        </div>
      </div>
      <div className="flex gap-1">
        {logTabs.map(tab => (
          <button key={tab.key} onClick={() => setActiveLog(tab.key)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${activeLog===tab.key?'bg-gradient-to-r from-violet-500/15 to-indigo-500/10 text-violet-300 border border-violet-500/20':'text-muted hover:text-text hover:bg-white/[0.03]'}`}
          >{tab.label}</button>
        ))}
      </div>
      <Card glow>
        <CardContent className="p-0">
          {loading ? (
            <div className="p-4 space-y-2">
              {Array.from({length:12}).map((_,i)=>(<div key={i} className="h-3 animate-pulse rounded bg-white/[0.03]"/>))}
            </div>
          ) : (
            <pre className="max-h-[70vh] overflow-auto p-4 text-[11px] font-mono leading-relaxed text-text-secondary/80 whitespace-pre-wrap">
              {content || <span className="text-muted italic">No logs available</span>}
            </pre>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
