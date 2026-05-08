'use client';

import { useState } from 'react';
import { AgentStatusList } from './agent-status-list';
import { BudgetBar } from './budget-bar';
import { Session, TaskResult, AgentStatus, BudgetInfo } from '@/app/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import {
  Activity, CheckCircle, AlertCircle, Clock, Zap,
  DollarSign, TrendingUp, Hash
} from 'lucide-react';

export function StatusPanel({
  sessions,
  activeSessionId,
  agents,
  result,
  budget,
}: {
  sessions: Session[];
  activeSessionId: string | null;
  agents: AgentStatus[];
  result: TaskResult | null;
  budget: BudgetInfo;
}) {
  const activeSession = sessions.find((s) => s.id === activeSessionId);

  const totalTokens = sessions.reduce((sum, s) => {
    return sum + (s.result?.tokens.total || 0);
  }, 0);

  const totalCost = sessions.reduce((sum, s) => {
    return sum + (s.result?.cost_usd || 0);
  }, 0);

  const completedCount = sessions.filter((s) => s.status === 'completed').length;
  const errorCount = sessions.filter((s) => s.status === 'error').length;

  return (
    <div className="flex flex-col h-full bg-panel border-l border-line">
      {/* Header */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-line">
        <Activity className="h-4 w-4 text-accent" />
        <h2 className="font-semibold text-sm">Status</h2>
      </div>

      <div className="flex-1 overflow-hidden">
        <div className="h-full overflow-auto p-3 space-y-3">
          {/* Current Task */}
          {activeSession && (
            <Card className="border-accent/20 bg-accent/5">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs flex items-center justify-between">
                  <span>Current Task</span>
                  <span className={`
                    text-[10px] px-1.5 py-0.5 rounded
                    ${activeSession.status === 'active' ? 'bg-accent/20 text-accent' : ''}
                    ${activeSession.status === 'completed' ? 'bg-ok/20 text-ok' : ''}
                    ${activeSession.status === 'error' ? 'bg-bad/20 text-bad' : ''}
                  `}>
                    {activeSession.status}
                  </span>
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-[11px] text-text-secondary line-clamp-2 mb-2">
                  {activeSession.title}
                </p>
                {result && (
                  <div className="space-y-1 text-[10px]">
                    <div className="flex justify-between">
                      <span className="text-text-tertiary">Latency</span>
                      <span>{result.latency_s.toFixed(2)}s</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-tertiary">Agents</span>
                      <span>{result.agents}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-text-tertiary">Cost</span>
                      <span className="text-accent">${result.cost_usd.toFixed(4)}</span>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Stats */}
          <div className="grid grid-cols-2 gap-2">
            <Card>
              <CardContent className="p-3 flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-accent" />
                <div>
                  <p className="text-[10px] text-text-tertiary">Total Cost</p>
                  <p className="text-sm font-semibold">${totalCost.toFixed(4)}</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 flex items-center gap-2">
                <Hash className="h-4 w-4 text-accent-3" />
                <div>
                  <p className="text-[10px] text-text-tertiary">Tokens</p>
                  <p className="text-sm font-semibold">{totalTokens.toLocaleString()}</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 flex items-center gap-2">
                <CheckCircle className="h-4 w-4 text-ok" />
                <div>
                  <p className="text-[10px] text-text-tertiary">Completed</p>
                  <p className="text-sm font-semibold">{completedCount}</p>
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-3 flex items-center gap-2">
                <AlertCircle className="h-4 w-4 text-bad" />
                <div>
                  <p className="text-[10px] text-text-tertiary">Errors</p>
                  <p className="text-sm font-semibold">{errorCount}</p>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Budget */}
          <BudgetBar budget={budget} />

          {/* Active Agents */}
          {agents.length > 0 && (
            <div className="pt-2">
              <AgentStatusList agents={agents} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
