'use client';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { fetchRuns } from '@/lib/api';
import type { Run } from '@/types';
import { Download, ChevronUp, ChevronDown, Table2 } from 'lucide-react';

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortCol, setSortCol] = useState<keyof Run>('ts');
  const [sortDesc, setSortDesc] = useState(true);

  const load = useCallback(async () => { try { const r = await fetchRuns(200); setRuns(r.runs || []); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const sorted = useMemo(() => [...runs].sort((a, b) => {
    const av = a[sortCol] ?? 0; const bv = b[sortCol] ?? 0;
    if (typeof av === 'number' && typeof bv === 'number') return sortDesc ? bv - av : av - bv;
    return sortDesc ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
  }), [runs, sortCol, sortDesc]);

  const exportCSV = () => {
    const header = 'Time,Task,Provider,Model,Fallback,Latency,Status,Refusal\n';
    const rows = runs.map(r => `${new Date(r.ts*1000).toISOString()},${r.task_id},${r.provider},${r.model},${r.fallback_reason},${r.latency_ms},${r.completion_status},${r.refusal_intercepted}`).join('\n');
    const blob = new Blob([header+rows], {type:'text/csv'});
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `runs-${Date.now()}.csv`; a.click();
  };

  const toggleSort = (col: keyof Run) => { if (sortCol === col) setSortDesc(!sortDesc); else { setSortCol(col); setSortDesc(true); } };
  const SortIcon = ({ col }: { col: keyof Run }) => sortCol !== col ? <span className="ml-1 text-muted/30">⇅</span> : sortDesc ? <ChevronDown className="ml-1 h-3 w-3" /> : <ChevronUp className="ml-1 h-3 w-3" />;

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Table2 className="h-5 w-5 text-accent" />
          <h2 className="text-sm font-semibold text-text tracking-tight">Task Runs</h2>
          <Badge color="muted">{runs.length} records</Badge>
        </div>
        <div className="flex gap-2">
          <button onClick={load} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
            <RotateCcw className="h-3.5 w-3.5" /> Refresh
          </button>
          <button onClick={exportCSV} className="inline-flex items-center gap-1 rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-3 py-2 text-xs text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all">
            <Download className="h-3.5 w-3.5" /> Export CSV
          </button>
        </div>
      </div>
      <Card glow>
        <CardContent className="pt-5">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.06] text-left text-[11px] text-muted uppercase tracking-wider">
                  <th className="pb-3 pr-4 cursor-pointer hover:text-text transition-colors" onClick={() => toggleSort('ts')}>Time<SortIcon col="ts"/></th>
                  <th className="pb-3 pr-4 cursor-pointer hover:text-text transition-colors" onClick={() => toggleSort('task_id')}>Task<SortIcon col="task_id"/></th>
                  <th className="pb-3 pr-4 cursor-pointer hover:text-text transition-colors" onClick={() => toggleSort('provider')}>Provider<SortIcon col="provider"/></th>
                  <th className="pb-3 pr-4 cursor-pointer hover:text-text transition-colors" onClick={() => toggleSort('model')}>Model<SortIcon col="model"/></th>
                  <th className="pb-3 pr-4">Fallback</th>
                  <th className="pb-3 pr-4 cursor-pointer hover:text-text transition-colors" onClick={() => toggleSort('latency_ms')}>Latency<SortIcon col="latency_ms"/></th>
                  <th className="pb-3 pr-4">Status</th>
                  <th className="pb-3">Refusal</th>
                </tr>
              </thead>
              <tbody>
                {loading ? Array.from({length:8}).map((_,i)=>(
                  <tr key={i}><td colSpan={8} className="py-3"><div className="h-4 animate-pulse rounded bg-white/[0.03]"/></td></tr>
                )) : sorted.map(run => (
                  <tr key={`${run.ts}-${run.task_id}`} className="border-b border-white/[0.03] transition-colors hover:bg-white/[0.02]">
                    <td className="py-3 pr-4 font-mono text-xs text-muted">{new Date(run.ts*1000).toLocaleString()}</td>
                    <td className="py-3 pr-4 text-xs">{run.task_id}</td>
                    <td className="py-3 pr-4"><Badge color={run.provider==='remote'?'accent':run.provider==='policy'?'warn':'muted'}>{run.provider}</Badge></td>
                    <td className="py-3 pr-4 font-mono text-xs text-muted">{run.model}</td>
                    <td className="py-3 pr-4 text-xs text-muted">{run.fallback_reason!=='none'?run.fallback_reason:'—'}</td>
                    <td className="py-3 pr-4 text-xs font-mono">{run.latency_ms}ms</td>
                    <td className="py-3 pr-4"><Badge color={run.completion_status==='completed'?'ok':run.completion_status==='refused'?'warn':'bad'}>{run.completion_status}</Badge></td>
                    <td className="py-3">{run.refusal_intercepted?<Badge color="warn">Yes</Badge>:'—'}</td>
                  </tr>
                ))}
                {!loading && runs.length===0 && <tr><td colSpan={8} className="py-10 text-center text-muted text-sm">No runs recorded</td></tr>}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function RotateCcw(props: React.SVGProps<SVGSVGElement>) {
  return <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" {...props}><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"/><path d="M3 3v5h5"/></svg>;
}
