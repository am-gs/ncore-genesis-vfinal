"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import type { ToolCall } from "@/types";
import { Badge } from "@/components/ui/Badge";
import {
  Globe,
  Terminal,
  FileText,
  Code2,
  Camera,
  ChevronDown,
  ChevronRight,
  Bot,
} from "lucide-react";

const BASE = typeof window !== "undefined" ? (process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:3004") : "";

function formatTime(ts: string) {
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function ToolIcon({ tool }: { tool: string }) {
  const cls = "h-3.5 w-3.5 shrink-0";
  if (tool.includes("browser")) return <Globe className={`${cls} text-cyan-400`} />;
  if (tool.includes("terminal")) return <Terminal className={`${cls} text-emerald-400`} />;
  if (tool.includes("file")) return <FileText className={`${cls} text-amber-400`} />;
  if (tool.includes("code")) return <Code2 className={`${cls} text-violet-400`} />;
  if (tool.includes("screenshot")) return <Camera className={`${cls} text-rose-400`} />;
  return <Bot className={`${cls} text-muted`} />;
}

function ToolCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(call.status === "running" || call.status === "error");
  const statusColor = call.status === "done" ? "ok" : call.status === "error" ? "bad" : "cyan";

  const inputSnippet = JSON.stringify(call.input, null, 2).slice(0, 800);
  const hasOutput = call.output && call.output.length > 0;
  const isScreenshot = call.tool.includes("screenshot");

  return (
    <div className="rounded-xl border border-white/[0.04] bg-white/[0.02] overflow-hidden transition-all hover:border-white/[0.08]">
      <button
        onClick={() => setExpanded((e) => !e)}
        className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left"
      >
        <ToolIcon tool={call.tool} />
        <span className="text-[11px] font-medium text-text capitalize flex-1 truncate">{call.tool.replace(/_/g, " ")}</span>
        <Badge color={statusColor} className="text-[10px]">{call.status}</Badge>
        <span className="text-[10px] text-muted font-mono">{formatTime(call.timestamp)}</span>
        {expanded ? <ChevronDown className="h-3.5 w-3.5 text-muted" /> : <ChevronRight className="h-3.5 w-3.5 text-muted" />}
      </button>

      {expanded && (
        <div className="px-3 pb-3 space-y-2 border-t border-white/[0.03]">
          {/* Input */}
          {Object.keys(call.input).length > 0 && (
            <div className="mt-2">
              <div className="text-[10px] uppercase tracking-wider text-muted/60 mb-1">Input</div>
              <pre className="rounded-lg bg-[#070a12] border border-white/[0.04] p-2 text-[11px] font-mono text-text-secondary overflow-x-auto whitespace-pre-wrap">
                {inputSnippet}
              </pre>
            </div>
          )}

          {/* Output */}
          {hasOutput && (
            <div>
              <div className="text-[10px] uppercase tracking-wider text-muted/60 mb-1">Output</div>
              {isScreenshot ? (
                <img
                  src={`data:image/png;base64,${call.output}`}
                  alt="screenshot"
                  className="rounded-lg border border-white/[0.06] max-h-48 object-contain"
                />
              ) : (
                <pre className="rounded-lg bg-[#070a12] border border-white/[0.04] p-2 text-[11px] font-mono text-text-secondary overflow-x-auto whitespace-pre-wrap max-h-48 overflow-y-auto">
                  {call.output.length > 2000 ? call.output.slice(0, 2000) + "\n…" : call.output}
                </pre>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export function ExecutionStream({ taskId }: { taskId: string }) {
  const [events, setEvents] = useState<ToolCall[]>([]);
  const [connected, setConnected] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);
  const esRef = useRef<EventSource | null>(null);

  const addEvent = useCallback((call: ToolCall) => {
    setEvents((prev) => {
      const exists = prev.find((e) => e.step === call.step && e.tool === call.tool && e.timestamp === call.timestamp);
      if (exists) {
        return prev.map((e) => (e.step === call.step && e.tool === call.tool && e.timestamp === call.timestamp ? call : e));
      }
      return [...prev, call].sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
    });
  }, []);

  useEffect(() => {
    const es = new EventSource(`${BASE}/api/tasks/stream`);
    esRef.current = es;

    es.onopen = () => setConnected(true);
    es.onerror = () => setConnected(false);

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (data.task_id === taskId && data.tool_call) {
          addEvent(data.tool_call as ToolCall);
        }
      } catch {
        // ignore malformed SSE events
      }
    };

    return () => {
      es.close();
      esRef.current = null;
    };
  }, [taskId, addEvent]);

  // Auto-scroll to bottom
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events.length]);

  return (
    <div className="flex flex-col rounded-2xl border border-white/[0.06] bg-[rgba(15,23,42,0.55)] backdrop-blur-xl overflow-hidden h-full">
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.06] bg-[rgba(15,23,42,0.6)] backdrop-blur-xl shrink-0">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>
          <span className="text-[11px] font-medium text-muted">Execution Stream</span>
          <Badge color={connected ? "ok" : "muted"} className="text-[10px]">
            {connected ? "LIVE" : "OFFLINE"}
          </Badge>
        </div>
        <span className="text-[10px] text-muted font-mono">{events.length} events</span>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto p-3 space-y-2">
        {events.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <Bot className="h-8 w-8 text-muted/20 mb-2" />
            <div className="text-xs text-muted/40">Waiting for agent events…</div>
          </div>
        )}
        {events.map((call, i) => (
          <ToolCard key={`${call.step}-${call.tool}-${i}`} call={call} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
