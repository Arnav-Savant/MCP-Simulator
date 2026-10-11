import { Background, ReactFlow, type Edge, type Node } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useMemo } from "react";
import type { McpEvent } from "../../types";
import { EDGE_DEFS, NODE_DEFS, deriveFlow, type Visual } from "./flowModel";

const COLORS: Record<Visual, string> = { idle: "#2b3441", active: "#2f81f7", done: "#238636", error: "#da3633" };

export function FlowGraph({ events, onSelectComponent }: { events: McpEvent[]; onSelectComponent: (c: string) => void }) {
  const flow = useMemo(() => deriveFlow(events), [events]);
  const nodes: Node[] = NODE_DEFS.map((n) => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: {
      label: (
        <div>
          <b>{n.label}</b>
          <div style={{ fontSize: 11, opacity: 0.85 }}>{flow.nodes[n.id].label || "idle"}</div>
        </div>
      ),
    },
    style: { background: COLORS[flow.nodes[n.id].visual], color: "#fff", border: "1px solid #444", borderRadius: 8, width: 190 },
  }));
  const edges: Edge[] = EDGE_DEFS.map((d) => ({
    id: d.id,
    source: d.source,
    target: d.target,
    label: flow.edges[d.id].label,
    animated: flow.edges[d.id].visual === "active",
    style: { stroke: COLORS[flow.edges[d.id].visual], strokeWidth: 2 },
    labelStyle: { fill: "#d7dde4", fontSize: 11 },
    labelBgStyle: { fill: "#161b22" },
  }));
  return (
    <div>
      <div style={{ height: 380 }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          fitView
          nodesDraggable={false}
          proOptions={{ hideAttribution: true }}
          onNodeClick={(_, n) => onSelectComponent(n.id === "result" ? "host" : n.id)}
        >
          <Background />
        </ReactFlow>
      </div>
      <div className="flow-status">
        {flow.current ? (
          <>
            Current operation: <b>{flow.current.operation}</b> · component: <b>{flow.current.component}</b> · status:{" "}
            <b>{flow.current.status}</b>
            {flow.current.method && (
              <>
                {" "}
                · method: <b>{flow.current.method}</b>
              </>
            )}
            {flow.current.error && (
              <span className="tl-err">
                {" "}
                · {flow.current.error.layer}/{flow.current.error.category} (reached server:{" "}
                {String(flow.current.error.reached_server)})
              </span>
            )}
          </>
        ) : (
          "No events yet."
        )}
      </div>
    </div>
  );
}
