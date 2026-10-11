# MCP Lab: Design Spec

Date: 2026-10-11. Status: approved in conversation, pending written-spec review.

## 1. Purpose
A locally runnable interactive MCP protocol debugger for learning MCP and interview prep. A developer
watches a real MCP host, client and server interact, inspects raw JSON-RPC, and sees failures at the
layer where they occur. No LLM key, database or external service is needed.

## 2. Pinned versions and protocol eras
- Python SDK `mcp==2.3.0` (verified: `mcp-types==2.3.0`, `pydantic 2.14`, `starlette 1.7`).
- Spec `2026-07-28` is the **modern** era (`server/discover`, no `initialize`). The SDK also supports the
  **legacy handshake** era (`2024-11-05`, `2025-03-26`, `2025-06-18`, `2025-11-25`: `initialize`, then
  `notifications/initialized`).
- `mcp.Client(mode=...)`: `"auto"` probes `server/discover` and falls back to `initialize`; `"legacy"` forces
  the handshake; a modern version string forces that version.
- **Connection model (option A):** Connect defaults to modern. A "Legacy handshake" option forces
  `mode="legacy"`, and every legacy event is labeled `legacy` in the UI.
- Spec text is not available offline; spec-sensitive behaviour (see section 9) is verified against the
  installed SDK source and by manual runs, then documented in the README.

## 3. Real vs simulated
| Layer | Real or simulated |
|---|---|
| Server, tool handlers, stdio transport, JSON-RPC, discovery, validation, errors | **Real** (SDK) |
| Client, host orchestration, host policy | **Real** code (project-owned) |
| LLM | **Simulated** (deterministic; every output tagged `simulated`) |
| Playback delay, animations | **Playback** only; measured latency is separate |

Every event carries `kind`: `real_mcp | host_internal | simulated | playback | legacy`.

## 4. Layout (no `app/` directory; work directly in `backend/`)
```
backend/
  run.py            launcher: `python run.py` starts uvicorn on main:app (not named server.py,
                    because `server/` is a package)
  main.py           FastAPI app and routes
  mcp_server.py     entry point the client spawns over stdio (python mcp_server.py)
  host/             orchestration loop, policy
  client/           wrapper around mcp.Client, JSON-RPC tap
  server/           MCPServer construction, tool registration, server-side event emission
  tools/            tool handlers and fixtures (the ONLY tool definitions)
  schemas/          pydantic API models
  transports/       stdio parameters, tap/recording, failure injection
  simulation/       deterministic simulated LLM
  scenarios/        scenario definitions as data
  events/           event model, per-run recorder, SSE broadcaster
  requirements.txt
frontend/src/{components,features,api,types,hooks}
docs/
```
Run everything from inside `backend/` with a venv the user creates. No `__init__.py` files anywhere
(Python namespace packages); no tests.

## 5. Backend components
- **Server** (`server/`, `tools/`): `MCPServer` with deterministic tools. Initial set: `calculator` (add,
  subtract, multiply, divide with output schema), `text_stats`, `notes_add` / `notes_list` / `notes_get`
  (seeded in-memory store with reset), `always_fails` (raises). Server runs as a stdio subprocess and
  writes server-side events (received, validated, dispatched, handler start and end) to a side channel
  (JSON lines on stderr, tagged), read by the host process. The reset operation restarts the subprocess
  or calls a dedicated reset tool excluded from the scenario tool catalog (decided in the plan).
- **Client** (`client/`): owns the `mcp.Client` session. Methods: `connect(mode)`, `list_tools()`,
  `describe_tool(name)`, `call_tool(name, args)`, `close()`. Raw JSON-RPC requests and responses are
  captured with a transport tap, not reconstructed. No tool registry of its own.
- **Host** (`host/`): runs a scenario step by step: discover via client, give tool metadata to the
  simulated LLM, receive a proposal, apply policy (deny list, argument limits), call through the client,
  feed the result back, produce the final response. It never imports `tools/` or `server/`.
- **Simulation** (`simulation/`): pure function of (scenario step, discovered tools, prior results) ->
  proposal or final text. Reads live `tools/list` output; fails visibly if a scripted tool is absent.
- **Scenarios** (`scenarios/`): declarative step lists (user message, expected path, sim proposals,
  policy settings, fault injection). Served by the API; the frontend never defines them.
- **Events** (`events/`): one model and one recorder. Fields: `id`, `run_id`, `scenario_id`, `seq`,
  `component`, `operation`, `status`, `kind`, `method`, `request`, `response`, `message`, `error`
  (`layer`, `code`, `detail`), `latency_ms` (measured, real events only), `ts`. Raw MCP messages live only
  in `request` / `response`; explanatory text lives in `message`.

