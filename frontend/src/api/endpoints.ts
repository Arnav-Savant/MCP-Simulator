import { api, post } from "./client";
import type { ComponentInfo, RunState, Scenario, Tool } from "../types";

export const endpoints = {
  scenarios: () => api<Scenario[]>("/scenarios"),
  tools: () => api<Tool[]>("/mcp/tools"),
  components: () => api<ComponentInfo[]>("/components"),
  connect: (mode: string) => post("/mcp/connect", { mode }),
  discover: () => post("/mcp/discover"),
  callTool: (name: string, args: unknown) => post(`/mcp/tools/${name}/call`, { arguments: args }),
  runScenario: (scenario_id: string, delay_ms: number, paused: boolean) =>
    post<RunState>("/runs", { scenario_id, delay_ms, paused }),
  control: (action: "pause" | "resume" | "step") => post<RunState>(`/runs/current/${action}`),
  playback: (delay_ms: number) => post<RunState>("/playback", { delay_ms }),
  reset: () => post<RunState>("/reset"),
};
