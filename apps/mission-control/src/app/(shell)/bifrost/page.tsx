'use client';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { fetchRuns } from '@/lib/api';
import type { Run } from '@/types';
import { Shield, TrendingUp, Clock, AlertTriangle, ArrowRight } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';

export default function BifrostPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => { try { const r = await fetchRuns(200); setRuns(r.runs || []); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const stats = useMemo(() => {
    const total = runs.length;
    const completed = runs.filter(r => r.completion_status === 'completed').length;
    const refused = runs.filter(r => r.refusal_intercepted).length;
    const avgLatency = total > 0 ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / total) : 0;
    const remote = runs.filter(r => r.provider === 'remote').length;
    const local = runs.filter(r => r.provider === 'sovereign-local').length;
    const policy = runs.filter(r => r.provider === 'policy').length;
    return { total, completed, refused, avgLatency, remote, local, policy };
  }, [runs]);

  const hourly = useMemo(() => {
    const buckets: Record<string, number> = {};
    runs.forEach(r => { const h = new Date(r.ts * 1000).toISOString().slice(0, 13) + ':00'; buckets[h] = (buckets[h] || 0) + 1; });
    return Object.entries(buckets).slice(-24).sort((a, b) => a[0].localeCompare(b[0])).map(([time, count]) => ({ time: time.replace('T', ' '), count }));
  }, [runs]);

  const providerData = useMemo(() => [
    { name: 'Remote', value: stats.remote, fill: '#8b5cf6' },
    { name: 'Local', value: stats.local, fill: '#22c55e' },
    { name: 'Policy', value: stats.policy, fill: '#ef4444' },
  ], [stats]);

  const chartTooltipStyle = {
    backgroundColor: 'rgba(15, 23, 42, 0.95)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: '12px',
    backdropFilter: 'blur(12px)',
    color: '#e5e7eb',
    fontSize: '12px',
  };

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.08)] to-[rgba(6,182,212,0.04)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient-accent">Bifrost Gateway</h1>
            <p className="mt-1 text-xs text-muted">Policy-enforced LLM routing with budget tracking and refusal interception</p>
          </div>
          <Shield className="h-8 w-8 text-violet-400/60" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Total Calls</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{stats.total.toLocaleString()}</div>
            </div>
            <div className="rounded-xl bg-violet-500/10 p-2.5"><TrendingUp className="h-5 w-5 text-violet-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Completed</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{stats.completed}</div>
            </div>
            <div className="rounded-xl bg-emerald-500/10 p-2.5"><Shield className="h-5 w-5 text-emerald-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Avg Latency</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{stats.avgLatency}ms</div>
            </div>
            <div className="rounded-xl bg-cyan-500/10 p-2.5"><Clock className="h-5 w-5 text-cyan-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Refusals</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{stats.refused}</div>
            </div>
            <div className="rounded-xl bg-amber-500/10 p-2.5"><AlertTriangle className="h-5 w-5 text-amber-400" /></div>
          </div>
        </CardContent></Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card glow>
          <CardHeader><CardTitle>Provider Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={providerData} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="name" stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Bar dataKey="value" radius={[6, 6, 0, 0]}>
                    {providerData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        <Card glow>
          <CardHeader><CardTitle>Hourly Activity</CardTitle></CardHeader>
          <CardContent>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={hourly} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
                  <defs>
                    <linearGradient id="areaColor" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#8b5cf6" stopOpacity={0.3} />
                      <stop offset="95%" stopColor="#8b5cf6" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.04)" />
                  <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} axisLine={false} angle={-30} textAnchor="end" height={50} />
                  <YAxis stroke="#94a3b8" fontSize={12} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={chartTooltipStyle} />
                  <Area type="monotone" dataKey="count" stroke="#8b5cf6" strokeWidth={2} fill="url(#areaColor)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>
      </div>

      <Card glow>
        <CardHeader><CardTitle>Fallback Chain</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <Badge color="accent">Remote API</Badge>
            <ArrowRight className="h-3.5 w-3.5 text-muted" />
            <Badge color="ok">Local (qwen3-8b)</Badge>
            <ArrowRight className="h-3.5 w-3.5 text-muted" />
            <Badge color="warn">Local (dolphin-mistral)</Badge>
            <ArrowRight className="h-3.5 w-3.5 text-muted" />
            <Badge color="bad">Policy Block</Badge>
          </div>
          <p className="mt-4 text-xs text-muted leading-relaxed">
            Bifrost routes to remote APIs first, falls back to local Ollama models, and intercepts refusals with policy enforcement.
            Monthly cap: <span className="font-mono text-text">$38.00</span>. Hard stops on CSAM/bodily harm. Dual-use requires authorization.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
