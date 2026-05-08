'use client';

import { AgentStatus } from '@/app/types';
import { Circle, CheckCircle, AlertCircle, Clock } from 'lucide-react';

export function AgentStatusList({ agents }: { agents: AgentStatus[] }) {
  if (agents.length === 0) return null;

  return (
    <div className="space-y-1">
      <h4 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium mb-2">
        Active Agents
      </h4>
      {agents.map((agent) => {
        const getIcon = () => {
          switch (agent.status) {
            case 'running': return <Circle className="h-3 w-3 text-accent animate-pulse" />;
            case 'completed': return <CheckCircle className="h-3 w-3 text-ok" />;
            case 'error': return <AlertCircle className="h-3 w-3 text-bad" />;
            default: return <Clock className="h-3 w-3 text-text-tertiary" />;
          }
        };

        return (
          <div
            key={agent.role}
            className="flex items-center gap-2 px-2 py-1.5 rounded-md text-xs hover:bg-bg-2 transition-colors"
          >
            {getIcon()}
            <span className="flex-1 truncate">{agent.role}</span>
            <span className="text-[10px] text-text-tertiary tabular-nums">
              {agent.tokens_in + agent.tokens_out}t
            </span>
            <span className="text-[10px] text-text-tertiary tabular-nums">
              ${agent.cost_usd.toFixed(4)}
            </span>
          </div>
        );
      })}
    </div>
  );
}
