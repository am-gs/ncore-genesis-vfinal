import type { HealthResponse, RunsResponse, RestartResponse, Task, PlanStep, Artifact, Screenshot } from '@/types';

const BASE = typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_API_URL || '') : '';

export async function fetchHealth(): Promise<HealthResponse> {
  const r = await fetch(`${BASE}/api/health`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Health ${r.status}`);
  return r.json();
}

export async function fetchRuns(limit = 50): Promise<RunsResponse> {
  const r = await fetch(`${BASE}/api/runs?limit=${limit}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Runs ${r.status}`);
  return r.json();
}

export async function fetchLogs(name: string): Promise<string> {
  const r = await fetch(`${BASE}/api/logs/${name}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Logs ${r.status}`);
  return r.text();
}

export async function restartService(name: string): Promise<RestartResponse> {
  const r = await fetch(`${BASE}/api/restart/${name}`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Restart ${r.status}`);
  return r.json();
}

const DEERFLOW_BASE = typeof window !== 'undefined' ? (process.env.NEXT_PUBLIC_DEERFLOW_URL || 'http://127.0.0.1:2026') : '';

export async function chatDeerFlow(messages: { role: string; content: string }[], threadId = 'dashboard'): Promise<{ content: string }> {
  const r = await fetch(`${DEERFLOW_BASE}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages, thread_id: threadId }),
  });
  if (!r.ok) throw new Error(`Chat ${r.status}`);
  return r.json();
}

/* ── Task Execution API (cognitive infrastructure) ── */

export async function fetchTasks(status?: string, limit = 50): Promise<{ tasks: Task[] }> {
  const qs = status ? `?status=${status}&limit=${limit}` : `?limit=${limit}`;
  const r = await fetch(`${BASE}/api/tasks${qs}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Tasks ${r.status}`);
  return r.json();
}

export async function createTask(body: { name: string; description: string; agent: string; plan_steps?: { description: string }[] }): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store' });
  if (!r.ok) throw new Error(`Create ${r.status}`);
  return r.json();
}

export async function fetchTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Task ${r.status}`);
  return r.json();
}

export async function fetchTaskTree(id: string): Promise<{ tree: Task }> {
  const r = await fetch(`${BASE}/api/tasks/${id}/tree`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Tree ${r.status}`);
  return r.json();
}

export async function spawnSubtask(id: string, body: { name: string; description: string; agent: string }): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/spawn`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store' });
  if (!r.ok) throw new Error(`Spawn ${r.status}`);
  return r.json();
}

export async function branchTask(id: string, body: { name: string; description: string; from_step_id?: string }): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/branch`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), cache: 'no-store' });
  if (!r.ok) throw new Error(`Branch ${r.status}`);
  return r.json();
}

export async function pauseTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/pause`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Pause ${r.status}`);
  return r.json();
}

export async function resumeTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/resume`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Resume ${r.status}`);
  return r.json();
}

export async function retryTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/retry`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Retry ${r.status}`);
  return r.json();
}

export async function cancelTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/cancel`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Cancel ${r.status}`);
  return r.json();
}

/* ── Manus autonomous execution API ── */

export async function executeTask(id: string): Promise<Task> {
  const r = await fetch(`${BASE}/api/tasks/${id}/execute`, { method: 'POST', cache: 'no-store' });
  if (!r.ok) throw new Error(`Execute ${r.status}`);
  return r.json();
}

export async function getScreenshots(id: string): Promise<{ task_id: string; screenshots: Screenshot[]; current_url?: string }> {
  const r = await fetch(`${BASE}/api/tasks/${id}/screenshots`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Screenshots ${r.status}`);
  return r.json();
}

export async function sendTerminalCommand(id: string, command: string, timeout = 30): Promise<{ task_id: string; output: string }> {
  const r = await fetch(`${BASE}/api/tasks/${id}/terminal`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ command, timeout }),
    cache: 'no-store',
  });
  if (!r.ok) throw new Error(`Terminal ${r.status}`);
  return r.json();
}

export async function getArtifacts(id: string): Promise<{ task_id: string; artifacts: Artifact[] }> {
  const r = await fetch(`${BASE}/api/tasks/${id}/artifacts`, { cache: 'no-store' });
  if (!r.ok) throw new Error(`Artifacts ${r.status}`);
  return r.json();
}

export function getTerminalWSUrl(id: string): string {
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  const host = typeof window !== 'undefined' ? window.location.host : '127.0.0.1:3004';
  return `${protocol}//${host}/ws/terminal/${id}`;
}

/** @deprecated - use getTerminalWSUrl for URL strings; this creates the WebSocket directly */
export function connectTerminalWS(id: string): WebSocket {
  return new WebSocket(getTerminalWSUrl(id));
}
