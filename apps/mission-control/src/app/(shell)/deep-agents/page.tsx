'use client';
import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { fetchTasks, createTask } from '@/lib/api';
import type { Task } from '@/types';
import {
  GitBranch, Cpu, Zap, Play, ArrowRight, Sparkles, Layers,
  Terminal, Shield, Clock, RotateCcw, Plus
} from 'lucide-react';

export default function DeepAgentsPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      const r = await fetchTasks(undefined, 20);
      setTasks(r.tasks || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 5000); return () => clearInterval(t); }, [load]);

  const spawnDemo = async () => {
    try {
      const t = await createTask({
        name: 'Deep Agents Orchestration Demo',
        description: 'Demonstrates recursive planning, subagent spawning, and self-healing execution.',
        agent: 'research-agent',
        plan_steps: [
          { description: 'Research target domain' },
          { description: 'Draft execution plan' },
          { description: 'Spawn code-agent for implementation' },
          { description: 'Validate outputs with browser grounding' },
        ],
      });
      setTasks(prev => [t, ...prev]);
      toast.success('Demo task spawned with 4 plan steps');
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Spawn failed');
    }
  };

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.1)] via-[rgba(6,182,212,0.05)] to-[rgba(99,102,241,0.08)] p-6 backdrop-blur-xl"
      >
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 via-indigo-600 to-cyan-500 shadow-lg shadow-violet-500/20">
                <Zap className="h-4 w-4 text-white" />
              </div>
              <h1 className="text-lg font-bold text-gradient">Deep Agents</h1>
            </div>
            <p className="text-xs text-muted mt-1">LangChain Deep Agents SDK integration &middot; Recursive planning &middot; Subagent spawning &middot; Self-healing</p>
          </div>
          <Button variant="primary" onClick={spawnDemo}><Play className="h-4 w-4 mr-1.5" /> Run Demo</Button>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Active Tasks</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{tasks.filter(t => t.status === 'running' || t.status === 'planning' || t.status === 'retrying').length}</div>
            </div>
            <div className="rounded-xl bg-violet-500/10 p-2.5"><Cpu className="h-5 w-5 text-violet-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Completed</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{tasks.filter(t => t.status === 'completed').length}</div>
            </div>
            <div className="rounded-xl bg-emerald-500/10 p-2.5"><Sparkles className="h-5 w-5 text-emerald-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Branches</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{tasks.filter(t => t.branch_from).length}</div>
            </div>
            <div className="rounded-xl bg-cyan-500/10 p-2.5"><GitBranch className="h-5 w-5 text-cyan-400" /></div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5">
          <div className="flex items-start justify-between">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Subtasks</div>
              <div className="mt-2 text-3xl font-bold tracking-tight">{tasks.reduce((a, t) => a + t.subtasks.length, 0)}</div>
            </div>
            <div className="rounded-xl bg-amber-500/10 p-2.5"><Layers className="h-5 w-5 text-amber-400" /></div>
          </div>
        </CardContent></Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card glow>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Terminal className="h-4 w-4 text-violet-400" />
              <CardTitle>SDK Patterns</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 text-sm">
              {[
                { label: 'Recursive Planning', desc: 'Auto-decompose tasks into plan steps with dependency tracking', icon: Layers },
                { label: 'Subagent Spawning', desc: 'Spawn specialized agents (research, code, security) from parent tasks', icon: Cpu },
                { label: 'Branching Trajectories', desc: 'Create A/B execution paths from any task step', icon: GitBranch },
                { label: 'Self-Healing', desc: 'Auto-retry failed tasks with exponential backoff and state recovery', icon: RotateCcw },
                { label: 'Browser Grounding', desc: 'Validate outputs against live web pages with screenshot verification', icon: Shield },
              ].map((p, i) => (
                <motion.div
                  key={p.label}
                  initial={{ opacity: 0, x: -12 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.08, duration: 0.35 }}
                  className="flex items-start gap-3 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2.5"
                >
                  <div className="rounded-lg bg-white/[0.04] p-1.5 mt-0.5"><p.icon className="h-3.5 w-3.5 text-muted" /></div>
                  <div>
                    <div className="text-xs font-medium text-text">{p.label}</div>
                    <div className="text-[11px] text-muted mt-0.5">{p.desc}</div>
                  </div>
                </motion.div>
              ))}
            </div>
          </CardContent>
        </Card>

        <Card glow>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-cyan-400" />
              <CardTitle>Recent Activity</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {loading && tasks.length === 0 ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => <div key={i} className="h-10 animate-pulse bg-white/[0.02] rounded-lg" />)}
              </div>
            ) : tasks.length === 0 ? (
              <div className="text-center py-8">
                <Zap className="h-8 w-8 text-violet-500/20 mx-auto mb-2" />
                <div className="text-xs text-muted">No tasks yet</div>
                <div className="text-[10px] text-muted/60 mt-1">Run the demo to see Deep Agents in action</div>
              </div>
            ) : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {tasks.slice(0, 15).map(task => (
                  <div key={task.id} className="flex items-center justify-between rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2 text-xs">
                    <div className="flex items-center gap-2 min-w-0">
                      <Badge color={task.status === 'completed' ? 'ok' : task.status === 'running' ? 'cyan' : task.status === 'failed' ? 'bad' : 'muted'} className="text-[10px] shrink-0">{task.status}</Badge>
                      <span className="truncate text-text max-w-[180px]">{task.name}</span>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <span className="text-muted font-mono">{task.progress}%</span>
                      {task.subtasks.length > 0 && <span className="text-muted/60 flex items-center gap-1"><GitBranch className="h-3 w-3" />{task.subtasks.length}</span>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <Card glow>
        <CardHeader><CardTitle>Execution Architecture</CardTitle></CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge color="accent">User Prompt</Badge>
            <ArrowRight className="h-3 w-3 text-muted" />
            <Badge color="ok">Plan Tool</Badge>
            <ArrowRight className="h-3 w-3 text-muted" />
            <Badge color="cyan">Spawn Subagent</Badge>
            <ArrowRight className="h-3 w-3 text-muted" />
            <Badge color="warn">Browser Grounding</Badge>
            <ArrowRight className="h-3 w-3 text-muted" />
            <Badge color="accent">Artifact Store</Badge>
            <ArrowRight className="h-3 w-3 text-muted" />
            <Badge color="ok">Mem0 Memory</Badge>
          </div>
          <p className="mt-4 text-xs text-muted leading-relaxed">
            The Deep Agents SDK execution loop: user input is recursively planned into steps,
            each step may spawn a specialized subagent, outputs are grounded via browser,
            artifacts are stored to the filesystem backend, and all state is persisted to mem0 memory.
            Failed steps auto-retry with exponential backoff. Branching creates parallel trajectories for A/B testing.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
