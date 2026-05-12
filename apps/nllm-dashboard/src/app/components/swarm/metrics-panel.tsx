'use client';

import { SwarmMetrics } from '@/app/types/swarm';
import { Activity, Zap, Clock, Database, Shield, MessageSquare } from 'lucide-react';

export function SwarmMetricsPanel({ metrics }: { metrics: SwarmMetrics }) {
  return (
    <div className="p-3 space-y-2 border-b border-line">
      <h3 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium flex items-center gap-1.5">
        <Activity className="h-3 w-3" /> Swarm Metrics
      </h3>
      <div className="grid grid-cols-2 gap-1.5">
        <MetricTile icon={<Zap className="h-3 w-3" />} label="Agents" value={metrics.total_agents.toString()} accent="text-accent" />
        <MetricTile icon={<Clock className="h-3 w-3" />} label="Avg Latency" value={`${metrics.avg_latency.toFixed(2)}s`} accent="text-cyan" />
        <MetricTile icon={<Database className="h-3 w-3" />} label="Checkpoints" value={metrics.checkpoint_count.toString()} accent="text-ok" />
        <MetricTile icon={<Shield className="h-3 w-3" />} label="Recovery" value={`${(metrics.recovery_success_rate * 100).toFixed(0)}%`} accent="text-ok" />
        <MetricTile icon={<MessageSquare className="h-3 w-3" />} label="A2A/min" value={metrics.a2a_messages_per_min.toString()} accent="text-warn" />
        <MetricTile icon={<Zap className="h-3 w-3" />} label="Cost Today" value={`$${metrics.total_cost_today.toFixed(4)}`} accent="text-accent" />
      </div>
    </div>
  );
}

function MetricTile({ icon, label, value, accent }: { icon: React.ReactNode; label: string; value: string; accent: string }) {
  return (
    <div className="rounded-md bg-panel-2 border border-line p-2">
      <div className={`${accent} mb-0.5`}>{icon}</div>
      <p className="text-sm font-semibold leading-tight">{value}</p>
      <p className="text-[9px] text-text-tertiary">{label}</p>
    </div>
  );
}
