'use client';

import { SwarmAgent } from '@/app/types/swarm';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Cpu, Clock, Coins, Database, CheckCircle, AlertCircle, Circle, Loader2 } from 'lucide-react';

export function AgentStatusCards({ agents }: { agents: SwarmAgent[] }) {
  return (
    <div className="h-full overflow-auto p-3 space-y-2">
      <h3 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium flex items-center gap-1.5 sticky top-0 bg-panel py-1 z-10">
        <Cpu className="h-3 w-3" /> Agents
      </h3>
      {agents.map((agent) => (
        <AgentCard key={agent.id} agent={agent} />
      ))}
    </div>
  );
}

function AgentCard({ agent }: { agent: SwarmAgent }) {
  const statusIcons: Record<string, React.ReactNode> = {
    idle: <Circle className="h-3 w-3 text-text-tertiary" />,
    running: <Loader2 className="h-3 w-3 text-accent animate-spin" />,
    completed: <CheckCircle className="h-3 w-3 text-ok" />,
    error: <AlertCircle className="h-3 w-3 text-bad" />,
    paused: <Circle className="h-3 w-3 text-warn" />,
  };

  const statusColors: Record<string, string> = {
    idle: 'border-line',
    running: 'border-accent/30 bg-accent/5',
    completed: 'border-ok/30 bg-ok/5',
    error: 'border-bad/30 bg-bad/5',
    paused: 'border-warn/30 bg-warn/5',
  };

  return (
    <Card className={`border ${statusColors[agent.status] || 'border-line'} transition-colors`}>
      <CardHeader className="pb-1.5 pt-2.5 px-3">
        <CardTitle className="text-xs flex items-center justify-between">
          <span className="truncate">{agent.role}</span>
          <span className="flex items-center gap-1">{statusIcons[agent.status]}</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="px-3 pb-2.5 pt-0">
        <div className="grid grid-cols-2 gap-x-3 gap-y-1 text-[10px]">
          <div className="flex items-center gap-1 text-text-tertiary">
            <Cpu className="h-3 w-3" />
            <span className="truncate">{agent.model}</span>
          </div>
          <div className="flex items-center gap-1 text-text-tertiary">
            <Clock className="h-3 w-3" />
            <span>{(agent.latency_ms / 1000).toFixed(2)}s</span>
          </div>
          <div className="flex items-center gap-1 text-text-tertiary">
            <Coins className="h-3 w-3" />
            <span className="text-accent">${agent.cost_usd.toFixed(5)}</span>
          </div>
          <div className="flex items-center gap-1 text-text-tertiary">
            <Database className="h-3 w-3" />
            <span>{(agent.tokens_in + agent.tokens_out).toLocaleString()}</span>
          </div>
        </div>
        {agent.checkpoint_id && (
          <div className="mt-1.5 flex items-center gap-1 text-[9px] text-cyan">
            <Database className="h-2.5 w-2.5" />
            <span>CP: {agent.checkpoint_id}</span>
          </div>
        )}
        {(agent.depends_on.length > 0 || agent.parallel_with.length > 0) && (
          <div className="mt-1 flex flex-wrap gap-1">
            {agent.depends_on.map((dep) => (
              <span key={dep} className="px-1 py-0.5 rounded text-[9px] bg-panel-3 text-text-tertiary border border-line">
                ↳ {dep.slice(-4)}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
