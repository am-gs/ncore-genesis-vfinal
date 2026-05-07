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
