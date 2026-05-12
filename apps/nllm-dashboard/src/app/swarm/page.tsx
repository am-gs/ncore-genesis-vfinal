'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import { SwarmTask, LangGraphNode, SwarmMetrics } from '@/app/types/swarm';
import { SwarmMetricsPanel } from '@/app/components/swarm/metrics-panel';
import { LangGraphCanvas } from '@/app/components/swarm/langgraph-canvas';
import { AgentStatusCards } from '@/app/components/swarm/agent-status-cards';
import { CheckpointTimeline } from '@/app/components/swarm/checkpoint-timeline';
import { TaskQueue } from '@/app/components/swarm/task-queue';
import { Button } from '@/app/components/ui/button';
import {
  Play, RefreshCw, Zap, Network, Activity,
  RotateCcw, Shield, GitBranch
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

const DEMO_SWARM_TASKS: SwarmTask[] = [
  {
    id: 'swarm-001',
    title: 'Multi-Agent Code Review Pipeline',
    status: 'running',
    agents: [
      {
        id: 'agent-a1',
        role: 'Router',
        status: 'completed',
        model: 'kimi-k2.6',
        provider: 'fireworks',
        tokens_in: 420,
        tokens_out: 180,
        latency_ms: 1240,
        cost_usd: 0.0003,
        checkpoint_id: 'cp-001',
        depends_on: [],
        parallel_with: [],
      },
      {
        id: 'agent-a2',
        role: 'Code Analyst',
        status: 'running',
        model: 'kimi-k2.6',
        provider: 'fireworks',
        tokens_in: 2100,
        tokens_out: 3400,
        latency_ms: 3800,
        cost_usd: 0.0021,
        checkpoint_id: 'cp-002',
        depends_on: ['agent-a1'],
        parallel_with: ['agent-a3'],
      },
      {
        id: 'agent-a3',
        role: 'Security Critic',
        status: 'running',
        model: 'kimi-k2.6',
        provider: 'fireworks',
        tokens_in: 1800,
        tokens_out: 2900,
        latency_ms: 4100,
        cost_usd: 0.0019,
        checkpoint_id: 'cp-003',
        depends_on: ['agent-a1'],
        parallel_with: ['agent-a2'],
      },
      {
        id: 'agent-a4',
        role: 'Synthesis',
        status: 'idle',
        model: 'kimi-k2.6',
        provider: 'fireworks',
        tokens_in: 0,
        tokens_out: 0,
        latency_ms: 0,
        cost_usd: 0,
        depends_on: ['agent-a2', 'agent-a3'],
        parallel_with: [],
      },
    ],
    nodes: [
      { id: 'entry', label: 'Start', type: 'entry', status: 'completed', x: 50, y: 50 },
      { id: 'agent-a1', label: 'Router', type: 'router', status: 'completed', x: 200, y: 50 },
      { id: 'agent-a2', label: 'Code Analyst', type: 'agent', status: 'active', x: 350, y: 20 },
      { id: 'agent-a3', label: 'Security Critic', type: 'critic', status: 'active', x: 350, y: 80 },
      { id: 'cp-002', label: 'CP', type: 'checkpoint', status: 'completed', x: 500, y: 20 },
      { id: 'cp-003', label: 'CP', type: 'checkpoint', status: 'completed', x: 500, y: 80 },
      { id: 'agent-a4', label: 'Synthesis', type: 'agent', status: 'idle', x: 650, y: 50 },
      { id: 'end', label: 'End', type: 'end', status: 'idle', x: 800, y: 50 },
    ],
    edges: [
      { from: 'entry', to: 'agent-a1', status: 'completed' },
      { from: 'agent-a1', to: 'agent-a2', status: 'completed', label: 'route' },
      { from: 'agent-a1', to: 'agent-a3', status: 'completed', label: 'route' },
      { from: 'agent-a2', to: 'cp-002', status: 'completed' },
      { from: 'agent-a3', to: 'cp-003', status: 'completed' },
      { from: 'cp-002', to: 'agent-a4', status: 'pending' },
      { from: 'cp-003', to: 'agent-a4', status: 'pending' },
      { from: 'agent-a4', to: 'end', status: 'pending' },
    ],
    checkpoints: [
      { id: 'cp-001', thread_id: 'swarm-001', checkpoint_ns: 'router', created_at: '2026-05-12T10:00:00Z', agent_id: 'agent-a1', state_json: '{"route": "parallel_review"}' },
      { id: 'cp-002', thread_id: 'swarm-001', checkpoint_ns: 'analysis', created_at: '2026-05-12T10:02:30Z', agent_id: 'agent-a2', state_json: '{"findings": 7}' },
      { id: 'cp-003', thread_id: 'swarm-001', checkpoint_ns: 'security', created_at: '2026-05-12T10:03:15Z', agent_id: 'agent-a3', state_json: '{"vulns": 2}' },
    ],
    total_latency: 9.14,
    total_cost: 0.0043,
    created_at: Date.now() - 300000,
    updated_at: Date.now(),
    recovery_count: 0,
  },
];

const DEMO_METRICS: SwarmMetrics = {
  active_tasks: 1,
  total_agents: 4,
  avg_latency: 3.05,
  total_cost_today: 0.0124,
  checkpoint_count: 12,
  recovery_success_rate: 0.98,
  a2a_messages_per_min: 45,
};

export default function SwarmPage() {
  const [tasks, setTasks] = useState<SwarmTask[]>(DEMO_SWARM_TASKS);
  const [selectedTaskId, setSelectedTaskId] = useState<string>(DEMO_SWARM_TASKS[0].id);
  const [metrics, setMetrics] = useState<SwarmMetrics>(DEMO_METRICS);
  const [isSimulating, setIsSimulating] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const selectedTask = tasks.find((t) => t.id === selectedTaskId);

  const simulateTick = useCallback(() => {
    setTasks((prev) =>
      prev.map((task) => {
        if (task.status !== 'running') return task;
        const runningAgents = task.agents.filter((a) => a.status === 'running');
        if (runningAgents.length === 0) {
          const pendingAgents = task.agents.filter((a) => a.status === 'idle');
          if (pendingAgents.length > 0) {
            const nextAgent = pendingAgents[0];
            return {
              ...task,
              agents: task.agents.map((a) =>
                a.id === nextAgent.id
                  ? { ...a, status: 'running', tokens_in: a.tokens_in + 100, tokens_out: a.tokens_out + 150 }
                  : a
              ),
              nodes: task.nodes.map((n) =>
                n.id === nextAgent.id ? { ...n, status: 'active' as const } : n
              ),
            };
          }
          return { ...task, status: 'completed' as const };
        }
        return {
          ...task,
          agents: task.agents.map((a) => {
            if (a.status !== 'running') return a;
            const newTokensIn = a.tokens_in + Math.floor(Math.random() * 200);
            const newTokensOut = a.tokens_out + Math.floor(Math.random() * 300);
            const isDone = Math.random() > 0.92;
            return {
              ...a,
              tokens_in: newTokensIn,
              tokens_out: newTokensOut,
              latency_ms: a.latency_ms + 300,
              cost_usd: (newTokensIn + newTokensOut) * 0.0000003,
              status: isDone ? ('completed' as const) : ('running' as const),
            };
          }),
          nodes: task.nodes.map((n) => {
            const agent = task.agents.find((a) => a.id === n.id);
            if (!agent) return n;
            if (agent.status === 'running' && Math.random() > 0.92) return { ...n, status: 'completed' as const };
            return n;
          }),
          total_latency: task.total_latency + 0.3,
          total_cost: task.total_cost + 0.0001,
          updated_at: Date.now(),
        };
      })
    );
  }, []);

  const startSimulation = () => {
    setIsSimulating(true);
    intervalRef.current = setInterval(simulateTick, 1000);
  };

  const stopSimulation = () => {
    setIsSimulating(false);
    if (intervalRef.current) clearInterval(intervalRef.current);
  };

  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  return (
    <div className="flex flex-col h-full bg-bg text-text overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-line bg-panel/50 backdrop-blur-sm">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-lg bg-accent/10 flex items-center justify-center">
            <Network className="h-4 w-4 text-accent" />
          </div>
          <div>
            <h1 className="font-semibold text-sm">Swarm Control</h1>
            <p className="text-[10px] text-text-tertiary">LangGraph · A2A · PostgreSQL Checkpoints</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-panel-2 border border-line">
            <Activity className="h-3 w-3 text-ok animate-pulse" />
            <span className="text-[10px] font-medium">{metrics.active_tasks} active</span>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={isSimulating ? stopSimulation : startSimulation}
            className="h-7 text-[11px] gap-1"
          >
            {isSimulating ? (
              <><RefreshCw className="h-3 w-3 animate-spin" /> Stop</>
            ) : (
              <><Play className="h-3 w-3" /> Simulate</>
            )}
          </Button>
        </div>
      </div>

      {/* Main content grid */}
      <div className="flex-1 overflow-hidden grid grid-cols-[280px_1fr_300px] gap-0">
        {/* Left: Task queue + metrics */}
        <div className="flex flex-col h-full border-r border-line overflow-hidden">
          <SwarmMetricsPanel metrics={metrics} />
          <div className="flex-1 overflow-hidden">
            <TaskQueue tasks={tasks} selectedId={selectedTaskId} onSelect={setSelectedTaskId} />
          </div>
        </div>

        {/* Center: LangGraph canvas */}
        <div className="flex flex-col h-full overflow-hidden">
          <div className="flex items-center justify-between px-4 py-2 border-b border-line">
            <div className="flex items-center gap-2">
              <GitBranch className="h-3.5 w-3.5 text-accent" />
              <span className="text-xs font-medium">Execution Graph</span>
            </div>
            <div className="flex items-center gap-3 text-[10px] text-text-tertiary">
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-ok" /> Completed
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-accent animate-pulse" /> Active
              </span>
              <span className="flex items-center gap-1">
                <span className="h-2 w-2 rounded-full bg-warn" /> Pending
              </span>
            </div>
          </div>
          <div className="flex-1 overflow-hidden relative">
            <AnimatePresence mode="wait">
              {selectedTask && (
                <motion.div
                  key={selectedTask.id}
                  initial={{ opacity: 0, scale: 0.98 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.3 }}
                  className="h-full"
                >
                  <LangGraphCanvas nodes={selectedTask.nodes} edges={selectedTask.edges} />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Right: Agent cards + checkpoints */}
        <div className="flex flex-col h-full border-l border-line overflow-hidden">
          <div className="flex-1 overflow-hidden">
            <AgentStatusCards agents={selectedTask?.agents ?? []} />
          </div>
          <div className="h-48 border-t border-line overflow-hidden">
            <CheckpointTimeline checkpoints={selectedTask?.checkpoints ?? []} />
          </div>
        </div>
      </div>
    </div>
  );
}
