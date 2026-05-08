// Types for the NLLM.ING Dashboard — Manus-style three-panel layout

export interface Agent {
  role: string;
  prompt: string;
  uncensored: boolean;
  max_tokens: number;
  tool?: 'gpu_image' | 'gpu_video' | 'browser' | 'code' | 'codeact' | 'osint' | null;
  execution_mode?: 'llm' | 'codeact' | 'browser' | 'agent_zero';
  depends_on?: string[];
  parallel_with?: string[];
}

export interface TaskPlan {
  task_id: string;
  agents: Agent[];
  plan_time: number;
}

export interface AgentResult {
  role: string;
  status: 'ok' | 'error' | 'running' | 'pending';
  latency: number;
  provider: string;
  uncensored: boolean;
  tokens_in: number;
  tokens_out: number;
  model: string;
  output: string;
}

export interface TaskResult {
  output: string;
  route: {
    tier: string;
    estimated_cost_usd: number;
    model: string;
    provider: string;
  };
  task_id: string;
  agents: number;
  plan_time: number;
  exec_time: number;
  latency_s: number;
  cost_usd: number;
  tokens: {
    in: number;
    out: number;
    total: number;
  };
  specialist_results: AgentResult[];
}

export interface Session {
  id: string;
  title: string;
  status: 'active' | 'completed' | 'error' | 'idle' | 'paused';
  createdAt: number;
  updatedAt: number;
  task?: string;
  result?: TaskResult;
}

export interface FileNode {
  name: string;
  path: string;
  type: 'image' | 'video' | 'audio' | 'document' | 'code' | 'directory';
  size: number;
  modified: number;
  url?: string;
  children?: FileNode[];
}

export interface BudgetInfo {
  daily: number;
  daily_limit: number;
  monthly: number;
  monthly_limit: number;
  cache_hit_rate: number;
}

// ── WebSocket message types (real-time bidirectional) ──────────────
export type WSMessage =
  | { type: 'task_start'; task_id: string; task: string; plan: TaskPlan }
  | { type: 'agent_update'; task_id: string; agent: AgentStatus }
  | { type: 'terminal_output'; task_id: string; output: string; is_stderr: boolean }
  | { type: 'file_update'; task_id: string; files: FileNode[] }
  | { type: 'plan_update'; task_id: string; plan: TaskPlan }
  | { type: 'completion'; task_id: string; result: TaskResult }
  | { type: 'error'; task_id: string; error: string }
  | { type: 'budget_update'; daily: number; monthly: number; cache_hit_rate: number }
  | { type: 'connected'; client_id: string }
  | { type: 'disconnected' };

export interface AgentStatus {
  role: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  tokens_in: number;
  tokens_out: number;
  latency: number;
  cost_usd: number;
  progress: number; // 0-100
  message?: string;
}

export interface UsageStats {
  totalTokens: number;
  totalCost: number;
  requests: {
    timestamp: number;
    model: string;
    inputTokens: number;
    outputTokens: number;
    cost: number;
    latency: number;
    status: 'ok' | 'error';
  }[];
}
