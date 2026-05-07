'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
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
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Brain className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">Mem0 Memory</h2>
          <p className="text-xs text-muted">Persistent memory layer for agents and user preferences</p>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card><CardContent className="pt-4 flex items-center gap-3">
          <MemoryStick className="h-5 w-5 text-accent" />
          <div>
            <div className="text-xs text-muted uppercase tracking-wider">Memories</div>
            <div className="text-2xl font-bold">{memories.length}</div>
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4 flex items-center gap-3">
          <Search className="h-5 w-5 text-accent-2" />
          <div>
            <div className="text-xs text-muted uppercase tracking-wider">Searches</div>
            <div className="text-2xl font-bold">1,247</div>
          </div>
        </CardContent></Card>
        <Card><CardContent className="pt-4 flex items-center gap-3">
          <Clock className="h-5 w-5 text-warn" />
          <div>
            <div className="text-xs text-muted uppercase tracking-wider">Last Updated</div>
            <div className="text-sm font-bold">2h ago</div>
          </div>
        </CardContent></Card>
      </div>

      <Card>
        <CardHeader><CardTitle>Recent Memories</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {memories.map((m) => (
              <div key={m.id} className="flex items-start gap-3 rounded-md border border-line bg-panel-2 p-3">
                <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent/15">
                  <Brain className="h-3 w-3 text-accent" />
                </div>
                <div className="flex-1">
                  <div className="text-sm text-text">{m.content}</div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted">
                    <span className="rounded bg-panel px-1.5 py-0.5">{m.category}</span>
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
