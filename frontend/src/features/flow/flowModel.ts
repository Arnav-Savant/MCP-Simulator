import type { McpEvent } from "../../types";

export type NodeId = "host" | "llm" | "client" | "transport" | "server" | "tool" | "result";
export type EdgeId = "host-llm" | "host-client" | "client-transport" | "transport-server" | "server-tool" | "host-result";
export type Visual = "idle" | "active" | "done" | "error";

export const NODE_DEFS: { id: NodeId; label: string; x: number; y: number }[] = [
  { id: "llm", label: "Simulated LLM", x: 0, y: 0 },
  { id: "host", label: "MCP Host", x: 0, y: 150 },
  { id: "result", label: "Result Processing", x: 0, y: 300 },
  { id: "client", label: "MCP Client", x: 260, y: 150 },
  { id: "transport", label: "Transport (stdio)", x: 520, y: 150 },
  { id: "server", label: "MCP Server", x: 780, y: 150 },
  { id: "tool", label: "Tool Handler", x: 780, y: 300 },
];

export const EDGE_DEFS: { id: EdgeId; source: NodeId; target: NodeId }[] = [
  { id: "host-llm", source: "host", target: "llm" },
  { id: "host-client", source: "host", target: "client" },
  { id: "client-transport", source: "client", target: "transport" },
  { id: "transport-server", source: "transport", target: "server" },
  { id: "server-tool", source: "server", target: "tool" },
  { id: "host-result", source: "host", target: "result" },
];

type Touch = { nodes: NodeId[]; edges: { id: EdgeId; forward: boolean }[] };

// Which nodes/edges an event concerns. Purely a function of the backend event.
export function touches(e: McpEvent): Touch {
  const nodes: NodeId[] = [];
  const edges: Touch["edges"] = [];
  switch (e.component) {
    case "user":
      nodes.push("host");
      break;
    case "llm":
      nodes.push("llm");
      edges.push({ id: "host-llm", forward: e.direction === "request" });
      break;
    case "host":
      nodes.push("host");
      if (["dispatch_to_client", "request_connect", "request_discovery"].includes(e.operation))
        edges.push({ id: "host-client", forward: true });
      if (e.operation === "receive_result") edges.push({ id: "host-client", forward: false });
      if (e.operation === "supply_tools_to_llm") edges.push({ id: "host-llm", forward: true });
      if (e.operation === "final_response" || e.operation === "run_complete") {
        nodes.push("result");
        edges.push({ id: "host-result", forward: true });
      }
      break;
    case "client":
      nodes.push("client");
      break;
    case "transport":
      nodes.push("transport");
      if (e.direction === "response")
        edges.push({ id: "transport-server", forward: false }, { id: "client-transport", forward: false });
      else edges.push({ id: "client-transport", forward: true }, { id: "transport-server", forward: true });
      break;
    case "server":
      nodes.push("server");
      break;
    case "tool":
      nodes.push("tool");
      edges.push({ id: "server-tool", forward: e.status === "started" });
      break;
  }
  return { nodes, edges };
}

export interface FlowState {
  nodes: Record<NodeId, { visual: Visual; label: string }>;
  edges: Record<EdgeId, { visual: Visual; label: string }>;
  current: McpEvent | null;
}

export function deriveFlow(events: McpEvent[]): FlowState {
  const nodes = Object.fromEntries(
    NODE_DEFS.map((n) => [n.id, { visual: "idle" as Visual, label: "" }]),
  ) as FlowState["nodes"];
  const edges = Object.fromEntries(
    EDGE_DEFS.map((d) => [d.id, { visual: "idle" as Visual, label: "" }]),
  ) as FlowState["edges"];
  const last = events[events.length - 1] ?? null;
  for (const e of events) {
    const t = touches(e);
    const isLast = e === last;
    const visual: Visual = e.status === "failed" ? "error" : isLast ? "active" : "done";
    for (const n of t.nodes) nodes[n] = { visual, label: e.operation };
    for (const ed of t.edges)
      edges[ed.id] = { visual, label: `${ed.forward ? "→" : "←"} ${e.method ?? e.operation}` };
  }
  if (last?.operation === "run_complete") {
    for (const id of Object.keys(nodes) as NodeId[]) if (nodes[id].visual === "active") nodes[id].visual = "done";
    for (const id of Object.keys(edges) as EdgeId[]) if (edges[id].visual === "active") edges[id].visual = "done";
    nodes.result = {
      visual: last.status === "failed" ? "error" : "done",
      label: last.status === "failed" ? "run failed" : "complete",
    };
  }
  return { nodes, edges, current: last };
}
