'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Settings, Server, Globe, Info, Shield, Zap } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6 animate-slide-up max-w-3xl">
      <div className="relative overflow-hidden rounded-2xl border border-white/[0.06] bg-gradient-to-br from-[rgba(99,102,241,0.08)] to-[rgba(139,92,246,0.04)] p-6 backdrop-blur-xl">
        <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-indigo-500/10 blur-3xl" />
        <div className="relative flex items-center justify-between">
          <div>
            <h1 className="text-lg font-bold text-gradient">Settings</h1>
            <p className="mt-1 text-xs text-muted">Configure Mission Control and sovereign stack</p>
          </div>
          <Settings className="h-8 w-8 text-indigo-400/60" />
        </div>
      </div>

      <Card glow>
        <CardHeader><CardTitle>API Endpoints</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { name: 'Mission Control', url: 'http://127.0.0.1:3004', status: 'ok' },
              { name: 'Bifrost Gateway', url: 'http://127.0.0.1:8000', status: 'ok' },
              { name: 'DeerFlow', url: 'http://127.0.0.1:2026', status: 'ok' },
              { name: 'Mem0', url: 'http://127.0.0.1:8300', status: 'ok' },
              { name: 'Ollama LLM', url: 'http://127.0.0.1:11434', status: 'ok' },
            ].map(ep => (
              <div key={ep.name} className="flex items-center justify-between rounded-xl border border-white/[0.06] bg-white/[0.03] px-4 py-3 backdrop-blur-md hover:bg-white/[0.05] transition-all">
                <div className="flex items-center gap-3">
                  <div className="rounded-lg bg-white/[0.04] p-1.5"><Server className="h-4 w-4 text-muted" /></div>
                  <span className="text-sm text-text">{ep.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <code className="text-[11px] font-mono text-muted">{ep.url}</code>
                  <Badge color="ok">Active</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card glow>
        <CardHeader><CardTitle>Bifrost Configuration</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-4 text-sm">
            {[
              { label: 'Monthly Cap', value: '$38.00 USD' },
              { label: 'Local Chain', value: 'qwen3-8b, dolphin-mistral-7b' },
              { label: 'Policy Engine', value: 'Hard Stop + Dual-Use Auth' },
              { label: 'Fallback Strategy', value: 'Remote → Local → Policy' },
            ].map(item => (
              <div key={item.label} className="flex justify-between items-center border-b border-white/[0.04] pb-3 last:border-0 last:pb-0">
                <span className="text-muted">{item.label}</span>
                <span className="font-mono text-text text-xs">{item.value}</span>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card glow>
        <CardHeader><CardTitle>About</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-violet-600 via-indigo-600 to-cyan-500 shadow-lg shadow-violet-500/20">
                <Zap className="h-5 w-5 text-white" />
              </div>
              <div>
                <div className="text-sm font-semibold text-text">Sovereign Mission Control</div>
                <div className="text-xs text-muted">v1.0.0-beta &middot; ncore-genesis-vfinal</div>
              </div>
            </div>
            <p className="text-xs text-muted leading-relaxed">
              Local high-compliance agentic stack. All inference runs on localhost.
              Remote APIs only used when explicitly configured and for non-sensitive tasks.
              Built with Next.js 16, React 19, Tailwind CSS, and sovereign-local LLMs.
            </p>
            <div className="flex items-center gap-2 text-xs text-muted">
              <Shield className="h-3.5 w-3.5" /> End-to-end encrypted
              <span className="mx-1">&middot;</span>
              <Globe className="h-3.5 w-3.5" /> Zero external dependencies
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
