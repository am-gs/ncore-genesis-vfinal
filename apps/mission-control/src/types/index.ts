export interface Service {
  name: string;
  ok: boolean;
  latency_ms: number;
  detail: string;
  link: string;
}
export interface HealthResponse {
  services: Service[];
}
export interface Run {
  ts: number;
  task_id: string;
  requested_model: string;
  provider: string;
  model: string;
  fallback_reason: string;
  latency_ms: number;
  completion_status: string;
  refusal_intercepted: number;
}
export interface RunsResponse {
  runs: Run[];
  error?: string;
}
export interface RestartResponse {
  ok: boolean;
  output: string;
}

export interface Artifact {
  name: string;
  type: string;
  content: string;
  created_at: string;
}

export interface PlanStep {
  id: string;
  description: string;
  status: 'pending' | 'planning' | 'running' | 'paused' | 'completed' | 'failed' | 'retrying' | 'cancelled';
  agent?: string;
  depends_on: string[];
  output?: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'planning' | 'running' | 'paused' | 'completed' | 'failed' | 'retrying' | 'cancelled';
  agent: string;
  progress: number;
  created_at: string;
  updated_at: string;
  plan: PlanStep[];
  subtasks: string[];
  parent_id?: string;
  branch_from?: string;
  latency_ms: number;
  retries: number;
  error?: string;
  artifacts: Artifact[];
  memory_refs: string[];
}
