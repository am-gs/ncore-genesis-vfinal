'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { fetchRuns } from '@/lib/api';
import type { Run } from '@/types';
import { Download, ChevronUp, ChevronDown } from 'lucide-react';

export default function RunsPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [sortCol, setSortCol] = useState<keyof Run>('ts');
  const [sortDesc, setSortDesc] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetchRuns(200);
      setRuns(r.runs || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const sorted = [...runs].sort((a, b) => {
    const av = a[sortCol] ?? 0;
    const bv = b[sortCol] ?? 0;
    if (typeof av === 'number' && typeof bv === 'number') return sortDesc ? bv - av : av - bv;
    return sortDesc ? String(bv).localeCompare(String(av)) : String(av).localeCompare(String(bv));
  });

  const exportCSV = () => {
    const header = 'Time,Task,Provider,Model,Fallback,Latency,Status,Refusal\n';
    const rows = runs.map((r) =>
      `${new Date(r.ts * 1000).toISOString()},${r.task_id},${r.provider},${r.model},${r.fallback_reason},${r.latency_ms},${r.completion_status},${r.refusal_intercepted}`
    ).join('\n');
    const blob = new Blob([header + rows], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `runs-${Date.now()}.csv`;
    a.click();
  };

  const toggleSort = (col: keyof Run) => {
    if (sortCol === col) setSortDesc(!sortDesc);
    else { setSortCol(col); setSortDesc(true); }
  };

  const SortIcon = ({ col }: { col: keyof Run }) => {
    if (sortCol !== col) return <span className="ml-1 text-muted/50">⇅</span>;
    return sortDesc ? <ChevronDown className="ml-1 h-3 w-3" /> : <ChevronUp className="ml-1 h-3 w-3" />;
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text">Task Runs ({runs.length})</h2>
        <div className="flex gap-2">
          <Button onClick={load} variant="ghost">Refresh</Button>
          <Button onClick={exportCSV} variant="primary"><Download className="h-4 w-4 mr-1" /> Export CSV</Button>
        </div>
      </div>
      <Card>
        <CardContent className="pt-4">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted uppercase tracking-wider">
                  <th className="pb-2 pr-4 cursor-pointer hover:text-text" onClick={() => toggleSort('ts')}>Time<SortIcon col="ts" /></th>
                  <th className="pb-2 pr-4 cursor-pointer hover:text-text" onClick={() => toggleSort('task_id')}>Task<SortIcon col="task_id" /></th>
                  <th className="pb-2 pr-4 cursor-pointer hover:text-text" onClick={() => toggleSort('provider')}>Provider<SortIcon col="provider" /></th>
                  <th className="pb-2 pr-4 cursor-pointer hover:text-text" onClick={() => toggleSort('model')}>Model<SortIcon col="model" /></th>
                  <th className="pb-2 pr-4">Fallback</th>
                  <th className="pb-2 pr-4 cursor-pointer hover:text-text" onClick={() => toggleSort('latency_ms')}>Latency<SortIcon col="latency_ms" /></th>
                  <th className="pb-2 pr-4">Status</th>
                  <th className="pb-2">Refusal</th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 8 }).map((_, i) => (
                    <tr key={i}><td colSpan={8} className="py-3"><div className="h-4 animate-pulse rounded bg-panel-2" /></td></tr>
                  ))
                ) : sorted.map((run) => (
                  <tr key={`${run.ts}-${run.task_id}`} className="border-b border-line/50">
                    <td className="py-2 pr-4 font-mono text-xs text-muted">{new Date(run.ts * 1000).toLocaleString()}</td>
                    <td className="py-2 pr-4 text-xs">{run.task_id}</td>
                    <td className="py-2 pr-4"><Badge color={run.provider === 'remote' ? 'accent' : 'muted'}>{run.provider}</Badge></td>
                    <td className="py-2 pr-4 font-mono text-xs text-muted">{run.model}</td>
                    <td className="py-2 pr-4 text-xs text-muted">{run.fallback_reason !== 'none' ? run.fallback_reason : '—'}</td>
                    <td className="py-2 pr-4 text-xs">{run.latency_ms}ms</td>
                    <td className="py-2 pr-4"><Badge color={run.completion_status === 'completed' ? 'ok' : run.completion_status === 'refused' ? 'warn' : 'bad'}>{run.completion_status}</Badge></td>
                    <td className="py-2">{run.refusal_intercepted ? <Badge color="warn">Yes</Badge> : '—'}</td>
                  </tr>
                ))}
                {!loading && runs.length === 0 && (
                  <tr><td colSpan={8} className="py-8 text-center text-muted">No runs recorded</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
