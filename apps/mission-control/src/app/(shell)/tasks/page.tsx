'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Button } from '@/components/ui/Button';
import {
  fetchTasks, createTask, pauseTask, resumeTask, retryTask, cancelTask,
} from '@/lib/api';
import type { Task } from '@/types';
import { GitBranch, Plus, Clock, Play, Pause, RotateCcw, Trash2, Zap, X } from 'lucide-react';

const statuses = ['all', 'pending', 'planning', 'running', 'paused', 'completed', 'failed', 'retrying'] as const;
type StatusFilter = typeof statuses[number];

function statusColor(s: Task['status']) {
  switch (s) {
    case 'completed': return 'ok';
    case 'running': return 'cyan';
    case 'planning': return 'accent';
    case 'paused': return 'warn';
    case 'failed': return 'bad';
    case 'retrying': return 'warn';
    case 'pending': return 'muted';
    case 'cancelled': return 'muted';
    default: return 'muted';
  }
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [filter, setFilter] = useState<StatusFilter>('all');
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [newTask, setNewTask] = useState({ name: '', description: '', agent: 'research-agent' });

  const load = useCallback(async () => {
    try {
      const r = await fetchTasks(filter === 'all' ? undefined : filter, 50);
      setTasks(r.tasks || []);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to load tasks');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const t = setInterval(load, 3000);
    return () => clearInterval(t);
  }, [load]);

  const handleCreate = async () => {
    if (!newTask.name.trim()) return;
    try {
      const t = await createTask(newTask);
      setTasks(prev => [t, ...prev]);
      toast.success(`Task "${t.name}" created`);
      setModalOpen(false);
      setNewTask({ name: '', description: '', agent: 'research-agent' });
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Create failed');
    }
  };

  const handleAction = async (id: string, action: 'pause' | 'resume' | 'retry' | 'cancel') => {
    try {
      let t: Task;
      switch (action) {
        case 'pause': t = await pauseTask(id); break;
        case 'resume': t = await resumeTask(id); break;
        case 'retry': t = await retryTask(id); break;
        case 'cancel': t = await cancelTask(id); break;
      }
      setTasks(prev => prev.map(x => x.id === id ? t : x));
      toast.success(`Task ${action}d`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `${action} failed`);
    }
  };

  const filtered = tasks;
  const counts = Object.fromEntries(statuses.map(s => [s, s === 'all' ? tasks.length : tasks.filter(t => t.status === s).length]));

  return (
    <div className="space-y-6">
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.08)] via-[rgba(6,182,212,0.04)] to-[rgba(99,102,241,0.06)] p-6 backdrop-blur-xl"
      >
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient">Task Execution</h1>
            <p className="mt-1 text-xs text-muted">Cognitive infrastructure &middot; Durable execution &middot; Branching trajectories</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge color="ok">{counts.completed} done</Badge>
            <Badge color="cyan">{counts.running} active</Badge>
            <Button variant="primary" onClick={() => setModalOpen(true)}><Plus className="h-4 w-4 mr-1" /> New Task</Button>
          </div>
        </div>
      </motion.div>

      <div className="flex flex-wrap gap-2">
        {statuses.map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all capitalize ${
              filter === f ? 'bg-gradient-to-r from-violet-500/15 to-indigo-500/10 text-violet-300 border border-violet-500/20' : 'text-muted hover:text-text hover:bg-white/[0.03]'
            }`}
          >
            {f === 'all' ? `All (${counts[f]})` : `${f} (${counts[f]})`}
          </button>
        ))}
      </div>

      {loading && tasks.length === 0 && (
        <div className="grid gap-3">
          {Array.from({ length: 5 }).map((_, i) => (
            <Card key={i} className="h-24 animate-pulse bg-white/[0.02]" />
          ))}
        </div>
      )}

      <div className="grid gap-3">
        {filtered.map((task, i) => (
          <motion.div
            key={task.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.04, duration: 0.35, ease: "easeOut" }}
          >
            <Link href={`/tasks/${task.id}/`} className="block">
              <Card glow className="hover:bg-white/[0.04] transition-all cursor-pointer group">
                <CardContent className="pt-5">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <StatusDot ok={task.status === 'completed'} size="md" pulse={task.status === 'running' || task.status === 'retrying'} />
                      <div>
                        <div className="text-sm font-semibold text-text group-hover:text-violet-300 transition-colors">{task.name}</div>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge color={statusColor(task.status)}>{task.status}</Badge>
                          <span className="text-xs text-muted font-mono">{task.agent}</span>
                          {task.subtasks.length > 0 && (
                            <span className="flex items-center gap-1 text-xs text-muted">
                              <GitBranch className="h-3 w-3" /> {task.subtasks.length} subtasks
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 text-xs text-muted">
                      <div className="text-right">
                        <div className="font-mono">{task.progress}%</div>
                        <div className="w-24 h-1 bg-white/[0.06] rounded-full mt-1">
                          <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 transition-all" style={{ width: `${task.progress}%` }} />
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="flex items-center gap-1"><Clock className="h-3 w-3" /> {task.latency_ms > 0 ? `${(task.latency_ms / 1000).toFixed(1)}s` : '—'}</div>
                        <div className="text-muted/60">{new Date(task.updated_at).toLocaleTimeString()}</div>
                      </div>
                      <div className="flex gap-1" onClick={e => e.preventDefault()}>
                        {task.status === 'running' && (
                          <button onClick={() => handleAction(task.id, 'pause')} className="rounded-lg p-1.5 text-muted hover:text-amber-400 hover:bg-amber-500/10 transition-all"><Pause className="h-3.5 w-3.5" /></button>
                        )}
                        {task.status === 'paused' && (
                          <button onClick={() => handleAction(task.id, 'resume')} className="rounded-lg p-1.5 text-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all"><Play className="h-3.5 w-3.5" /></button>
                        )}
                        {(task.status === 'failed' || task.status === 'retrying') && (
                          <button onClick={() => handleAction(task.id, 'retry')} className="rounded-lg p-1.5 text-muted hover:text-violet-400 hover:bg-violet-500/10 transition-all"><RotateCcw className="h-3.5 w-3.5" /></button>
                        )}
                        <button onClick={() => handleAction(task.id, 'cancel')} className="rounded-lg p-1.5 text-muted hover:text-rose-400 hover:bg-rose-500/10 transition-all"><Trash2 className="h-3.5 w-3.5" /></button>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </Link>
          </motion.div>
        ))}
      </div>

      {filtered.length === 0 && !loading && (
        <div className="text-center py-20">
          <Zap className="h-12 w-12 text-violet-500/20 mx-auto mb-3" />
          <div className="text-sm text-muted">No tasks found</div>
          <div className="text-xs text-muted/60 mt-1">Create a new task to start execution</div>
        </div>
      )}

      {modalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setModalOpen(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-strong rounded-2xl p-6 w-full max-w-md border border-white/[0.06]" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-text">New Task</h2>
              <button onClick={() => setModalOpen(false)} className="text-muted hover:text-text"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-3">
              <input value={newTask.name} onChange={e => setNewTask(p => ({ ...p, name: e.target.value }))} placeholder="Task name" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
              <input value={newTask.description} onChange={e => setNewTask(p => ({ ...p, description: e.target.value }))} placeholder="Description" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
              <select value={newTask.agent} onChange={e => setNewTask(p => ({ ...p, agent: e.target.value }))} className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text outline-none focus:border-violet-500/30">
                <option value="research-agent">research-agent</option>
                <option value="code-agent">code-agent</option>
                <option value="security-agent">security-agent</option>
                <option value="data-agent">data-agent</option>
                <option value="copy-agent">copy-agent</option>
              </select>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setModalOpen(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-white/[0.04] transition-all">Cancel</button>
              <button onClick={handleCreate} className="rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-1.5 text-xs text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all">Create</button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}
