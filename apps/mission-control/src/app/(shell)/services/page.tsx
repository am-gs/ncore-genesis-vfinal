'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { StatusDot } from '@/components/ui/StatusDot';
import { fetchHealth, restartService } from '@/lib/api';
import type { Service } from '@/types';
import { ExternalLink, RotateCcw } from 'lucide-react';

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
    try {
      await restartService(id);
      await load();
    } finally {
      setRestarting(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-text">All Services</h2>
        <Button onClick={load} variant="ghost"><RotateCcw className="h-4 w-4 mr-1" /> Refresh</Button>
      </div>
      {loading ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 10 }).map((_, i) => (
            <Card key={i} className="h-36 animate-pulse bg-panel-2" />
          ))}
        </div>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {services.map((svc) => (
            <Card key={svc.name}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{svc.name}</CardTitle>
                  <StatusDot ok={svc.ok} />
                </div>
              </CardHeader>
              <CardContent>
                <div className="mb-2 text-xs text-muted line-clamp-2">{svc.detail || 'No details'}</div>
                <div className="flex items-center gap-2 mb-3">
                  <Badge color={svc.ok ? 'ok' : 'bad'}>{svc.ok ? 'Healthy' : 'Unhealthy'}</Badge>
                  <span className="text-xs text-muted">{svc.latency_ms}ms</span>
                </div>
                <div className="flex gap-2">
                  {svc.link && (
                    <a href={svc.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-md border border-line px-2 py-1 text-xs text-muted hover:text-text transition-colors">
                      <ExternalLink className="h-3 w-3" /> Open
                    </a>
                  )}
                  <Button variant="ghost" onClick={() => handleRestart(svc.name)} disabled={restarting === svc.name} className="text-xs">
                    <RotateCcw className={`h-3 w-3 mr-1 ${restarting === svc.name ? 'animate-spin' : ''}`} />
                    {restarting === svc.name ? 'Restarting...' : 'Restart'}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
