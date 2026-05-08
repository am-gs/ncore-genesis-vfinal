'use client';

import { TaskPlan, AgentStatus } from '@/app/types';
import {
  CheckCircle, Circle, AlertCircle, Clock,
  FileText
} from 'lucide-react';

export function PlanViewer({
  plan,
  agentStatuses,
}: {
  plan: TaskPlan | null;
  agentStatuses?: AgentStatus[];
}) {
  if (!plan) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-text-tertiary">
        <FileText className="h-10 w-10 mb-2 opacity-20" />
        <p className="text-sm">No plan generated yet</p>
        <p className="text-xs mt-1">The agent will create a plan when you start a task</p>
      </div>
    );
  }

  const getStatus = (role: string): AgentStatus | undefined => {
    return agentStatuses?.find((a) => a.role === role);
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'completed': return <CheckCircle className="h-3.5 w-3.5 text-ok" />;
      case 'running': return <Circle className="h-3.5 w-3.5 text-accent animate-pulse" />;
      case 'error': return <AlertCircle className="h-3.5 w-3.5 text-bad" />;
      default: return <Clock className="h-3.5 w-3.5 text-text-tertiary" />;
    }
  };

  return (
    <div className="h-full flex flex-col bg-bg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-medium">Execution Plan</h3>
        <span className="text-[10px] text-text-tertiary">
          {plan.agents.length} agents · {plan.plan_time.toFixed(2)}s plan time
        </span>
      </div>

      <div className="space-y-3">
        {plan.agents.map((agent, i) => {
          const status = getStatus(agent.role);
          return (
            <div
              key={i}
              className={`rounded-lg border p-3 transition-all
                ${status?.status === 'running'
                  ? 'border-accent/30 bg-accent/5'
                  : status?.status === 'completed'
                  ? 'border-ok/20 bg-ok/5'
                  : 'border-line bg-panel'
                }`}
            >
              <div className="flex items-center gap-2 mb-2">
                {getStatusIcon(status?.status)}
                <span className="text-xs font-medium">{agent.role}</span>
                {agent.tool && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-bg-2 text-text-tertiary">
                    {agent.tool}
                  </span>
                )}
                {agent.uncensored && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-bad/10 text-bad">
                    uncensored
                  </span>
                )}
              </div>
              <p className="text-[11px] text-text-secondary leading-relaxed">
                {agent.prompt}
              </p>
              {status && (
                <div className="flex items-center gap-3 mt-2 text-[10px] text-text-tertiary">
                  <span>{status.tokens_in + status.tokens_out} tokens</span>
                  <span>${status.cost_usd.toFixed(4)}</span>
                  <span>{status.latency.toFixed(1)}s</span>
                  {status.progress > 0 && status.progress < 100 && (
                    <div className="flex-1 h-1 bg-bg-2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-accent transition-all duration-300"
                        style={{ width: `${status.progress}%` }}
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
