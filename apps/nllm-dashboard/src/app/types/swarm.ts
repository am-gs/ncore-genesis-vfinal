export interface SwarmAgent {
  id: string;
  role: string;
  status: 'idle' | 'running' | 'completed' | 'error' | 'paused';
  model: string;
  provider: string;
  tokens_in: number;
  tokens_out: number;
  latency_ms: number;
  cost_usd: number;
  checkpoint_id?: string;
  depends_on: string[];
  parallel_with: string[];
}

export interface LangGraphNode {
  id: string;
  label: string;
  type: 'agent' | 'router' | 'checkpoint' | 'critic' | 'entry' | 'end';
  status: 'idle' | 'active' | 'completed' | 'error';
  x: number;
  y: number;
  agent?: SwarmAgent;
}

export interface LangGraphEdge {
  from: string;
  to: string;
  label?: string;
  status: 'pending' | 'active' | 'completed' | 'error';
}

export interface CheckpointInfo {
  id: string;
  thread_id: string;
  checkpoint_ns: string;
  created_at: string;
  agent_id: string;
  state_json: string;
  metadata?: Record<string, unknown>;
}

export interface SwarmTask {
  id: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'error';
  agents: SwarmAgent[];
  nodes: LangGraphNode[];
  edges: LangGraphEdge[];
  checkpoints: CheckpointInfo[];
  total_latency: number;
  total_cost: number;
  created_at: number;
  updated_at: number;
  recovery_count: number;
}

export interface SwarmMetrics {
  active_tasks: number;
  total_agents: number;
  avg_latency: number;
  total_cost_today: number;
  checkpoint_count: number;
  recovery_success_rate: number;
  a2a_messages_per_min: number;
}
