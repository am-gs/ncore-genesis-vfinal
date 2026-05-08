'use client';

import { useRef, useEffect } from 'react';
import { ScrollArea } from '@/app/components/ui/scroll-area';

export function TerminalView({
  output,
}: {
  output: { output: string; is_stderr: boolean }[];
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [output]);

  return (
    <div className="h-full flex flex-col bg-[#0d0d0d] text-[#e5e5e5] font-mono text-[13px]">
      <div className="flex items-center gap-2 px-3 py-1.5 bg-[#1a1a1a] border-b border-[#2a2a2a]">
        <div className="w-2.5 h-2.5 rounded-full bg-bad" />
        <div className="w-2.5 h-2.5 rounded-full bg-warn" />
        <div className="w-2.5 h-2.5 rounded-full bg-ok" />
        <span className="text-[10px] text-[#666] ml-2">Terminal</span>
      </div>
      <div
        ref={scrollRef}
        className="flex-1 overflow-auto p-3 space-y-0.5"
      >
        {output.length === 0 && (
          <div className="text-[#555] italic">No output yet. Run a task to see results.</div>
        )}
        {output.map((line, i) => (
          <div
            key={i}
            className={`whitespace-pre-wrap break-all leading-relaxed
              ${line.is_stderr ? 'text-bad' : 'text-[#e5e5e5]'}`}
          >
            {line.output || '\n'}
          </div>
        ))}
        <div className="animate-pulse text-accent text-xs mt-1">
          <span className="mr-1">›</span>
          <span className="animate-typing">_</span>
        </div>
      </div>
    </div>
  );
}
