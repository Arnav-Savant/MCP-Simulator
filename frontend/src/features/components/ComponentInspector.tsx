import { useEffect, useState } from "react";
import { endpoints } from "../../api/endpoints";
import type { ComponentInfo, McpEvent } from "../../types";

export function ComponentInspector({ events, selected, onSelect }: { events: McpEvent[]; selected: string; onSelect: (c: string) => void }) {
  const [infos, setInfos] = useState<ComponentInfo[]>([]);
  useEffect(() => {
    endpoints.components().then(setInfos).catch(() => setInfos([]));
  }, [events.length]);
  const info = infos.find((i) => i.name === selected);
  const mine = events.filter((e) => e.component === selected);
  const lastWire = [...mine].reverse().find((e) => e.request || e.response);
  return (
    <div>
      <div className="tabs">
        {infos.map((i) => (
          <button key={i.name} className={i.name === selected ? "on" : ""} onClick={() => onSelect(i.name)}>
            {i.name}
          </button>
        ))}
      </div>
      {info && (
        <>
          <h4>
            {info.title} <span className={`badge impl-${info.implementation}`}>{info.implementation.toUpperCase()}</span>
          </h4>
          <p>{info.responsibility}</p>
          <p>
            <b>State:</b> {info.state} · <b>events:</b> {info.event_count}
          </p>
          <b>Operations performed</b>
          <ul>
            {Object.entries(info.operations).map(([op, n]) => (
              <li key={op}>
                {op} × {n}
              </li>
            ))}
          </ul>
          {lastWire && (
            <>
              <b>Latest protocol data</b>
              <pre>{JSON.stringify(lastWire.request ?? lastWire.response, null, 2)}</pre>
            </>
          )}
        </>
      )}
    </div>
  );
}
