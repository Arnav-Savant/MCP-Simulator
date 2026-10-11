// Hand-written mirrors of backend/events/model.py and backend/schemas/api.py.
export type ComponentName = "user" | "host" | "llm" | "client" | "transport" | "server" | "tool";
export type Kind = "real_mcp" | "host_internal" | "simulated" | "playback" | "legacy";

export interface ErrorInfo {
  layer: "protocol" | "tool" | "host" | "transport";
  category: string;
  code: number | null;
  message: string;
  reached_server: boolean;
}

export interface McpEvent {
  id: string;
  run_id: string;
  scenario_id: string | null;
  seq: number;
  component: ComponentName;
  operation: string;
  status: "started" | "completed" | "failed" | "skipped";
  kind: Kind;
  direction: "request" | "response" | "notification" | "internal" | null;
  method: string | null;
  request: Record<string, unknown> | null;
  response: Record<string, unknown> | null;
  data: Record<string, unknown> | null;
  message: string;
  error: ErrorInfo | null;
  latency_ms: number | null;
  ts: number;
}

export interface RunState {
  run_id: string;
  scenario_id: string | null;
  status: "idle" | "running" | "finished" | "complete";
  total: number;
  released: number;
  paused: boolean;
  delay_ms: number;
}

export interface Step {
  type: string;
  [k: string]: unknown;
}

export interface Scenario {
  id: string;
  title: string;
  category: string;
  description: string;
  user_message: string;
  expected: string;
  steps: Step[];
}

export interface ComponentInfo {
  name: ComponentName;
  title: string;
  implementation: "real" | "simulated" | "conceptual";
  responsibility: string;
  state: string;
  event_count: number;
  operations: Record<string, number>;
  last_event_id: string | null;
}

export interface Tool {
  name: string;
  description?: string;
  inputSchema?: Record<string, any>;
  outputSchema?: Record<string, any>;
  [k: string]: unknown;
}
