'use client';
import { useState, useEffect, useCallback } from 'react';
import { useParams } from 'next/navigation';
import { motion } from 'framer-motion';
import { toast } from 'sonner';
import Link from 'next/link';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import {
  fetchTask, fetchTaskTree, pauseTask, resumeTask, retryTask, cancelTask,
  spawnSubtask, branchTask,
} from '@/lib/api';
import type { Task, PlanStep } from '@/types';
import {
  ArrowLeft, GitBranch, Play, Pause, RotateCcw, Trash2, Plus,
  Sparkles, Clock, Cpu, FileText, AlertTriangle, X, ChevronRight, FolderTree,
} from 'lucide-react';

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

function StepStatus({ s }: { s: PlanStep['status'] }) {
  const color =
    s === 'completed' ? 'text-emerald-400' :
    s === 'running' ? 'text-cyan-400' :
    s === 'failed' ? 'text-rose-400' :
    s === 'paused' ? 'text-amber-400' :
    'text-muted';
  return <span className={`text-[11px] font-medium ${color}`}>{s}</span>;
}

export default function TaskDetailClient() {
  const params = useParams<{ id: string }>();
  const id = params?.id;

  const [task, setTask] = useState<Task | null>(null);
  const [tree, setTree] = useState<Task | null>(null);
  const [loading, setLoading] = useState(true);
  const [spawnOpen, setSpawnOpen] = useState(false);
  const [branchOpen, setBranchOpen] = useState(false);
  const [spawnForm, setSpawnForm] = useState({ name: '', description: '', agent: 'research-agent' });
  const [branchForm, setBranchForm] = useState({ name: '', description: '' });

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const [t, tr] = await Promise.all([fetchTask(id), fetchTaskTree(id)]);
      setTask(t);
      setTree(tr.tree);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to load task');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (!task) return;
    if (task.status === 'running' || task.status === 'retrying' || task.status === 'planning') {
      const t = setInterval(load, 3000);
      return () => clearInterval(t);
    }
  }, [task?.status, load]);

  const handleAction = async (action: 'pause' | 'resume' | 'retry' | 'cancel') => {
    try {
      let t: Task;
      switch (action) {
        case 'pause': t = await pauseTask(id); break;
        case 'resume': t = await resumeTask(id); break;
        case 'retry': t = await retryTask(id); break;
        case 'cancel': t = await cancelTask(id); break;
      }
      setTask(t);
      toast.success(`Task ${action}d`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : `${action} failed`);
    }
  };

  const handleSpawn = async () => {
    if (!spawnForm.name.trim()) return;
    try {
      await spawnSubtask(id, spawnForm);
      toast.success('Subtask spawned');
      setSpawnOpen(false);
      setSpawnForm({ name: '', description: '', agent: 'research-agent' });
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Spawn failed');
    }
  };

  const handleBranch = async () => {
    if (!branchForm.name.trim()) return;
    try {
      await branchTask(id, branchForm);
      toast.success('Branch created');
      setBranchOpen(false);
      setBranchForm({ name: '', description: '' });
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Branch failed');
    }
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="h-32 animate-pulse bg-white/[0.02] rounded-2xl" />
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
          <div className="h-40 animate-pulse bg-white/[0.02] rounded-xl" />
          <div className="h-40 animate-pulse bg-white/[0.02] rounded-xl" />
          <div className="h-40 animate-pulse bg-white/[0.02] rounded-xl" />
        </div>
      </div>
    );
  }

  if (!task) return (
    <div className="text-center py-20">
      <AlertTriangle className="h-10 w-10 text-rose-500/40 mx-auto mb-3" />
      <div className="text-sm text-muted">Task not found</div>
    </div>
  );

  return (
    <div className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}>
        <div className="flex items-center gap-3 mb-4">
          <Link href="/tasks/" className="rounded-lg p-2 text-muted hover:text-text hover:bg-white/[0.04] transition-all">
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-lg font-bold text-gradient">{task.name}</h1>
            <p className="text-xs text-muted mt-0.5">{task.description}</p>
          </div>
        </div>
      </motion.div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-center gap-3 mb-3">
              <StatusDot ok={task.status === 'completed'} size="lg" pulse={task.status === 'running' || task.status === 'retrying'} />
              <div>
                <Badge color={statusColor(task.status)}>{task.status}</Badge>
                <div className="text-[10px] text-muted mt-0.5">{task.retries > 0 ? `${task.retries} retries` : 'No retries'}</div>
              </div>
            </div>
            <div className="w-full h-2 bg-white/[0.06] rounded-full mb-2">
              <div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-cyan-500 transition-all" style={{ width: `${task.progress}%` }} />
            </div>
            <div className="text-xs text-muted text-right">{task.progress}% complete</div>
          </CardContent>
        </Card>

        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 mb-3">
              <Cpu className="h-4 w-4 text-violet-400" />
              <span className="text-xs font-semibold text-text">Agent</span>
            </div>
            <div className="font-mono text-sm text-text">{task.agent}</div>
            <div className="text-[11px] text-muted mt-1">ID: {task.id.slice(0, 8)}</div>
            {task.parent_id && <div className="text-[11px] text-violet-400 mt-1">Parent: {task.parent_id.slice(0, 8)}</div>}
            {task.branch_from && <div className="text-[11px] text-cyan-400 mt-1">Branched from: {task.branch_from.slice(0, 8)}</div>}
          </CardContent>
        </Card>

        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-center gap-2 mb-3">
              <Clock className="h-4 w-4 text-cyan-400" />
              <span className="text-xs font-semibold text-text">Timing</span>
            </div>
            <div className="space-y-1.5 text-xs">
              <div className="flex justify-between"><span className="text-muted">Created</span><span className="font-mono text-text">{new Date(task.created_at).toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-muted">Updated</span><span className="font-mono text-text">{new Date(task.updated_at).toLocaleString()}</span></div>
              <div className="flex justify-between"><span className="text-muted">Latency</span><span className="font-mono text-text">{task.latency_ms > 0 ? `${(task.latency_ms / 1000).toFixed(1)}s` : '—'}</span></div>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="flex gap-2 flex-wrap">
        {task.status === 'running' && (
          <button onClick={() => handleAction('pause')} className="flex items-center gap-2 rounded-xl bg-amber-500/10 border border-amber-500/20 px-4 py-2 text-xs font-medium text-amber-400 hover:bg-amber-500/20 transition-all"><Pause className="h-3.5 w-3.5" /> Pause</button>
        )}
        {task.status === 'paused' && (
          <button onClick={() => handleAction('resume')} className="flex items-center gap-2 rounded-xl bg-emerald-500/10 border border-emerald-500/20 px-4 py-2 text-xs font-medium text-emerald-400 hover:bg-emerald-500/20 transition-all"><Play className="h-3.5 w-3.5" /> Resume</button>
        )}
        {(task.status === 'failed' || task.status === 'retrying') && (
          <button onClick={() => handleAction('retry')} className="flex items-center gap-2 rounded-xl bg-violet-500/10 border border-violet-500/20 px-4 py-2 text-xs font-medium text-violet-400 hover:bg-violet-500/20 transition-all"><RotateCcw className="h-3.5 w-3.5" /> Retry</button>
        )}
        {task.status !== 'cancelled' && task.status !== 'completed' && (
          <button onClick={() => handleAction('cancel')} className="flex items-center gap-2 rounded-xl bg-rose-500/10 border border-rose-500/20 px-4 py-2 text-xs font-medium text-rose-400 hover:bg-rose-500/20 transition-all"><Trash2 className="h-3.5 w-3.5" /> Cancel</button>
        )}
        <button onClick={() => setSpawnOpen(true)} className="flex items-center gap-2 rounded-xl bg-white/[0.04] border border-white/[0.06] px-4 py-2 text-xs font-medium text-muted hover:text-text hover:bg-white/[0.06] transition-all"><Plus className="h-3.5 w-3.5" /> Spawn Subtask</button>
        <button onClick={() => setBranchOpen(true)} className="flex items-center gap-2 rounded-xl bg-white/[0.04] border border-white/[0.06] px-4 py-2 text-xs font-medium text-muted hover:text-text hover:bg-white/[0.06] transition-all"><GitBranch className="h-3.5 w-3.5" /> Branch</button>
      </div>

      {task.error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-xs text-rose-300 backdrop-blur-md">
          <div className="flex items-center gap-2"><AlertTriangle className="h-3.5 w-3.5" />{task.error}</div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Card glow>
          <CardHeader><CardTitle>Plan Steps</CardTitle></CardHeader>
          <CardContent>
            {task.plan.length === 0 ? (
              <div className="text-xs text-muted py-4">No plan steps defined</div>
            ) : (
              <div className="space-y-2">
                {task.plan.map((step, idx) => (
                  <div key={step.id} className="flex items-start gap-3 rounded-lg border border-white/[0.04] bg-white/[0.02] px-3 py-2.5">
                    <div className="mt-0.5 text-[10px] font-mono text-muted w-4">{idx + 1}</div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <StepStatus s={step.status} />
                        {step.agent && <span className="text-[10px] text-muted font-mono">{step.agent}</span>}
                      </div>
                      <div className="text-xs text-text mt-0.5">{step.description}</div>
                      {step.output && <div className="text-[10px] text-muted mt-1 line-clamp-2">{step.output}</div>}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Card glow>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FolderTree className="h-4 w-4 text-violet-400" />
              <CardTitle>Execution Tree</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {tree && renderTree(tree, 0)}
            {(!tree || tree.subtasks.length === 0) && (
              <div className="text-xs text-muted py-4">No subtasks yet</div>
            )}
          </CardContent>
        </Card>
      </div>

      {task.artifacts.length > 0 && (
        <Card glow>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-cyan-400" />
              <CardTitle>Artifacts</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {task.artifacts.map(a => (
                <div key={a.name} className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-xs">
                  <div className="font-medium text-text">{a.name}</div>
                  <div className="text-muted/60 mt-0.5">{a.type} &middot; {new Date(a.created_at).toLocaleTimeString()}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {task.memory_refs.length > 0 && (
        <Card glow>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-400" />
              <CardTitle>Memory References</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {task.memory_refs.map(ref => (
                <Link key={ref} href="/mem0/" className="rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5 text-xs text-muted hover:text-violet-300 hover:border-violet-500/20 transition-all font-mono">
                  {ref.slice(0, 12)}...
                </Link>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Spawn Modal */}
      {spawnOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setSpawnOpen(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-strong rounded-2xl p-6 w-full max-w-md border border-white/[0.06]" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-text">Spawn Subtask</h2>
              <button onClick={() => setSpawnOpen(false)} className="text-muted hover:text-text"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-3">
              <input value={spawnForm.name} onChange={e => setSpawnForm(p => ({ ...p, name: e.target.value }))} placeholder="Subtask name" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
              <input value={spawnForm.description} onChange={e => setSpawnForm(p => ({ ...p, description: e.target.value }))} placeholder="Description" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
              <select value={spawnForm.agent} onChange={e => setSpawnForm(p => ({ ...p, agent: e.target.value }))} className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text outline-none focus:border-violet-500/30">
                <option value="research-agent">research-agent</option>
                <option value="code-agent">code-agent</option>
                <option value="security-agent">security-agent</option>
                <option value="data-agent">data-agent</option>
              </select>
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setSpawnOpen(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-white/[0.04] transition-all">Cancel</button>
              <button onClick={handleSpawn} className="rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-1.5 text-xs text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all">Spawn</button>
            </div>
          </motion.div>
        </div>
      )}

      {/* Branch Modal */}
      {branchOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm" onClick={() => setBranchOpen(false)}>
          <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="glass-strong rounded-2xl p-6 w-full max-w-md border border-white/[0.06]" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold text-text">Branch Trajectory</h2>
              <button onClick={() => setBranchOpen(false)} className="text-muted hover:text-text"><X className="h-4 w-4" /></button>
            </div>
            <div className="space-y-3">
              <input value={branchForm.name} onChange={e => setBranchForm(p => ({ ...p, name: e.target.value }))} placeholder="Branch name" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
              <input value={branchForm.description} onChange={e => setBranchForm(p => ({ ...p, description: e.target.value }))} placeholder="Description" className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30" />
            </div>
            <div className="mt-4 flex justify-end gap-2">
              <button onClick={() => setBranchOpen(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-white/[0.04] transition-all">Cancel</button>
              <button onClick={handleBranch} className="rounded-lg bg-gradient-to-r from-cyan-600 to-indigo-600 px-4 py-1.5 text-xs text-white shadow-lg shadow-cyan-500/20 hover:shadow-cyan-500/30 transition-all">Branch</button>
            </div>
          </motion.div>
        </div>
      )}
    </div>
  );
}

interface TreeNode extends Task {
  children?: TreeNode[];
}

function renderTree(t: TreeNode, depth: number): React.ReactNode {
  return (
    <div key={t.id} className="space-y-1">
      <div className="flex items-center gap-2 text-xs" style={{ paddingLeft: depth * 20 }}>
        <ChevronRight className="h-3 w-3 text-muted" />
        <StatusDot ok={t.status === 'completed'} size="sm" pulse={t.status === 'running'} />
        <Link href={`/tasks/${t.id}/`} className="text-text hover:text-violet-300 transition-colors truncate max-w-[200px]">{t.name}</Link>
        <Badge color={t.status === 'completed' ? 'ok' : t.status === 'running' ? 'cyan' : t.status === 'failed' ? 'bad' : 'muted'} className="text-[10px]">{t.status}</Badge>
        <span className="text-muted/60 font-mono">{t.progress}%</span>
      </div>
      {t.children && t.children.length > 0 && (
        <div className="mt-1">
          {t.children.map(child => renderTree(child, depth + 1))}
        </div>
      )}
    </div>
  );
}
