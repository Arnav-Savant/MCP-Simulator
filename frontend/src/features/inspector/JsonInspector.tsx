import { useState } from "react";
import type { McpEvent, Tool } from "../../types";

const Pre = ({ v }: { v: unknown }) => <pre>{v == null ? "—" : JSON.stringify(v, null, 2)}</pre>;

export function JsonInspector({ event, tool }: { event: McpEvent | null; tool: Tool | null }) {
  const [tab, setTab] = useState("request");
  const tabs = ["request", "response", "data", "error", "event", "explain"];
  if (!event && !tool) return <div className="muted">Select an event in the timeline or a tool in the catalog.</div>;
  return (
    <div>
      {tool && (
        <>
          <h4>Tool definition (from tools/list)</h4>
          <Pre v={tool} />
        </>
      )}
      {event && (
        <>
          <h4>
            Event #{event.seq}: {event.operation}
          </h4>
          <div className="tabs">
            {tabs.map((t) => (
              <button key={t} className={t === tab ? "on" : ""} onClick={() => setTab(t)}>
                {t}
              </button>
            ))}
          </div>
          {tab === "request" && (
            <>
              <div className="muted">Raw JSON-RPC request/notification as captured on the wire</div>
              <Pre v={event.request} />
            </>
          )}
          {tab === "response" && (
            <>
              <div className="muted">Raw JSON-RPC response as captured on the wire</div>
              <Pre v={event.response} />
            </>
          )}
          {tab === "data" && (
            <>
              <div className="muted">Non-protocol data (simulated LLM IO, server-side events, summaries)</div>
              <Pre v={event.data} />
            </>
          )}
          {tab === "error" && <Pre v={event.error} />}
          {tab === "event" && <Pre v={event} />}
          {tab === "explain" && (
            <div className="explain">
              <b>UI explanation (not part of the protocol):</b>
              <p>{event.message}</p>
              <p>
                Kind: <code>{event.kind}</code>
                {event.kind === "simulated" && " — simulated inference, not an actual LLM."}
                {event.kind === "legacy" && " — legacy handshake era, shown for comparison."}
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
