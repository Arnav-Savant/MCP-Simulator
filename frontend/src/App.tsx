import { useCallback, useEffect, useMemo, useState } from "react";
import { endpoints } from "./api/endpoints";
import { ComponentInspector } from "./features/components/ComponentInspector";
import { ControlsBar } from "./features/controls/ControlsBar";
import { FlowGraph } from "./features/flow/FlowGraph";
import { JsonInspector } from "./features/inspector/JsonInspector";
import { ScenarioPanel } from "./features/scenarios/ScenarioPanel";
import { Timeline } from "./features/timeline/Timeline";
import { ToolCatalog } from "./features/tools/ToolCatalog";
import { useRunStream } from "./hooks/useRunStream";
import type { Scenario, Tool } from "./types";

export default function App() {
  const [epoch, setEpoch] = useState(0);
  const { events, state, setState } = useRunStream(epoch);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenarioId, setScenarioId] = useState<string | null>(null);
  const [tools, setTools] = useState<Tool[]>([]);
  const [selectedEventId, setSelectedEventId] = useState<string | null>(null);
  const [inspectTool, setInspectTool] = useState<Tool | null>(null);
  const [component, setComponent] = useState("host");
  const [delay, setDelay] = useState(500);
  const [stepMode, setStepMode] = useState(false);
  const [error, setError] = useState("");
  const [right, setRight] = useState<"inspector" | "components">("inspector");

  useEffect(() => {
    endpoints.scenarios().then(setScenarios).catch((e) => setError(String(e)));
  }, []);

  // Refetch the real discovered catalog whenever a (released) discovery completes.
  const discoveries = events.filter((e) => e.operation === "list_tools" && e.status === "completed").length;
  useEffect(() => {
    endpoints.tools().then(setTools).catch(() => setTools([]));
  }, [discoveries, epoch]);

  const act = useCallback(async (fn: () => Promise<unknown>) => {
    try {
      setError("");
      await fn();
    } catch (e) {
      setError(String(e));
    }
  }, []);

  const resubscribe = () => {
    setSelectedEventId(null);
    setInspectTool(null);
    setTools([]);
    setEpoch((n) => n + 1);
  };
  const selected = useMemo(() => events.find((e) => e.id === selectedEventId) ?? null, [events, selectedEventId]);
  const flowEvents = useMemo(() => {
    if (!selected) return events;
    return events.slice(0, events.findIndex((e) => e.id === selected.id) + 1);
  }, [events, selected]);
  const busy = state?.status === "running";

  return (
    <div className="app">
      <header>
        <b>MCP Lab</b>{" "}
        <span className="muted">
          real MCP (mcp 2.3.0, spec 2026-07-28) · simulated LLM · playback delay is visual only
        </span>
      </header>
      <ControlsBar
        state={state}
        busy={busy}
        delay={delay}
        stepMode={stepMode}
        onStepMode={setStepMode}
        onConnect={(m) => act(() => endpoints.connect(m))}
        onDiscover={() => act(endpoints.discover)}
        onPause={() => act(async () => setState(await endpoints.control("pause")))}
        onResume={() => act(async () => setState(await endpoints.control("resume")))}
        onStep={() => act(async () => setState(await endpoints.control("step")))}
        onDelay={(ms) => {
          setDelay(ms);
          act(() => endpoints.playback(ms));
        }}
        onReset={() =>
          act(async () => {
            await endpoints.reset();
            resubscribe();
          })
        }
      />
      {error && <div className="error">{error}</div>}
      <main>
        <aside>
          <h3>Scenarios</h3>
          <ScenarioPanel
            scenarios={scenarios}
            selected={scenarioId}
            onSelect={setScenarioId}
            events={events}
            onRun={() =>
              scenarioId &&
              act(async () => {
                await endpoints.runScenario(scenarioId, delay, stepMode);
                resubscribe();
              })
            }
          />
          <h3>
            Tool catalog <span className="muted">(from tools/list)</span>
          </h3>
          <ToolCatalog
            tools={tools}
            onInspect={(t) => {
              setInspectTool(t);
              setRight("inspector");
            }}
            onInvoke={(n, a) => act(() => endpoints.callTool(n, a))}
          />
        </aside>
        <section>
          <FlowGraph
            events={flowEvents}
            onSelectComponent={(c) => {
              setComponent(c);
              setRight("components");
            }}
          />
          <h3>Execution timeline</h3>
          <Timeline
            events={events}
            selectedId={selectedEventId}
            onSelect={(id) => {
              setSelectedEventId(id);
              setRight("inspector");
            }}
          />
        </section>
        <aside>
          <div className="tabs">
            <button className={right === "inspector" ? "on" : ""} onClick={() => setRight("inspector")}>
              JSON inspector
            </button>
            <button className={right === "components" ? "on" : ""} onClick={() => setRight("components")}>
              Components
            </button>
          </div>
          {right === "inspector" ? (
            <JsonInspector event={selected} tool={inspectTool} />
          ) : (
            <ComponentInspector events={events} selected={component} onSelect={setComponent} />
          )}
        </aside>
      </main>
    </div>
  );
}
