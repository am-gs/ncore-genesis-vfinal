"use client";

import { useState, useEffect } from "react";
import { ManusTerminal } from "@/components/manus/Terminal";
import { fetchTasks } from "@/lib/api";
import type { Task } from "@/types";
import { StatusDot } from "@/components/ui/StatusDot";
import { Terminal as TerminalIcon, ChevronDown } from "lucide-react";

export default function TerminalPage() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchTasks("running", 50)
      .then((res) => {
        setTasks(res.tasks);
        if (res.tasks.length > 0) setSelectedId(res.tasks[0].id);
      })
      .catch(() => setTasks([]))
      .finally(() => setLoading(false));
  }, []);

  // Also fetch all tasks so user can pick non-running ones
  useEffect(() => {
    const t = setInterval(() => {
      fetchTasks(undefined, 100)
        .then((res) => setTasks(res.tasks))
        .catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, []);

  const selectedTask = tasks.find((t) => t.id === selectedId);

  return (
    <div className="flex flex-col h-[calc(100vh-5rem)] gap-4">
      {/* Header */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-emerald-500/10 p-2.5">
            <TerminalIcon className="h-5 w-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gradient">Manus Terminal</h1>
            <p className="text-xs text-muted">Interactive shell for agent tasks</p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <select
              value={selectedId}
              onChange={(e) => setSelectedId(e.target.value)}
              className="appearance-none rounded-xl border border-white/[0.06] bg-white/[0.03] pl-3 pr-8 py-2 text-sm text-text outline-none focus:border-violet-500/30 font-mono"
            >
              {tasks.length === 0 && <option value="">No tasks</option>}
              {tasks.map((t) => (
                <option key={t.id} value={t.id}>
                  {t.name} ({t.status})
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-4 w-4 text-muted" />
          </div>
          {selectedTask && (
            <div className="flex items-center gap-2 rounded-xl border border-white/[0.06] bg-white/[0.03] px-3 py-2">
              <StatusDot ok={selectedTask.status === "running" || selectedTask.status === "completed"} size="sm" pulse={selectedTask.status === "running"} />
              <span className="text-[11px] text-muted font-mono">{selectedTask.status}</span>
            </div>
          )}
        </div>
      </div>

      {/* Terminal */}
      <div className="flex-1 min-h-0">
        {loading ? (
          <div className="h-full rounded-2xl border border-white/[0.06] bg-[#070a12] animate-pulse" />
        ) : selectedId ? (
          <ManusTerminal taskId={selectedId} fullScreen />
        ) : (
          <div className="h-full rounded-2xl border border-white/[0.06] bg-[rgba(15,23,42,0.55)] backdrop-blur-xl flex items-center justify-center">
            <div className="text-center">
              <TerminalIcon className="h-12 w-12 text-muted/20 mx-auto mb-3" />
              <div className="text-sm text-muted">Select a task to open its terminal</div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
