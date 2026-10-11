import { useState } from "react";
import type { RunState } from "../../types";

export function ControlsBar(p: {
  state: RunState | null;
  busy: boolean;
  onConnect: (mode: string) => void;
  onDiscover: () => void;
  onPause: () => void;
  onResume: () => void;
  onStep: () => void;
  onReset: () => void;
  delay: number;
  onDelay: (ms: number) => void;
  stepMode: boolean;
  onStepMode: (v: boolean) => void;
}) {
  const [mode, setMode] = useState("auto");
  return (
    <div className="controls">
      <select value={mode} onChange={(e) => setMode(e.target.value)}>
        <option value="auto">Modern 2026-07-28 (server/discover)</option>
        <option value="legacy">Legacy handshake (initialize)</option>
      </select>
      <button disabled={p.busy} onClick={() => p.onConnect(mode)}>
        Connect
      </button>
      <button disabled={p.busy} onClick={p.onDiscover}>
        Discover tools
      </button>
      <span className="sep" />
      <button onClick={p.onPause} disabled={p.state?.paused}>
        Pause
      </button>
      <button onClick={p.onResume} disabled={!p.state?.paused}>
        Resume
      </button>
      <button onClick={p.onStep}>Step</button>
      <label>
        <input type="checkbox" checked={p.stepMode} onChange={(e) => p.onStepMode(e.target.checked)} /> start paused
      </label>
      <label title="Visual playback delay only; not a measured latency">
        playback delay{" "}
        <select value={p.delay} onChange={(e) => p.onDelay(Number(e.target.value))}>
          {[0, 250, 500, 1000, 2000].map((v) => (
            <option key={v} value={v}>
              {v} ms
            </option>
          ))}
        </select>
      </label>
      <button onClick={p.onReset}>Reset</button>
      <span className="muted">
        {p.state
          ? `${p.state.status} · ${p.state.released}/${p.state.total} events released${p.state.paused ? " · paused" : ""}`
          : ""}
      </span>
    </div>
  );
}