## 6. API (FastAPI, typed models; OpenAPI drives frontend types)
`GET /scenarios`, `POST /mcp/connect` (mode), `POST /mcp/discover`, `GET /mcp/tools`,
`POST /mcp/tools/{name}/call`, `POST /runs` (scenario id), `POST /runs/{id}/step|pause|resume|reset`,
`GET /runs/{id}`, `GET /runs/{id}/events`, `GET /runs/{id}/stream` (SSE), `GET /components/{name}`.
Exact shapes are finalized in the plan. Execution runs on the backend; playback pacing is applied only
to the SSE stream; step mode releases one buffered event per request. Every endpoint that touches
protocol state goes through the host and client.

## 7. Failure taxonomy (each shown at its own layer)
| Case | Layer | Representation |
|---|---|---|
| Unknown tool | tool layer (SDK 2.3.0 `MCPServer`) | `isError: true` result whose text starts `Unknown tool:`; not a JSON-RPC error |
| Missing or wrong-type argument, invalid value | tool layer | `isError: true` result with pydantic validation text (verified); not a JSON-RPC error |
| Tool raises | tool execution | result with `isError: true` |
| Negative business result (for example division result flagged, note not found) | application | normal success result |
| Host policy rejection | host | never reaches server; event shows request not sent |
| Invalid protocol request | protocol | raw request via the SDK dispatcher: unknown method gives `-32601`; missing `_meta` envelope or bad params gives `-32602` |
| Server crash or spawn failure | transport | connection error; request reached server: no |
Each failure event states where it originated, whether the request reached the server, and what the host
received.

## 8. Frontend (React, TypeScript, Vite, `@xyflow/react`)
Panels: scenario chat, controls bar (Connect, Discover, tool catalog, Invoke tool, Run, Step,
Pause/Resume, Reset), flowchart (host, simulated LLM, client, transport, server, tool handler, result
path; node and edge state derived from events only), timeline (select an event), JSON inspector (raw
payloads, separate "explanation" tab), component inspector (responsibility, state, operations, events,
real-vs-simulated). Types come from `openapi-typescript`; no tool or scenario data is defined in the
frontend. Simulated events display a "Simulated inference" badge.

## 9. Open items to verify during implementation
1. How SDK 2.3.0 reports input-schema validation failures (protocol error vs `isError`).
2. Cleanest way to tap raw JSON-RPC from `mcp.Client` over stdio (transport wrapper or stream hook).
3. How `MCPServer` exposes output schemas and structured content in 2.3.0.
4. Server-side event side channel over stdio without corrupting the JSON-RPC stream (stderr).
5. How to send a deliberately invalid protocol request through the SDK transport.

## 10. Testing
None. By explicit user decision there are no automated tests, test directories, test dependencies or
test tooling. Verification is manual: start the backend and frontend and exercise scenarios in the UI.

## 11. Build order
Vertical slice (one tool, real client-server call, host, one endpoint, one UI button with the real
trace), then discovery, remaining tools, scenarios, errors, inspector, playback, component inspector,
manual verification, README.

## 12. Non-goals
Streamable HTTP transport, auth, resources and prompts, real LLM, persistence beyond the in-memory run
store. gRPC is not part of MCP and is not drawn.

## 13. Amendments after SDK verification (2026-10-11, supersede earlier text)
Verified against `mcp==2.3.0` in a scratch environment:
1. Schema-validation failures and unknown tools are `isError: true` results, not JSON-RPC errors (section 7 updated).
   Genuine JSON-RPC errors are demonstrated with raw requests through `session._dispatcher.send_raw_request`
   (a private SDK API; documented as a limitation).
2. Modern-era requests must carry `params._meta` with `io.modelcontextprotocol/protocolVersion` and
   `io.modelcontextprotocol/clientCapabilities`; omitting it yields `-32602`.
3. Raw JSON-RPC is captured by a `Transport` wrapper around `stdio_client` (the `Client` accepts any `Transport`).
4. Server-side events use stderr JSON lines prefixed `MCPLAB_EVENT ` (the MCP logging capability is deprecated as
   of 2026-07-28). A `MCPServer` subclass overrides `call_tool` for received/completed/failed events and handler
   wrappers emit handler_start/handler_end/handler_failed. The host buffers wire and server events per call and
   emits them in causal order: requests, server events, responses.
5. Reset = close the client (kills the server subprocess) and create a new run; the next connect respawns the
   server with a fresh seeded notes store.
6. Single active run (local single-user tool): API uses `/runs` (create) and `/runs/current/...` instead of
   `/runs/{id}/...`. Playback (pause/step/resume/delay) is a backend-held cursor over buffered real events.
7. Frontend types are hand-written mirrors of `events/model.py` (no OpenAPI generation step).
8. Manual controls (connect, discover, invoke, raw request) are Host methods, so they pass through host policy and
   the client exactly like scenario steps.
9. The MCP server file is `backend/mcp_server.py`; the launcher is `backend/run.py`.
