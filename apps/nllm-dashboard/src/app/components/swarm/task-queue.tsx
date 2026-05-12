'use client';

import { SwarmTask } from '@/app/types/swarm';
import { cn } from '@/app/lib/utils';
import { Play, CheckCircle, AlertCircle, Clock, Loader2 } from 'lucide-react';

export function TaskQueue({
  tasks,
  selectedId,
  onSelect,
}: {
  tasks: SwarmTask[];
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="h-full overflow-auto p-2 space-y-1">
      {tasks.map((task) => {
        const isActive = task.id === selectedId;
        const statusIcon = {
          running: <Loader2 className="h-3 w-3 text-accent animate-spin" />,
          completed: <CheckCircle className="h-3 w-3 text-ok" />,
          error: <AlertCircle className="h-3 w-3 text-bad" />,
          pending: <Clock className="h-3 w-3 text-text-tertiary" />,
        }[task.status];

        return (
          <button
            key={task.id}
            onClick={() => onSelect(task.id)}
            className={cn(
              'w-full text-left rounded-md p-2 border transition-all',
              isActive
                ? 'bg-accent/5 border-accent/30'
                : 'bg-panel-2 border-line hover:border-text-tertiary/30'
            )}
          >
            <div className="flex items-center justify-between mb-1">
              <span className="text-[10px] font-mono text-text-tertiary">{task.id}</span>
              {statusIcon}
            </div>
            <p className="text-xs font-medium truncate">{task.title}</p>
            <div className="flex items-center justify-between mt-1.5 text-[9px] text-text-tertiary">
              <span>{task.agents.length} agents</span>
              <span>${task.total_cost.toFixed(4)}</span>
            </div>
            <div className="flex items-center gap-1 mt-1">
              {task.agents.slice(0, 4).map((a) => (
                <div
                  key={a.id}
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    a.status === 'completed' && 'bg-ok',
                    a.status === 'running' && 'bg-accent animate-pulse',
                    a.status === 'error' && 'bg-bad',
                    a.status === 'idle' && 'bg-text-tertiary/30'
                  )}
                />
              ))}
            </div>
          </button>
        );
      })}
      {tasks.length === 0 && (
        <div className="text-center py-6 text-[10px] text-text-tertiary">
          No swarm tasks. Start a simulation to see LangGraph in action.
        </div>
      )}
    </div>
  );
}
