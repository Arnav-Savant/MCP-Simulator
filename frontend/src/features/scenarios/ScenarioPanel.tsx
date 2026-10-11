import type { McpEvent, Scenario } from "../../types";

export function ScenarioPanel({ scenarios, selected, onSelect, onRun, events }: {
  scenarios: Scenario[];
  selected: string | null;
  onSelect: (id: string) => void;
  onRun: () => void;
  events: McpEvent[];
}) {
  const chosen = scenarios.find((s) => s.id === selected);
  const final = [...events].reverse().find((e) => e.operation === "final_response");
  return (
    <div className="chat">
      {scenarios.map((s) => (
        <div key={s.id} className={`bubble user ${s.id === selected ? "sel" : ""}`} onClick={() => onSelect(s.id)}>
          <span className="badge">{s.category}</span> {s.user_message}
          <div className="muted">{s.title}</div>
        </div>
      ))}
      {chosen && (
        <div className="detail">
          <p>{chosen.description}</p>
          <p className="muted">
            <b>Expect:</b> {chosen.expected}
          </p>
          <button className="primary" onClick={onRun}>
            ▶ Run scenario
          </button>
        </div>
      )}
      {final && (
        <div className="bubble assistant">
          <span className="badge kind-simulated">SIMULATED</span> {String(final.data?.text ?? "")}
        </div>
      )}
    </div>
  );
}
