'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Sparkline } from '@/components/ui/Sparkline';
import { fetchHealth, fetchRuns, restartService } from '@/lib/api';
import type { Service, Run } from '@/types';
import { ExternalLink, RotateCcw, Clock, TrendingUp, AlertTriangle, Shield } from 'lucide-react';

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
  const sparkData = runs.slice(-20).map((r) => r.latency_ms);

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.1)] via-[rgba(6,182,212,0.05)] to-[rgba(99,102,241,0.08)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient">Sovereign Mission Control</h1>
            <p className="mt-1 text-xs text-muted">Local high-compliance agentic stack &middot; Real-time monitoring</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot ok={healthy === total && total > 0} size="lg" />
            <span className="text-sm font-medium text-text">{healthy === total && total > 0 ? 'All Systems Nominal' : `${total - healthy} Issues`}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Services</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{healthy}<span className="text-lg text-muted/60">/{total}</span></div>
                <div className="mt-1 text-xs text-emerald-400">{((healthy / (total || 1)) * 100).toFixed(0)}% uptime</div>
              </div>
              <div className="rounded-xl bg-emerald-500/10 p-2.5"><Shield className="h-5 w-5 text-emerald-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Total Calls</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{runs.length.toLocaleString()}</div>
                <Sparkline data={sparkData} height={30} color="#8b5cf6" />
              </div>
              <div className="rounded-xl bg-violet-500/10 p-2.5"><TrendingUp className="h-5 w-5 text-violet-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Avg Latency</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">
                  {runs.length > 0 ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / runs.length) : 0}ms
                </div>
              </div>
              <div className="rounded-xl bg-cyan-500/10 p-2.5"><Clock className="h-5 w-5 text-cyan-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Refusals</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{runs.filter((r) => r.refusal_intercepted).length}</div>
              </div>
              <div className="rounded-xl bg-amber-500/10 p-2.5"><AlertTriangle className="h-5 w-5 text-amber-400" /></div>
            </div>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300 backdrop-blur-md">
          <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{error}</div>
        </div>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text tracking-tight">Service Health</h2>
        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => <Card key={i} className="h-32 animate-pulse bg-white/[0.02]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((svc) => (
              <Card key={svc.name} glow>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{svc.name}</CardTitle>
                    <StatusDot ok={svc.ok} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-2 text-xs text-muted line-clamp-1">{svc.detail}</div>
                  <div className="flex items-center gap-2">
                    <Badge color={svc.ok ? 'ok' : 'bad'}>{svc.ok ? 'Healthy' : 'Down'}</Badge>
                    <span className="text-xs font-mono text-muted">{svc.latency_ms}ms</span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    {svc.link && (
                      <a href={svc.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
                        <ExternalLink className="h-3 w-3" /> Open
                      </a>
                    )}
                    <button onClick={async () => { await restartService(svc.name.toLowerCase().replace(/\s+/g, '-')); load(); }}
                      className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all"
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
        <h2 className="mb-3 text-sm font-semibold text-text tracking-tight">Recent Runs</h2>
        <Card glow>
          <CardContent className="pt-5">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-[11px] text-muted uppercase tracking-wider">
                    <th className="pb-3 pr-4 font-semibold">Time</th>
                    <th className="pb-3 pr-4 font-semibold">Task</th>
                    <th className="pb-3 pr-4 font-semibold">Provider</th>
                    <th className="pb-3 pr-4 font-semibold">Model</th>
                    <th className="pb-3 pr-4 font-semibold">Fallback</th>
                    <th className="pb-3 pr-4 font-semibold">Latency</th>
                    <th className="pb-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 12).map((run) => (
                    <tr key={`${run.ts}-${run.task_id}`} className="border-b border-white/[0.03] text-xs transition-colors hover:bg-white/[0.02]">
                      <td className="py-3 pr-4 font-mono text-muted">{new Date(run.ts * 1000).toLocaleTimeString()}</td>
                      <td className="py-3 pr-4 truncate max-w-[100px]">{run.task_id}</td>
                      <td className="py-3 pr-4"><Badge color={run.provider === 'remote' ? 'accent' : run.provider === 'policy' ? 'warn' : 'muted'}>{run.provider}</Badge></td>
                      <td className="py-3 pr-4 font-mono text-muted">{run.model}</td>
                      <td className="py-3 pr-4 text-muted">{run.fallback_reason !== 'none' ? run.fallback_reason : '—'}</td>
                      <td className="py-3 pr-4 font-mono">{run.latency_ms}ms</td>
                      <td className="py-3">
                        <Badge color={run.completion_status === 'completed' ? 'ok' : run.completion_status === 'refused' ? 'warn' : 'bad'}>{run.completion_status}</Badge>
                      </td>
                    </tr>
                  ))}
                  {runs.length === 0 && <tr><td colSpan={7} className="py-10 text-center text-muted text-sm">No runs yet</td></tr>}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
