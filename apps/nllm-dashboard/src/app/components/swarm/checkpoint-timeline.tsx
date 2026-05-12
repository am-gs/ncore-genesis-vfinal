'use client';

import { CheckpointInfo } from '@/app/types/swarm';
import { Database, Clock, ChevronRight } from 'lucide-react';

export function CheckpointTimeline({ checkpoints }: { checkpoints: CheckpointInfo[] }) {
  return (
    <div className="h-full flex flex-col overflow-hidden">
      <div className="flex items-center gap-1.5 px-3 py-2 border-b border-line">
        <Database className="h-3 w-3 text-cyan" />
        <h3 className="text-[10px] uppercase tracking-wider text-text-tertiary font-medium">Checkpoints</h3>
      </div>
      <div className="flex-1 overflow-auto p-3">
        <div className="space-y-2">
          {checkpoints.map((cp, i) => (
            <div key={cp.id} className="flex items-start gap-2 group">
              <div className="flex flex-col items-center gap-0.5 pt-1">
                <div className="h-2 w-2 rounded-full bg-cyan border border-cyan/50" />
                {i < checkpoints.length - 1 && (
                  <div className="w-px h-6 bg-line" />
                )}
              </div>
              <div className="flex-1 min-w-0 rounded-md bg-panel-2 border border-line p-2 group-hover:border-cyan/30 transition-colors">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-[10px] font-mono font-medium text-cyan">{cp.id}</span>
                  <span className="text-[9px] text-text-tertiary flex items-center gap-0.5">
                    <Clock className="h-2.5 w-2.5" />
                    {new Date(cp.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                  </span>
                </div>
                <p className="text-[9px] text-text-tertiary truncate">{cp.checkpoint_ns}</p>
                <p className="text-[9px] text-text-tertiary font-mono truncate mt-0.5 opacity-60">
                  {cp.state_json.slice(0, 60)}...
                </p>
              </div>
            </div>
          ))}
          {checkpoints.length === 0 && (
            <div className="text-center py-4 text-[10px] text-text-tertiary">
              No checkpoints yet
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
