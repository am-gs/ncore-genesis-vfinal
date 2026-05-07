'use client';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Settings, Server, Key, Globe, Info } from 'lucide-react';

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-3xl">
      <div className="flex items-center gap-3">
        <Settings className="h-5 w-5 text-accent" />
        <div>
          <h2 className="text-sm font-semibold text-text">Settings</h2>
          <p className="text-xs text-muted">Configure Mission Control and sovereign stack</p>
        </div>
      </div>

      <Card>
        <CardHeader><CardTitle>API Endpoints</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[
              { name: 'Mission Control', url: 'http://127.0.0.1:3004', status: 'ok' },
              { name: 'Bifrost Gateway', url: 'http://127.0.0.1:8000', status: 'ok' },
              { name: 'DeerFlow', url: 'http://127.0.0.1:2026', status: 'ok' },
              { name: 'Mem0', url: 'http://127.0.0.1:8300', status: 'ok' },
              { name: 'Ollama LLM', url: 'http://127.0.0.1:11434', status: 'ok' },
            ].map((ep) => (
              <div key={ep.name} className="flex items-center justify-between rounded-md border border-line bg-panel-2 px-3 py-2">
                <div className="flex items-center gap-2">
                  <Server className="h-3.5 w-3.5 text-muted" />
                  <span className="text-sm text-text">{ep.name}</span>
                </div>
                <div className="flex items-center gap-3">
                  <code className="text-xs font-mono text-muted">{ep.url}</code>
                  <Badge color="ok">Active</Badge>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Bifrost Configuration</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-3 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Monthly Cap</span>
              <span className="font-mono text-text">$38.00 USD</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Local Chain</span>
              <span className="font-mono text-text">qwen3-8b, dolphin-mistral-7b</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Policy Engine</span>
              <span className="font-mono text-text">Hard Stop + Dual-Use Auth</span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Fallback Strategy</span>
              <span className="font-mono text-text">Remote → Local → Policy</span>
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>About</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2 text-sm">
            <div className="flex items-center gap-2 text-muted">
              <Info className="h-4 w-4" />
              <span>Sovereign Mission Control v1.0.0-beta</span>
            </div>
            <div className="flex items-center gap-2 text-muted">
              <Globe className="h-4 w-4" />
              <span>ncore-genesis-vfinal</span>
            </div>
            <p className="text-xs text-muted mt-3">
              Local high-compliance agentic stack. All inference runs on localhost.
              Remote APIs only used when explicitly configured and for non-sensitive tasks.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
