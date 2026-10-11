import type { McpEvent } from "../../types";

const KIND_LABEL: Record<string, string> = {
  real_mcp: "REAL MCP",
  host_internal: "HOST",
  simulated: "SIMULATED",
  playback: "PLAYBACK",
  legacy: "LEGACY",
};

export function Timeline({ events, selectedId, onSelect }: { events: McpEvent[]; selectedId: string | null; onSelect: (id: string) => void }) {
  return (
    <div className="timeline">
      {events.map((e) => (
        <div key={e.id} className={`tl-row ${e.id === selectedId ? "sel" : ""} st-${e.status}`} onClick={() => onSelect(e.id)}>
          <span className="tl-seq">{e.seq}</span>
          <span className={`badge comp-${e.component}`}>{e.component}</span>
          <span className={`badge kind-${e.kind}`}>{KIND_LABEL[e.kind]}</span>
          <span className="tl-op">{e.operation}</span>
          <span className="tl-status">{e.status}</span>
          {e.latency_ms != null && (
            <span className="tl-lat" title="Measured round-trip latency">
              {e.latency_ms.toFixed(1)} ms
            </span>
          )}
          <div className="tl-msg">{e.message}</div>
          {e.error && (
            <div className="tl-err">
              [{e.error.layer}/{e.error.category}] reached server: {String(e.error.reached_server)}
            </div>
          )}
        </div>
      ))}
      {events.length === 0 && <div className="muted" style={{ padding: 8 }}>No events yet. Run a scenario or use the controls.</div>}
    </div>
  );
}
