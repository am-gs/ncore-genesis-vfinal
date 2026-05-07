'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { fetchHealth, restartService } from '@/lib/api';
import type { Service } from '@/types';
import { ExternalLink, RotateCcw, Activity } from 'lucide-react';

export default function ServicesPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [loading, setLoading] = useState(true);
  const [restarting, setRestarting] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setServices(h.services);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const handleRestart = async (name: string) => {
    const id = name.toLowerCase().replace(/\s+/g, '-');
    setRestarting(name);
    try { await restartService(id); await load(); } finally { setRestarting(null); }
  };

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-accent" />
          <h2 className="text-sm font-semibold text-text tracking-tight">All Services</h2>
          <Badge color="muted">{services.filter(s => s.ok).length}/{services.length} healthy</Badge>
        </div>
        <button onClick={load} className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
          <RotateCcw className="h-3.5 w-3.5" /> Refresh
        </button>
      </div>

      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 10 }).map((_, i) => <Card key={i} className="h-40 animate-pulse bg-white/[0.02]" />)}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {services.map((svc) => (
            <Card key={svc.name} glow>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{svc.name}</CardTitle>
                  <StatusDot ok={svc.ok} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-3 text-xs text-muted line-clamp-2">{svc.detail || 'No details'}</div>
                <div className="flex items-center gap-2 mb-4">
                  <Badge color={svc.ok ? 'ok' : 'bad'}>{svc.ok ? 'Healthy' : 'Unhealthy'}</Badge>
                  <span className="text-xs font-mono text-muted">{svc.latency_ms}ms</span>
                </div>
                <div className="flex gap-2">
                  {svc.link && (
                    <a href={svc.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
                      <ExternalLink className="h-3 w-3" /> Open
                    </a>
                  )}
                  <button onClick={() => handleRestart(svc.name)} disabled={restarting === svc.name}
                    className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all disabled:opacity-50"
                  >
                    <RotateCcw className={`h-3 w-3 ${restarting === svc.name ? 'animate-spin' : ''}`} />
                    {restarting === svc.name ? 'Restarting...' : 'Restart'}
                  </button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
