const BASE = typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:3004') : '';

export async function fetchHealth(): Promise<import('../types').HealthResponse> {
  const r = await fetch(`${BASE}/api/health`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Health ${r.status}`);
  return r.json();
}

export async function fetchRuns(limit = 50): Promise<import('../types').RunsResponse> {
  const r = await fetch(`${BASE}/api/runs?limit=${limit}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Runs ${r.status}`);
  return r.json();
}

export async function fetchLogs(name: string): Promise<string> {
  const r = await fetch(`${BASE}/api/logs/${name}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Logs ${r.status}`);
  return r.text();
}

export async function restartService(name: string): Promise<import('../types').RestartResponse> {
  const r = await fetch(`${BASE}/api/restart/${name}`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Restart ${r.status}`);
  return r.json();
}

export async function chatDeerFlow(messages: { role: string; content: string }[], threadId = 'dashboard'): Promise<{ content: string }> {
  const r = await fetch('http://127.0.0.1:2026/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, thread_id: threadId }),
  });
  if (!r.ok) throw new Error(`Chat ${r.status}`);
  return r.json();
}
