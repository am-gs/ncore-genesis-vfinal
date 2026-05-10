"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import { getScreenshots } from "@/lib/api";
import { Globe, ChevronLeft, ChevronRight, ExternalLink } from "lucide-react";

export function BrowserViewport({
  taskId,
  fullScreen = false,
}: {
  taskId: string;
  fullScreen?: boolean;
}) {
  const [screenshots, setScreenshots] = useState<string[]>([]);
  const [currentUrl, setCurrentUrl] = useState<string>("");
  const [history, setHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [idx, setIdx] = useState(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getScreenshots(taskId);
      const imgs = (data.screenshots || []).map((s) => (typeof s === 'string' ? s : s.data));
      setScreenshots(imgs);
      if (data.current_url) {
        setCurrentUrl(data.current_url);
        setHistory((prev) => {
          const last = prev[prev.length - 1];
          if (data.current_url && last !== data.current_url) {
            return [...prev, data.current_url].slice(-20);
          }
          return prev;
        });
      }
    } catch {
      // silently fail — screenshots may not be available yet
    } finally {
      setLoading(false);
    }
  }, [taskId]);

  useEffect(() => {
    load();
    intervalRef.current = setInterval(load, 3000);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [load]);

  useEffect(() => {
    if (screenshots.length > 0) {
      setIdx(screenshots.length - 1);
    }
  }, [screenshots.length]);

  const currentImage = screenshots[idx] ?? null;

  return (
    <div className={`flex flex-col rounded-2xl border border-white/[0.06] bg-[rgba(15,23,42,0.55)] backdrop-blur-xl overflow-hidden ${fullScreen ? "h-full" : "h-[420px]"}`}>
      {/* URL bar */}
      <div className="flex items-center gap-3 px-4 py-2.5 border-b border-white/[0.06] bg-[rgba(15,23,42,0.6)] backdrop-blur-xl">
        <div className="flex gap-1.5">
          <span className="w-2.5 h-2.5 rounded-full bg-rose-500/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-amber-500/80" />
          <span className="w-2.5 h-2.5 rounded-full bg-emerald-500/80" />
        </div>
        <div className="flex items-center gap-2 flex-1 min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.03] px-3 py-1.5">
          <Globe className="h-3.5 w-3.5 text-muted shrink-0" />
          <span className="text-[11px] text-text font-mono truncate">{currentUrl || "about:blank"}</span>
        </div>
        {currentUrl && (
          <a href={currentUrl} target="_blank" rel="noopener noreferrer" className="text-muted hover:text-text transition-colors">
            <ExternalLink className="h-3.5 w-3.5" />
          </a>
        )}
      </div>

      {/* Viewport */}
      <div className="flex-1 min-h-0 relative bg-[#070a12] flex items-center justify-center">
        {currentImage ? (
          <img
            src={`data:image/png;base64,${currentImage}`}
            alt="Browser viewport"
            className="max-w-full max-h-full object-contain"
            draggable={false}
          />
        ) : (
          <div className="text-center">
            <Globe className="h-10 w-10 text-muted/20 mx-auto mb-2" />
            <div className="text-xs text-muted/40">No screenshot available</div>
          </div>
        )}
        {loading && (
          <div className="absolute top-2 right-2">
            <div className="h-2 w-2 rounded-full bg-cyan-400 animate-pulse shadow-[0_0_8px_rgba(6,182,212,0.6)]" />
          </div>
        )}
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between px-4 py-2 border-t border-white/[0.06]">
        <div className="flex items-center gap-2">
          <button
            onClick={() => setIdx((i) => Math.max(0, i - 1))}
            disabled={idx <= 0}
            className="rounded-md p-1 text-muted hover:text-text hover:bg-white/[0.04] disabled:opacity-30 transition-all"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-[11px] text-muted font-mono min-w-[3rem] text-center">
            {screenshots.length > 0 ? `${idx + 1} / ${screenshots.length}` : "—"}
          </span>
          <button
            onClick={() => setIdx((i) => Math.min(screenshots.length - 1, i + 1))}
            disabled={idx >= screenshots.length - 1}
            className="rounded-md p-1 text-muted hover:text-text hover:bg-white/[0.04] disabled:opacity-30 transition-all"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto max-w-[60%] scrollbar-hide">
          {history.map((url, i) => (
            <span key={`${url}-${i}`} className="text-[10px] text-muted/60 truncate max-w-[120px] font-mono">
              {url.replace(/^https?:\/\//, "").replace(/\/$/, "").slice(0, 24)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
