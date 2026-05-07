'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { fetchHealth, fetchRuns, restartService } from '@/lib/api';
import type { Service, Run } from '@/types';
import { ExternalLink, RotateCcw, Clock, TrendingUp, AlertTriangle } from 'lucide-react';

export default function DashboardPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const [h, r] = await Promise.all([fetchHealth(), fetchRuns(20)]);
      setServices(h.services);
      setRuns(r.runs || []);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const healthy = services.filter((s) => s.ok).length;
  const total = services.length;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Services</div>
              <div className="mt-1 text-2xl font-bold">{healthy}/{total}</div>
            </div>
            <StatusDot ok={healthy === total && total > 0} size="lg" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Total Calls</div>
              <div className="mt-1 text-2xl font-bold">{runs.length}</div>
            </div>
            <TrendingUp className="h-5 w-5 text-accent" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Avg Latency</div>
              <div className="mt-1 text-2xl font-bold">
                {runs.length > 0 ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / runs.length) : 0}ms
              </div>
            </div>
            <Clock className="h-5 w-5 text-accent-2" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Refusals</div>
              <div className="mt-1 text-2xl font-bold">{runs.filter((r) => r.refusal_intercepted).length}</div>
            </div>
            <AlertTriangle className="h-5 w-5 text-warn" />
          </div>
        </CardContent></Card>
      </div>

      {error && <div className="rounded-lg border border-bad/25 bg-bad/10 px-4 py-3 text-sm text-bad">{error}</div>}

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text">Service Health</h2>
        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="h-28 animate-pulse bg-panel-2" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((svc) => (
              <Card key={svc.name}>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{svc.name}</CardTitle>
                    <StatusDot ok={svc.ok} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-2 text-xs text-muted">{svc.detail}</div>
                  <div className="flex items-center gap-2">
                    <Badge color={svc.ok ? 'ok' : 'bad'}>{svc.ok ? 'Healthy' : 'Down'}</Badge>
                    <span className="text-xs text-muted">{svc.latency_ms}ms</span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    {svc.link && (
                      <a href={svc.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-text transition-colors">
                        <ExternalLink className="h-3 w-3" /> Open
                      </a>
                    )}
                    <button
                      onClick={async () => {
                        const id = svc.name.toLowerCase().replace(/\s+/g, '-');
                        await restartService(id);
                        load();
                      }}
                      className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-text transition-colors"
                    >
                      <RotateCcw className="h-3 w-3" /> Restart
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text">Recent Runs</h2>
        <Card>
          <CardContent className="pt-4">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted uppercase tracking-wider">
                    <th className="pb-2 pr-4">Time</th>
                    <th className="pb-2 pr-4">Task</th>
                    <th className="pb-2 pr-4">Provider</th>
                    <th className="pb-2 pr-4">Model</th>
                    <th className="pb-2 pr-4">Fallback</th>
                    <th className="pb-2 pr-4">Latency</th>
                    <th className="pb-2">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 15).map((run) => (
                    <tr key={`${run.ts}-${run.task_id}`} className="border-b border-line/50 text-xs">
                      <td className="py-2 pr-4 font-mono text-muted">{new Date(run.ts * 1000).toLocaleTimeString()}</td>
                      <td className="py-2 pr-4 truncate max-w-[120px]">{run.task_id}</td>
                      <td className="py-2 pr-4"><Badge color={run.provider === 'remote' ? 'accent' : 'muted'}>{run.provider}</Badge></td>
                      <td className="py-2 pr-4 font-mono text-muted">{run.model}</td>
                      <td className="py-2 pr-4 text-muted">{run.fallback_reason !== 'none' ? run.fallback_reason : '—'}</td>
                      <td className="py-2 pr-4">{run.latency_ms}ms</td>
                      <td className="py-2">
                        <Badge color={run.completion_status === 'completed' ? 'ok' : run.completion_status === 'refused' ? 'warn' : 'bad'}>
                          {run.completion_status}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                  {runs.length === 0 && (
                    <tr><td colSpan={7} className="py-8 text-center text-muted">No runs yet</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
