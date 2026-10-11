import { useState } from "react";
import type { Tool } from "../../types";

function skeleton(schema?: Record<string, any>): string {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries<any>(schema?.properties ?? {})) {
    out[k] = v.enum ? v.enum[0] : v.type === "integer" || v.type === "number" ? 0 : v.type === "boolean" ? false : "";
  }
  return JSON.stringify(out, null, 2);
}

export function ToolCatalog({ tools, onInspect, onInvoke }: {
  tools: Tool[];
  onInspect: (t: Tool) => void;
  onInvoke: (name: string, args: unknown) => void;
}) {
  const [name, setName] = useState<string>("");
  const [text, setText] = useState("{}");
  const [err, setErr] = useState("");
  const pick = (t: Tool) => {
    setName(t.name);
    setText(skeleton(t.inputSchema));
    onInspect(t);
  };
  if (!tools.length) return <div className="muted">No tools discovered yet. Press “Discover tools”.</div>;
  return (
    <div>
      {tools.map((t) => (
        <div key={t.name} className={`tool ${t.name === name ? "sel" : ""}`} onClick={() => pick(t)}>
          <b>{t.name}</b>
          <div className="muted">{t.description}</div>
        </div>
      ))}
      <textarea value={text} onChange={(e) => setText(e.target.value)} rows={6} />
      <div className="muted">Arguments are sent as typed, even if invalid, so you can provoke server-side validation.</div>
      {err && <div className="tl-err">{err}</div>}
      <button
        disabled={!name}
        onClick={() => {
          try {
            setErr("");
            onInvoke(name, JSON.parse(text));
          } catch (e) {
            setErr(String(e));
          }
        }}
      >
        Invoke {name}
      </button>
    </div>
  );
}
