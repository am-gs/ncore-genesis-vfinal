'use client';
import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Button } from '@/components/ui/Button';
import { GitBranch, Plus, Clock, Play, Pause, RotateCcw, Trash2, Zap } from 'lucide-react';

interface Task {
  id: string;
  name: string;
  status: 'pending' | 'planning' | 'running' | 'paused' | 'completed' | 'failed' | 'retrying';
  agent: string;
  progress: number;
  subtasks: number;
  created: string;
  updated: string;
  latency: number;
}

const mockTasks: Task[] = [
  { id: 'task-001', name: 'Research competitor pricing', status: 'running', agent: 'research-agent', progress: 67, subtasks: 4, created: '2m ago', updated: '10s ago', latency: 3400 },
  { id: 'task-002', name: 'Generate marketing copy', status: 'completed', agent: 'copy-agent', progress: 100, subtasks: 2, created: '15m ago', updated: '12m ago', latency: 2100 },
  { id: 'task-003', name: 'Build API integration', status: 'failed', agent: 'code-agent', progress: 45, subtasks: 3, created: '30m ago', updated: '28m ago', latency: 8900 },
  { id: 'task-004', name: 'Audit security posture', status: 'planning', agent: 'security-agent', progress: 10, subtasks: 0, created: '1m ago', updated: '1m ago', latency: 0 },
  { id: 'task-005', name: 'Data pipeline ETL', status: 'retrying', agent: 'data-agent', progress: 23, subtasks: 1, created: '45m ago', updated: '5m ago', latency: 12000 },
  { id: 'task-006', name: 'Write test coverage', status: 'paused', agent: 'code-agent', progress: 78, subtasks: 2, created: '1h ago', updated: '20m ago', latency: 5600 },
];

function statusColor(s: Task['status']) {
  switch (s) {
    case 'completed': return 'ok';
    case 'running': return 'cyan';
    case 'planning': return 'accent';
    case 'paused': return 'warn';
    case 'failed': return 'bad';
    case 'retrying': return 'warn';
    case 'pending': return 'muted';
  }
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<Task[]>(mockTasks);
  const [filter, setFilter] = useState<string>('all');

  const filtered = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.08)] via-[rgba(6,182,212,0.04)] to-[rgba(99,102,241,0.06)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient">Task Execution</h1>
            <p className="mt-1 text-xs text-muted">Cognitive infrastructure &middot; Durable execution &middot; Branching trajectories</p>
          </div>
          <div className="flex items-center gap-3">
            <Badge color="ok">{tasks.filter(t => t.status === 'completed').length} done</Badge>
            <Badge color="cyan">{tasks.filter(t => t.status === 'running').length} active</Badge>
            <Button variant="primary"><Plus className="h-4 w-4 mr-1" /> New Task</Button>
          </div>
        </div>
      </div>

      <div className="flex gap-2">
        {['all', 'running', 'planning', 'completed', 'failed', 'paused', 'retrying'].map(f => (
          <button key={f} onClick={() => setFilter(f)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all capitalize ${
              filter === f ? 'bg-gradient-to-r from-violet-500/15 to-indigo-500/10 text-violet-300 border border-violet-500/20' : 'text-muted hover:text-text hover:bg-white/[0.03]'
            }`}
          >
            {f === 'all' ? `All (${tasks.length})` : `${f} (${tasks.filter(t => t.status === f).length})`}
          </button>
        ))}
      </div>

      <div className="grid gap-3">
        {filtered.map(task => (
          <Link key={task.id} href={`/tasks/${task.id}/`} className="block">
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
                        {task.subtasks > 0 && (
                          <span className="flex items-center gap-1 text-xs text-muted">
                            <GitBranch className="h-3 w-3" /> {task.subtasks} subtasks
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
                      <div className="flex items-center gap-1"><Clock className="h-3 w-3" /> {task.latency > 0 ? `${(task.latency / 1000).toFixed(1)}s` : '—'}</div>
                      <div className="text-muted/60">{task.updated}</div>
                    </div>
                    <div className="flex gap-1">
                      {task.status === 'running' && (
                        <button className="rounded-lg p-1.5 text-muted hover:text-amber-400 hover:bg-amber-500/10 transition-all"><Pause className="h-3.5 w-3.5" /></button>
                      )}
                      {task.status === 'paused' && (
                        <button className="rounded-lg p-1.5 text-muted hover:text-emerald-400 hover:bg-emerald-500/10 transition-all"><Play className="h-3.5 w-3.5" /></button>
                      )}
                      {(task.status === 'failed' || task.status === 'retrying') && (
                        <button className="rounded-lg p-1.5 text-muted hover:text-violet-400 hover:bg-violet-500/10 transition-all"><RotateCcw className="h-3.5 w-3.5" /></button>
                      )}
                      <button className="rounded-lg p-1.5 text-muted hover:text-rose-400 hover:bg-rose-500/10 transition-all"><Trash2 className="h-3.5 w-3.5" /></button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
