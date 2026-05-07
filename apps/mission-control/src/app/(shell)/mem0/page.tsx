'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Brain, MemoryStick, Search, Clock } from 'lucide-react';

const memories = [
  { id: 1, content: 'User prefers dark mode for all dashboards', category: 'Preference', created: '2h ago' },
  { id: 2, content: 'Bifrost fallback to local qwen3-8b when remote refuses', category: 'System', created: '5h ago' },
  { id: 3, content: 'Agent Zero skill: web-search enabled by default', category: 'Skill', created: '1d ago' },
  { id: 4, content: 'Watchdog restart threshold: 2 consecutive failures', category: 'Config', created: '2d ago' },
  { id: 5, content: 'Monthly budget cap set to $38.00 USD', category: 'Budget', created: '3d ago' },
];

export default function Mem0Page() {
  return (
    <div className="space-y-6 animate-slide-up">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(236,72,153,0.08)] to-[rgba(139,92,246,0.04)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-pink-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient-accent">Mem0 Memory</h1>
            <p className="mt-1 text-xs text-muted">Persistent memory layer for agents and user preferences</p>
          </div>
          <Brain className="h-8 w-8 text-pink-400/60" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card glow><CardContent className="pt-5 flex items-center gap-3">
          <div className="rounded-xl bg-pink-500/10 p-2.5"><MemoryStick className="h-5 w-5 text-pink-400" /></div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Memories</div>
            <div className="mt-1 text-2xl font-bold tracking-tight">{memories.length}</div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5 flex items-center gap-3">
          <div className="rounded-xl bg-violet-500/10 p-2.5"><Search className="h-5 w-5 text-violet-400" /></div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Searches</div>
            <div className="mt-1 text-2xl font-bold tracking-tight">1,247</div>
          </div>
        </CardContent></Card>
        <Card glow><CardContent className="pt-5 flex items-center gap-3">
          <div className="rounded-xl bg-amber-500/10 p-2.5"><Clock className="h-5 w-5 text-amber-400" /></div>
          <div>
            <div className="text-[11px] font-semibold uppercase tracking-[0.12em] text-muted">Last Updated</div>
            <div className="mt-1 text-sm font-bold">2h ago</div>
          </div>
        </CardContent></Card>
      </div>

      <Card glow>
        <CardHeader><CardTitle>Recent Memories</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {memories.map(m => (
              <div key={m.id} className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-white/[0.03] p-4 backdrop-blur-md hover:bg-white/[0.05] transition-all">
                <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-pink-500/20 to-violet-500/20">
                  <Brain className="h-3.5 w-3.5 text-pink-400" />
                </div>
                <div className="flex-1">
                  <div className="text-sm text-text">{m.content}</div>
                  <div className="mt-1.5 flex items-center gap-2 text-xs text-muted">
                    <Badge color="muted">{m.category}</Badge>
                    <span>{m.created}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
