'use client';
import { useState, useEffect, useCallback, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { fetchRuns } from '@/lib/api';
import type { Run } from '@/types';
import { Shield, TrendingUp, Clock, AlertTriangle, DollarSign } from 'lucide-react';

export default function BifrostPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetchRuns(200);
      setRuns(r.runs || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 30000); return () => clearInterval(t); }, [load]);

  const stats = useMemo(() => {
    const total = runs.length;
    const completed = runs.filter((r) => r.completion_status === 'completed').length;
    const refused = runs.filter((r) => r.refusal_intercepted).length;
    const avgLatency = total > 0 ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / total) : 0;
    const remote = runs.filter((r) => r.provider === 'remote').length;
    const local = runs.filter((r) => r.provider === 'sovereign-local').length;
    const policy = runs.filter((r) => r.provider === 'policy').length;
    return { total, completed, refused, avgLatency, remote, local, policy };
  }, [runs]);

  const hourly = useMemo(() => {
    const buckets: Record<string, number> = {};
    runs.forEach((r) => {
      const h = new Date(r.ts * 1000).toISOString().slice(0, 13) + ':00';
      buckets[h] = (buckets[h] || 0) + 1;
    });
    return Object.entries(buckets).slice(-24).sort((a, b) => a[0].localeCompare(b[0]));
  }, [runs]);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Shield className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">Bifrost Gateway</h2>
          <p className="text-xs text-muted">Policy-enforced LLM routing with budget tracking</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Total Calls</div>
              <div className="mt-1 text-2xl font-bold">{stats.total}</div>
            </div>
            <TrendingUp className="h-5 w-5 text-accent" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Completed</div>
              <div className="mt-1 text-2xl font-bold">{stats.completed}</div>
            </div>
            <Shield className="h-5 w-5 text-ok" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Avg Latency</div>
              <div className="mt-1 text-2xl font-bold">{stats.avgLatency}ms</div>
            </div>
            <Clock className="h-5 w-5 text-accent-2" />
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-muted uppercase tracking-wider">Refusals</div>
              <div className="mt-1 text-2xl font-bold">{stats.refused}</div>
            </div>
            <AlertTriangle className="h-5 w-5 text-warn" />
          </div>
        </CardContent></Card>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader><CardTitle>Provider Distribution</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {[
                { label: 'Remote (paid)', value: stats.remote, color: 'bg-accent' },
                { label: 'Sovereign Local', value: stats.local, color: 'bg-ok' },
                { label: 'Policy Block', value: stats.policy, color: 'bg-bad' },
              ].map((item) => (
                <div key={item.label}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className="text-muted">{item.label}</span>
                    <span className="text-text">{item.value}</span>
                  </div>
                  <div className="h-2 rounded-full bg-panel-2">
                    <div
                      className={`h-2 rounded-full ${item.color} transition-all`}
                      style={{ width: stats.total > 0 ? `${(item.value / stats.total) * 100}%` : '0%' }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle>Hourly Activity</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-2 max-h-64 overflow-y-auto">
              {hourly.length === 0 && <div className="text-sm text-muted">No data yet</div>}
              {hourly.map(([time, count]) => (
                <div key={time} className="flex items-center gap-3 text-xs">
                  <span className="w-32 shrink-0 font-mono text-muted">{time.replace('T', ' ')}</span>
                  <div className="h-3 rounded-full bg-accent flex-1" style={{ maxWidth: `${Math.min(count * 10, 200)}px` }} />
                  <span className="text-text w-8 text-right">{count}</span>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Fallback Chain</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-2 text-xs">
            <Badge color="accent">Remote API</Badge>
            <span className="text-muted">→</span>
            <Badge color="ok">Local (qwen3-8b)</Badge>
            <span className="text-muted">→</span>
            <Badge color="warn">Local (dolphin-mistral)</Badge>
            <span className="text-muted">→</span>
            <Badge color="bad">Policy Block</Badge>
          </div>
          <p className="mt-3 text-xs text-muted">
            Bifrost routes to remote APIs first, falls back to local Ollama models, and intercepts
            refusals with policy enforcement. Monthly cap: $38.00.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
