import { useEffect, useState } from "react";
import { API } from "../api/client";
import type { McpEvent, RunState } from "../types";

// Events come only from the backend SSE stream (the real, released execution trace).
// Bumping `epoch` re-subscribes (after a run or reset); the stream replays from event 1.
export function useRunStream(epoch: number) {
  const [events, setEvents] = useState<McpEvent[]>([]);
  const [state, setState] = useState<RunState | null>(null);

  useEffect(() => {
    setEvents([]);
    const es = new EventSource(`${API}/stream`);
    es.addEventListener("mcp_event", (e) => {
      const ev: McpEvent = JSON.parse((e as MessageEvent).data);
      setEvents((prev) => (prev.length && prev[prev.length - 1].seq >= ev.seq ? prev : [...prev, ev]));
    });
    es.addEventListener("state", (e) => setState(JSON.parse((e as MessageEvent).data)));
    return () => es.close();
  }, [epoch]);

  return { events, state, setState };
}
