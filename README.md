# MCP Lab: an interactive MCP protocol debugger

A locally runnable app that lets you watch a **real** MCP host, client and server interact, inspect the raw
JSON-RPC, and see failures at the layer where they happen. No LLM key, database or external service needed.

## Pinned versions
- Python SDK: `mcp==2.3.0`
- MCP spec: `2026-07-28` (modern era: `server/discover`, per-request `_meta` envelope).
  The SDK also speaks the handshake era (`2024-11-05` to `2025-11-25`: `initialize` then
  `notifications/initialized`). The UI shows that path only as a labeled **legacy** comparison.

## Setup (nothing is installed for you)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run.py            # FastAPI on http://localhost:8000
```
```bash
cd frontend
npm install
npm run dev              # UI on http://localhost:5173
npm run build            # type-check + production build
```
`run.py` is the launcher (not `server.py`, because `backend/server/` is a package). The MCP server itself is
`backend/mcp_server.py`; the client spawns it as a stdio subprocess. Always run backend commands from `backend/`.

## Architecture
```
React UI  --HTTP/SSE-->  FastAPI (main.py)
                            |
                          Host  --(scripted)-->  SimulatedLLM
                            |
                         LabClient (wraps mcp.Client)
                            |  tap records every JSON-RPC message
                       stdio transport  <--->  mcp_server.py (MCPServer + tools/catalog.py)
```
- `backend/host/` orchestrates a scenario: discovery, supplying tool metadata to the simulated LLM, host policy,
  asking the client to execute, final answer. It never imports `tools/` or `server/`.
- `backend/client/` wraps the SDK `Client`, records wire traffic via `transports/tap.py`, classifies results.
  It keeps no tool registry; tools come from `tools/list`.
- `backend/server/` + `backend/tools/` are the only place tools are defined and executed.
- `backend/simulation/` is the deterministic simulated LLM. Its inputs are the real discovered tool definitions.
- `backend/scenarios/` holds scenario definitions (the frontend only renders what `GET /scenarios` returns).
- `backend/events/` is the single event model, recorder, and playback cursor (`Run`).
- `frontend/src/` renders events: flowchart (`@xyflow/react`), timeline, JSON inspector, component inspector.

## Real vs simulated
| Layer | Status |
|---|---|
| MCP server, tool handlers, stdio transport, JSON-RPC, discovery, validation, errors | **Real** (SDK) |
| Client, host, host policy | **Real** project code |
| LLM | **Simulated**, deterministic; every such event is badged SIMULATED |
| Playback delay | **Visual only**; the latency shown on JSON-RPC responses is measured |

## Execution flow
A scenario run emits, in order: `user_request`, host `receive_request`, per step a `plan_step`; connection
(`server/discover` or legacy `initialize`); `tools/list`; `supply_tools_to_llm`; simulated `llm_input`/`llm_output`
(tool-call proposal); host `policy_check`; `dispatch_to_client`; the client's `tools/call`; transport request;
server `tools/call received`; tool handler start/end; server returned; transport response; client result;
host `receive_result`; simulated interpretation; simulated final response; `run_complete`. The UI shows only what
actually happened in the run. All events are recorded by the backend; the UI is driven by an SSE stream that
releases them according to a backend-held playback cursor (pause, step, resume, delay).

## Failure categories (verified against mcp 2.3.0)
| Case | How it appears |
|---|---|
| Unknown tool | `isError: true` result, text `Unknown tool: ...` (category `unknown_tool`). Not a JSON-RPC error in SDK 2.3.0 |
| Missing/wrong-type/invalid argument | `isError: true` result with validation text (`invalid_arguments`); handler never runs |
| Tool raises | `isError: true`, handler events show the failure (`tool_exception`) |
| Negative application result (`notes_get` id 999) | Normal success with `found: false` |
| Host policy rejection | Never reaches the client or server (`policy_rejection`) |
| Invalid protocol request | Real JSON-RPC error: `-32601` unknown method, `-32602` missing `_meta` envelope |
| Server missing/crashed | Transport failure, `reached_server: false` for spawn failures |

## Scenarios
The list is served by `GET /scenarios` (discovery, success, stateful notes, unknown tool with and without host
catalog enforcement, three validation failures, policy rejection, tool exception, business-negative result, two
protocol errors, transport failure, legacy handshake). Notes state lives in the server subprocess; **Reset**
kills it and the next connect respawns it with the seeded notes.

## Limitations
- Raw invalid requests use the SDK's private `session._dispatcher.send_raw_request`.
- Error categories (`unknown_tool`, `invalid_arguments`) use text heuristics on SDK 2.3.0 messages.
- Server-side events travel over a stderr side channel (JSON lines prefixed `MCPLAB_EVENT `), because the MCP
  logging capability is deprecated as of spec 2026-07-28. They are shown as server-reported, not as protocol messages.
- One active run at a time (single local user); no persistence.
- stdio only; Streamable HTTP, auth, resources and prompts are out of scope. gRPC is not part of MCP and is not drawn.
- By your decision there are no automated tests; verify manually by running the scenarios.

## Docs
`docs/superpowers/specs/` (design) and `docs/superpowers/plans/` (implementation plan).
