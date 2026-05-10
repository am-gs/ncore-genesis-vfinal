'use client';
import { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { StatusDot } from '@/components/ui/StatusDot';
import { Sparkline } from '@/components/ui/Sparkline';
import { fetchHealth, fetchRuns, fetchTasks, createTask, executeTask, restartService } from '@/lib/api';
import type { Service, Run, Task } from '@/types';
import { ExternalLink, RotateCcw, Clock, TrendingUp, AlertTriangle, Shield, Terminal, Rocket, X, Plus, Bot } from 'lucide-react';
import { toast } from 'sonner';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';

export default function DashboardPage() {
  const [services, setServices] = useState<Service[]>([]);
  const [runs, setRuns] = useState<Run[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ name: '', description: '', agent: 'code-agent' });

  const load = useCallback(async () => {
    try {
      const [h, r, t] = await Promise.all([
        fetchHealth(),
        fetchRuns(20),
        fetchTasks(undefined, 100),
      ]);
      setServices(h.services);
      setRuns(r.runs || []);
      setTasks(t.tasks || []);
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { const t = setInterval(load, 10000); return () => clearInterval(t); }, [load]);

  const healthy = services.filter((s) => s.ok).length;
  const total = services.length;
  const sparkData = runs.slice(-20).map((r) => r.latency_ms);

  const runningTasks = tasks.filter((t) => t.status === 'running' || t.status === 'planning');
  const recentTask = runningTasks.length > 0 ? runningTasks[0] : tasks.filter((t) => t.manus_state).sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];

  const handleCreateAndExecute = async () => {
    if (!form.name.trim()) return;
    setCreating(true);
    try {
      const task = await createTask({
        name: form.name,
        description: form.description,
        agent: form.agent,
      });
      await executeTask(task.id);
      toast.success('Task created and Manus execution started');
      setModalOpen(false);
      setForm({ name: '', description: '', agent: 'code-agent' });
      load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="space-y-6 animate-slide-up">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(139,92,246,0.1)] via-[rgba(6,182,212,0.05)] to-[rgba(99,102,241,0.08)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-violet-500/10 blur-3xl" />
        <div className="absolute -left-10 bottom-0 h-32 w-32 rounded-full bg-cyan-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient">Sovereign Mission Control</h1>
            <p className="mt-1 text-xs text-muted">Local high-compliance agentic stack &middot; Real-time monitoring</p>
          </div>
          <div className="flex items-center gap-2">
            <StatusDot ok={healthy === total && total > 0} size="lg" />
            <span className="text-sm font-medium text-text">{healthy === total && total > 0 ? 'All Systems Nominal' : `${total - healthy} Issues`}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Services</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{healthy}<span className="text-lg text-muted/60">/{total}</span></div>
                <div className="mt-1 text-xs text-emerald-400">{((healthy / (total || 1)) * 100).toFixed(0)}% uptime</div>
              </div>
              <div className="rounded-xl bg-emerald-500/10 p-2.5"><Shield className="h-5 w-5 text-emerald-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Total Calls</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{runs.length.toLocaleString()}</div>
                <Sparkline data={sparkData} height={30} color="#8b5cf6" />
              </div>
              <div className="rounded-xl bg-violet-500/10 p-2.5"><TrendingUp className="h-5 w-5 text-violet-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Avg Latency</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">
                  {runs.length > 0 ? Math.round(runs.reduce((a, r) => a + r.latency_ms, 0) / runs.length) : 0}ms
                </div>
              </div>
              <div className="rounded-xl bg-cyan-500/10 p-2.5"><Clock className="h-5 w-5 text-cyan-400" /></div>
            </div>
          </CardContent>
        </Card>
        <Card glow>
          <CardContent className="pt-5">
            <div className="flex items-start justify-between">
              <div>
                <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Refusals</div>
                <div className="mt-2 text-3xl font-bold tracking-tight">{runs.filter((r) => r.refusal_intercepted).length}</div>
              </div>
              <div className="rounded-xl bg-amber-500/10 p-2.5"><AlertTriangle className="h-5 w-5 text-amber-400" /></div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Active Manus Sessions + Quick Action */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <Card glow className="lg:col-span-2">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Terminal className="h-4 w-4 text-emerald-400" />
                <CardTitle>Active Manus Sessions</CardTitle>
              </div>
              <Badge color="cyan">{runningTasks.length} running</Badge>
            </div>
          </CardHeader>
          <CardContent>
            {runningTasks.length === 0 && !recentTask ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Bot className="h-10 w-10 text-muted/20 mb-2" />
                <div className="text-xs text-muted/60">No active Manus sessions</div>
              </div>
            ) : (
              <div className="space-y-3">
                {runningTasks.slice(0, 5).map((t) => (
                  <Link
                    key={t.id}
                    href={`/tasks/${t.id}/`}
                    className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-all"
                  >
                    <StatusDot ok={t.status === 'running'} size="sm" pulse={t.status === 'running'} />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-text truncate">{t.name}</div>
                      <div className="text-[10px] text-muted font-mono">{t.agent} &middot; {t.progress}%</div>
                    </div>
                    <Badge color={t.status === 'running' ? 'cyan' : 'accent'} className="text-[10px]">{t.status}</Badge>
                  </Link>
                ))}
                {recentTask && !runningTasks.find((t) => t.id === recentTask.id) && (
                  <Link
                    href={`/tasks/${recentTask.id}/`}
                    className="flex items-center gap-3 rounded-xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 hover:bg-white/[0.04] transition-all"
                  >
                    <StatusDot ok={recentTask.status === 'completed'} size="sm" />
                    <div className="flex-1 min-w-0">
                      <div className="text-xs font-medium text-text truncate">{recentTask.name}</div>
                      <div className="text-[10px] text-muted font-mono">{recentTask.agent} &middot; last active</div>
                    </div>
                    <Badge color="muted" className="text-[10px]">{recentTask.status}</Badge>
                  </Link>
                )}
              </div>
            )}
            {/* Mini terminal preview of most recent task */}
            {recentTask && (
              <div className="mt-3 rounded-xl border border-white/[0.04] bg-[#070a12] p-3 font-mono text-[11px] text-text-secondary overflow-x-auto">
                <span className="text-muted">$ </span>
                <span className="text-emerald-400">task</span>{" "}
                <span className="text-cyan-400">{recentTask.name}</span>
                <br />
                <span className="text-muted">status: </span>
                <span className={recentTask.status === 'running' ? 'text-cyan-400' : recentTask.status === 'completed' ? 'text-emerald-400' : 'text-amber-400'}>{recentTask.status}</span>
                <span className="text-muted">, progress: </span>
                <span className="text-violet-400">{recentTask.progress}%</span>
                {recentTask.error && (
                  <>
                    <br />
                    <span className="text-rose-400">{recentTask.error}</span>
                  </>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        <Card glow>
          <CardHeader>
            <CardTitle>Quick Actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <button
              onClick={() => setModalOpen(true)}
              className="w-full flex items-center gap-2 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-3 text-xs font-medium text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all"
            >
              <Rocket className="h-4 w-4" /> New Autonomous Task
            </button>
            <Link
              href="/terminal/"
              className="w-full flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-xs font-medium text-muted hover:text-text hover:bg-white/[0.06] transition-all"
            >
              <Terminal className="h-4 w-4" /> Open Terminal
            </Link>
            <Link
              href="/browser/"
              className="w-full flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 text-xs font-medium text-muted hover:text-text hover:bg-white/[0.06] transition-all"
            >
              <ExternalLink className="h-4 w-4" /> Open Browser
            </Link>
          </CardContent>
        </Card>
      </div>

      {error && (
        <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-300 backdrop-blur-md">
          <div className="flex items-center gap-2"><AlertTriangle className="h-4 w-4" />{error}</div>
        </div>
      )}

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text tracking-tight">Service Health</h2>
        {loading ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {Array.from({ length: 6 }).map((_, i) => <Card key={i} className="h-32 animate-pulse bg-white/[0.02]" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {services.map((svc) => (
              <Card key={svc.name} glow>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <CardTitle>{svc.name}</CardTitle>
                    <StatusDot ok={svc.ok} />
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="mb-2 text-xs text-muted line-clamp-1">{svc.detail}</div>
                  <div className="flex items-center gap-2">
                    <Badge color={svc.ok ? 'ok' : 'bad'}>{svc.ok ? 'Healthy' : 'Down'}</Badge>
                    <span className="text-xs font-mono text-muted">{svc.latency_ms}ms</span>
                  </div>
                  <div className="mt-3 flex gap-2">
                    {svc.link && (
                      <a href={svc.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all">
                        <ExternalLink className="h-3 w-3" /> Open
                      </a>
                    )}
                    <button onClick={async () => { await restartService(svc.name.toLowerCase().replace(/\s+/g, '-')); load(); }}
                      className="inline-flex items-center gap-1 rounded-lg border border-white/[0.06] bg-white/[0.03] px-2.5 py-1.5 text-xs text-muted hover:text-text hover:bg-white/[0.06] transition-all"
                    >
                      <RotateCcw className="h-3 w-3" /> Restart
                    </button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      <div>
        <h2 className="mb-3 text-sm font-semibold text-text tracking-tight">Recent Runs</h2>
        <Card glow>
          <CardContent className="pt-5">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-white/[0.06] text-left text-[11px] text-muted uppercase tracking-wider">
                    <th className="pb-3 pr-4 font-semibold">Time</th>
                    <th className="pb-3 pr-4 font-semibold">Task</th>
                    <th className="pb-3 pr-4 font-semibold">Provider</th>
                    <th className="pb-3 pr-4 font-semibold">Model</th>
                    <th className="pb-3 pr-4 font-semibold">Fallback</th>
                    <th className="pb-3 pr-4 font-semibold">Latency</th>
                    <th className="pb-3 font-semibold">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.slice(0, 12).map((run) => (
                    <tr key={`${run.ts}-${run.task_id}`} className="border-b border-white/[0.03] text-xs transition-colors hover:bg-white/[0.02]">
                      <td className="py-3 pr-4 font-mono text-muted">{new Date(run.ts * 1000).toLocaleTimeString()}</td>
                      <td className="py-3 pr-4 truncate max-w-[100px]">{run.task_id}</td>
                      <td className="py-3 pr-4"><Badge color={run.provider === 'remote' ? 'accent' : run.provider === 'policy' ? 'warn' : 'muted'}>{run.provider}</Badge></td>
                      <td className="py-3 pr-4 font-mono text-muted">{run.model}</td>
                      <td className="py-3 pr-4 text-muted">{run.fallback_reason !== 'none' ? run.fallback_reason : '—'}</td>
                      <td className="py-3 pr-4 font-mono">{run.latency_ms}ms</td>
                      <td className="py-3">
                        <Badge color={run.completion_status === 'completed' ? 'ok' : run.completion_status === 'refused' ? 'warn' : 'bad'}>{run.completion_status}</Badge>
                      </td>
                    </tr>
                  ))}
                  {runs.length === 0 && <tr><td colSpan={7} className="py-10 text-center text-muted text-sm">No runs yet</td></tr>}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* New Autonomous Task Modal */}
      <AnimatePresence>
        {modalOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
            onClick={() => setModalOpen(false)}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="glass-strong rounded-2xl p-6 w-full max-w-md border border-white/[0.06]"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Rocket className="h-5 w-5 text-violet-400" />
                  <h2 className="text-sm font-bold text-text">New Autonomous Task</h2>
                </div>
                <button onClick={() => setModalOpen(false)} className="text-muted hover:text-text">
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="space-y-3">
                <input
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Task name"
                  className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30"
                />
                <textarea
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                  placeholder="What should the agent do?"
                  rows={3}
                  className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text placeholder-muted/40 outline-none focus:border-violet-500/30 resize-none"
                />
                <select
                  value={form.agent}
                  onChange={(e) => setForm((p) => ({ ...p, agent: e.target.value }))}
                  className="w-full rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-2 text-sm text-text outline-none focus:border-violet-500/30"
                >
                  <option value="code-agent">code-agent</option>
                  <option value="research-agent">research-agent</option>
                  <option value="security-agent">security-agent</option>
                  <option value="data-agent">data-agent</option>
                </select>
              </div>
              <div className="mt-4 flex justify-end gap-2">
                <button onClick={() => setModalOpen(false)} className="rounded-lg px-3 py-1.5 text-xs text-muted hover:bg-white/[0.04] transition-all">Cancel</button>
                <button
                  onClick={handleCreateAndExecute}
                  disabled={creating || !form.name.trim()}
                  className="rounded-lg bg-gradient-to-r from-violet-600 to-indigo-600 px-4 py-1.5 text-xs text-white shadow-lg shadow-violet-500/20 hover:shadow-violet-500/30 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {creating ? (
                    <>
                      <Plus className="h-3.5 w-3.5 animate-spin" /> Creating…
                    </>
                  ) : (
                    <>
                      <Rocket className="h-3.5 w-3.5" /> Create & Execute
                    </>
                  )}
                </button>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
