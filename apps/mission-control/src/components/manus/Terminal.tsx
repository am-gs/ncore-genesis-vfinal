"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import { Terminal as XTerm } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";
import { sendTerminalCommand } from "@/lib/api";
import { StatusDot } from "@/components/ui/StatusDot";

const THEME = {
  background: "#070a12",
  foreground: "#e5e7eb",
  cursor: "#8b5cf6",
  selectionBackground: "rgba(139, 92, 246, 0.3)",
  black: "#0f172a",
  red: "#ef4444",
  green: "#22c55e",
  yellow: "#f59e0b",
  blue: "#3b82f6",
  magenta: "#8b5cf6",
  cyan: "#06b6d4",
  white: "#e5e7eb",
  brightBlack: "#1e293b",
  brightRed: "#f87171",
  brightGreen: "#4ade80",
  brightYellow: "#fbbf24",
  brightBlue: "#60a5fa",
  brightMagenta: "#a78bfa",
  brightCyan: "#22d3ee",
  brightWhite: "#f1f5f9",
};

export function ManusTerminal({
  taskId,
  wsUrl,
  fullScreen = false,
}: {
  taskId: string;
  wsUrl?: string;
  fullScreen?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<XTerm | null>(null);
  const fitRef = useRef<FitAddon | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const [pending, setPending] = useState(false);

  const writeOutput = useCallback((data: string) => {
    termRef.current?.write(data);
  }, []);

  // Initialize xterm
  useEffect(() => {
    if (!containerRef.current) return;
    const term = new XTerm({
      theme: THEME,
      fontFamily: "var(--font-jetbrains), ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace",
      fontSize: 14,
      cursorBlink: true,
      cursorStyle: "block",
      scrollback: 5000,
      allowTransparency: true,
    });
    const fit = new FitAddon();
    term.loadAddon(fit);
    term.open(containerRef.current);
    fit.fit();

    termRef.current = term;
    fitRef.current = fit;

    term.writeln("\x1b[38;5;141mManus Terminal initialized\x1b[0m");
    term.writeln(`\x1b[38;5;248mTask: ${taskId}\x1b[0m`);
    term.writeln("");

    const onResize = () => fit.fit();
    window.addEventListener("resize", onResize);

    return () => {
      window.removeEventListener("resize", onResize);
      term.dispose();
      termRef.current = null;
      fitRef.current = null;
    };
  }, [taskId]);

  // WebSocket connection
  useEffect(() => {
    if (!wsUrl || !termRef.current) return;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      setConnected(true);
      writeOutput(`\x1b[38;5;82mConnected to ${wsUrl}\x1b[0m\r\n`);
    };
    ws.onmessage = (e) => {
      writeOutput(e.data);
    };
    ws.onclose = () => {
      setConnected(false);
      writeOutput(`\x1b[38;5;196mConnection closed\x1b[0m\r\n`);
    };
    ws.onerror = () => {
      setConnected(false);
      writeOutput(`\x1b[38;5;196mConnection error\x1b[0m\r\n`);
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [wsUrl, writeOutput]);

  // Handle user input when no WebSocket (fallback POST mode)
  useEffect(() => {
    if (wsUrl) return;
    const term = termRef.current;
    if (!term) return;

    let currentLine = "";
    const disposable = term.onData((data) => {
      const code = data.charCodeAt(0);
      if (code === 13) {
        // Enter
        term.writeln("");
        if (currentLine.trim()) {
          setPending(true);
          sendTerminalCommand(taskId, currentLine.trim())
            .then((res) => {
              term.writeln(res.output);
            })
            .catch((err) => {
              term.writeln(`\x1b[38;5;196mError: ${err.message}\x1b[0m`);
            })
            .finally(() => {
              setPending(false);
              term.write("$ ");
            });
        } else {
          term.write("$ ");
        }
        currentLine = "";
      } else if (code === 127) {
        // Backspace
        if (currentLine.length > 0) {
          currentLine = currentLine.slice(0, -1);
          term.write("\b \b");
        }
      } else if (code >= 32 && code <= 126) {
        currentLine += data;
        term.write(data);
      }
    });

    term.write("$ ");
    return () => disposable.dispose();
  }, [wsUrl, taskId]);

  return (
    <div className={`flex flex-col rounded-2xl border border-white/[0.06] bg-[#070a12] overflow-hidden ${fullScreen ? "h-full" : "h-[420px]"}`}>
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/[0.06] bg-[rgba(15,23,42,0.6)] backdrop-blur-xl">
        <div className="flex items-center gap-2.5">
          <div className="flex gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
          </div>
          <span className="text-[11px] font-medium text-muted font-mono">Terminal</span>
          <span className="text-[10px] text-muted/50 font-mono">{taskId.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          {pending && <span className="text-[10px] text-amber-400 animate-pulse">running…</span>}
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md border border-white/[0.06] bg-white/[0.02]">
            <StatusDot ok={connected} size="sm" pulse={connected} />
            <span className="text-[10px] text-muted font-mono">{connected ? "WS" : "POST"}</span>
          </div>
        </div>
      </div>
      <div ref={containerRef} className="flex-1 min-h-0 p-2" />
    </div>
  );
}
