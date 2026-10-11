import asyncio
import sys
import time
from pathlib import Path
from typing import Any

from mcp import Client, Implementation, MCPError, StdioServerParameters
from mcp_types.version import MODERN_PROTOCOL_VERSIONS

from events.model import ErrorInfo
from events.recorder import Recorder
from transports.stdio import StderrPump
from transports.tap import TapTransport

BACKEND_DIR = Path(__file__).resolve().parents[1]
CONNECTION_CLOSED = -32000  # observed: MCPError(-32000, "Connection closed") when the server process dies
PROTOCOL_CATEGORIES = {
    -32700: "parse_error",
    -32600: "invalid_request",
    -32601: "method_not_found",
    -32602: "invalid_params",
    -32603: "internal_error",
}


class ClientError(Exception):
    """Raised for transport-level failures (spawn failure, connection closed, not connected)."""


def dump(obj: Any) -> Any:
    return obj.model_dump(by_alias=True, exclude_none=True, mode="json") if hasattr(obj, "model_dump") else obj


def leaf_message(exc: BaseException) -> str:
    """Unwrap ExceptionGroups (the SDK uses anyio task groups) to the underlying cause."""
    inner = getattr(exc, "exceptions", None)
    if inner:
        return "; ".join(leaf_message(e) for e in inner)
    return f"{type(exc).__name__}: {exc}"


def classify_tool_error(text: str, server_events: list[dict]) -> str:
    if any(e["op"] == "handler_start" for e in server_events):
        return "tool_exception"
    if text.startswith("Unknown tool"):
        return "unknown_tool"
    if "validation error" in text or "rejected arguments" in text:
        return "invalid_arguments"
    return "tool_error"  # SDK text heuristics; pinned to mcp==2.3.0


class LabClient:
    def __init__(self, recorder: Recorder, server_script: str | None = None):
        self.rec = recorder
        self.script = server_script or str(BACKEND_DIR / "mcp_server.py")
        self.connected = False
        self.mode: str | None = None
        self.protocol_version: str | None = None
        self.tools: list[dict] | None = None
        self._task: asyncio.Task | None = None
        self._queue: asyncio.Queue = asyncio.Queue()
        self._pump: StderrPump | None = None
        self._wire: list[tuple[str, dict, float]] = []
        self._sent_at: dict[Any, float] = {}
        self._req_method: dict[Any, str] = {}

    # ---- wire capture -------------------------------------------------
    def _on_wire(self, direction: str, session_message) -> None:
        msg = dump(session_message.message)
        now = time.perf_counter()
        if direction == "->" and "id" in msg and "method" in msg:
            self._sent_at[msg["id"]] = now
            self._req_method[msg["id"]] = msg["method"]
        self._wire.append((direction, msg, now))

    def _emit_message(self, direction: str, msg: dict, now: float) -> None:
        method = msg.get("method") or self._req_method.get(msg.get("id"))
        legacy = self.mode == "legacy" and method in ("initialize", "notifications/initialized")
        kind = "legacy" if legacy else "real_mcp"
        arrow = "client → server" if direction == "->" else "server → client"
        if "method" in msg and "id" in msg:
            self.rec.emit("transport", "jsonrpc_request", "started", kind,
                          f"JSON-RPC request {method} (id={msg['id']}) {arrow}",
                          direction="request", method=method, request=msg)
        elif "method" in msg:
            self.rec.emit("transport", "jsonrpc_notification", "completed", kind,
                          f"JSON-RPC notification {method} {arrow}",
                          direction="notification", method=method, request=msg)
        else:
            failed = "error" in msg
            latency = None
            if msg.get("id") in self._sent_at:
                latency = (now - self._sent_at[msg["id"]]) * 1000
            error = None
            if failed:
                code = msg["error"].get("code")
                error = ErrorInfo(layer="protocol", category=PROTOCOL_CATEGORIES.get(code, "protocol_error"),
                                  code=code, message=str(msg["error"].get("message")), reached_server=True)
            self.rec.emit("transport", "jsonrpc_response", "failed" if failed else "completed", kind,
                          f"JSON-RPC {'error' if failed else 'result'} for {method} (id={msg.get('id')}) {arrow}",
                          direction="response", method=method, response=msg, latency_ms=latency, error=error)

    def _emit_server_event(self, ev: dict) -> None:
        op, tool = ev["op"], ev.get("tool")
        table = {
            "received": ("server", "tools/call received", "started"),
            "completed": ("server", "tools/call returned", "completed"),
            "failed": ("server", "tools/call raised", "failed"),
            "handler_start": ("tool", f"{tool} handler start", "started"),
            "handler_end": ("tool", f"{tool} handler end", "completed"),
            "handler_failed": ("tool", f"{tool} handler raised", "failed"),
        }
        component, operation, status = table[op]
        self.rec.emit(component, operation, status, "real_mcp",
                      f"Server-side event '{op}' for tool '{tool}' (reported by the server over its stderr side channel)",
                      direction="internal", method="tools/call", data=ev)

    def _flush(self, server_events: list[dict] | None = None) -> None:
        """Emit buffered wire messages. With server events: requests, server events, then responses."""
        wire, self._wire = self._wire, []
        if server_events is None:
            for d, msg, now in wire:
                self._emit_message(d, msg, now)
            return
        for d, msg, now in wire:
            if d == "->":
                self._emit_message(d, msg, now)
        for ev in server_events:
            self._emit_server_event(ev)
        for d, msg, now in wire:
            if d == "<-":
                self._emit_message(d, msg, now)

    # ---- session task (owns the anyio context so it is entered/exited in one task) ----
    async def _session(self, mode: str, script: str, ready: asyncio.Future) -> None:
        self._pump = StderrPump()
        params = StdioServerParameters(command=sys.executable, args=[script], cwd=str(BACKEND_DIR))
        transport = TapTransport(params, self._pump.write_file, self._on_wire)
        try:
            async with Client(transport, mode=mode,
                              client_info=Implementation(name="mcp-lab-client", version="0.1.0")) as client:
                self.protocol_version = client.protocol_version
                ready.set_result(client)
                while True:
                    item = await self._queue.get()
                    if item is None:
                        return
                    fn, fut = item
                    try:
                        fut.set_result(await fn(client))
                    except Exception as exc:  # noqa: BLE001 - forwarded to the caller
                        fut.set_exception(exc)
        except Exception as exc:  # noqa: BLE001
            if not ready.done():
                ready.set_exception(exc)
        finally:
            self.connected = False
            self._pump.close()

    async def _run(self, fn, op: str, method: str | None):
        problem = None
        if not self.connected or self._task is None or self._task.done():
            problem = ("not_connected", "Not connected: the MCP session is not open (connect first).")
        else:
            fut = asyncio.get_running_loop().create_future()
            await self._queue.put((fn, fut))
            try:
                return await asyncio.wait_for(fut, 20)
            except asyncio.TimeoutError:
                problem = ("timeout", "The server did not respond within 20 seconds.")
        category, text = problem
        self.rec.emit("client", op, "failed", "real_mcp", f"{text} The request was not completed.", method=method,
                      error=ErrorInfo(layer="transport", category=category, message=text, reached_server=False))
        raise ClientError(text)

    def _transport_error(self, operation: str, method: str | None, exc: BaseException, reached: bool) -> ClientError:
        text = leaf_message(exc)
        stderr_tail = " | ".join(self._pump.other_lines[-3:]) if self._pump else ""
        if stderr_tail:
            text += f" (server stderr: {stderr_tail})"
        error = ErrorInfo(layer="transport", category="connection_failed", message=text, reached_server=reached)
        self.rec.emit("transport", operation, "failed", "real_mcp", f"Transport failure: {text}",
                      method=method, error=error)
        self.rec.emit("client", operation, "failed", "real_mcp", "Client could not complete the operation",
                      method=method, error=error)
        return ClientError(text)

    def _protocol_error(self, exc: MCPError) -> ErrorInfo:
        return ErrorInfo(layer="protocol", category=PROTOCOL_CATEGORIES.get(exc.code, "protocol_error"),
                         code=exc.code, message=exc.message, reached_server=True)

    # ---- public operations ---------------------------------------------
    async def connect(self, mode: str = "auto", script: str | None = None) -> dict:
        if self.connected:
            raise ClientError("Already connected.")
        self.mode = mode
        script = script or self.script
        kind = "legacy" if mode == "legacy" else "real_mcp"
        self.rec.emit("client", "connect", "started", kind,
                      f"Opening stdio transport (mode={mode}): spawning the server subprocess and negotiating",
                      data={"mode": mode, "transport": "stdio", "command": [sys.executable, script]})
        ready = asyncio.get_running_loop().create_future()
        self._task = asyncio.create_task(self._session(mode, script, ready))
        try:
            client = await ready
        except BaseException as exc:  # includes ExceptionGroup from the SDK task group
            if self._pump:
                await asyncio.to_thread(self._pump.settle)
            self._flush()
            raise self._transport_error("connect", None, exc, reached=False) from None
        self.connected = True
        self._flush()
        info = {
            "protocol_version": client.protocol_version,
            "server_info": dump(client.server_info),
            "server_capabilities": dump(client.server_capabilities),
        }
        self.rec.emit("client", "connect", "completed", kind,
                      f"Connected; negotiated protocol version {client.protocol_version}", data=info)
        return info

    async def list_tools(self) -> list[dict]:
        self.rec.emit("client", "list_tools", "started", "real_mcp", "Requesting the tool catalog via tools/list",
                      method="tools/list")
        try:
            result = await self._run(lambda c: c.list_tools(), "list_tools", "tools/list")
        except MCPError as exc:
            self._flush()
            if exc.code == CONNECTION_CLOSED:
                raise self._transport_error("list_tools", "tools/list", exc, reached=True) from None
            self.rec.emit("client", "list_tools", "failed", "real_mcp", "tools/list returned a JSON-RPC error",
                          method="tools/list", error=self._protocol_error(exc))
            raise ClientError(exc.message) from None
        self._flush()
        self.tools = [dump(t) for t in result.tools]
        self.rec.emit("client", "list_tools", "completed", "real_mcp", f"Discovered {len(self.tools)} tools",
                      method="tools/list", data={"tool_names": [t["name"] for t in self.tools]})
        return self.tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict:
        self.rec.emit("client", "call_tool", "started", "real_mcp", f"Issuing tools/call for '{name}'",
                      method="tools/call", data={"name": name, "arguments": arguments})
        try:
            result = await self._run(lambda c: c.call_tool(name, arguments), "call_tool", "tools/call")
            protocol_error = None
        except MCPError as exc:
            if exc.code == CONNECTION_CLOSED:
                self._flush()
                raise self._transport_error("call_tool", "tools/call", exc, reached=True) from None
            result, protocol_error = None, exc
        server_events, complete = await asyncio.to_thread(self._pump.drain, 0 if protocol_error else 1)
        self._flush(server_events)
        if not complete and not protocol_error:
            self.rec.emit("client", "server_events_incomplete", "completed", "host_internal",
                          "Server-side events did not all arrive before the timeout; the trace may lack server events")
        if protocol_error:
            self.rec.emit("client", "call_tool", "failed", "real_mcp", "Server answered with a JSON-RPC error",
                          method="tools/call", error=self._protocol_error(protocol_error))
            return {"outcome": "protocol_error", "code": protocol_error.code, "message": protocol_error.message}
        raw = dump(result)
        text = " ".join(c.get("text", "") for c in raw.get("content", []) if c.get("type") == "text")
        is_error = bool(raw.get("isError"))
        category = classify_tool_error(text, server_events) if is_error else None
        error = ErrorInfo(layer="tool", category=category, message=text[:300], reached_server=True) if is_error else None
        self.rec.emit("client", "call_tool", "failed" if is_error else "completed", "real_mcp",
                      "Result delivered to the client" + (f" with isError=true ({category})" if is_error else ""),
                      method="tools/call", data={"result": raw}, error=error)
        return {"outcome": "result", "is_error": is_error, "category": category, "text": text,
                "structured": raw.get("structuredContent"), "result": raw}

    async def send_raw(self, method: str, params: dict | None = None, with_envelope: bool = True) -> dict:
        """Send a deliberately raw JSON-RPC request. Uses the SDK dispatcher (private API: session._dispatcher)."""
        params = dict(params or {})
        if with_envelope and self.protocol_version in MODERN_PROTOCOL_VERSIONS:
            params["_meta"] = {"io.modelcontextprotocol/protocolVersion": self.protocol_version,
                               "io.modelcontextprotocol/clientCapabilities": {}}
        self.rec.emit("client", "raw_request", "started", "real_mcp",
                      f"Sending a raw '{method}' request via the SDK dispatcher "
                      f"(_meta envelope {'included' if with_envelope else 'omitted'})",
                      method=method, data={"params": params})
        try:
            result = await self._run(lambda c: c.session._dispatcher.send_raw_request(method, params), "raw_request", method)
            protocol_error = None
        except MCPError as exc:
            if exc.code == CONNECTION_CLOSED:
                self._flush()
                raise self._transport_error("raw_request", method, exc, reached=True) from None
            result, protocol_error = None, exc
        self._flush([])  # requests first, then responses; no server-side events expected
        if protocol_error:
            self.rec.emit("client", "raw_request", "failed", "real_mcp", "Server answered with a JSON-RPC error",
                          method=method, error=self._protocol_error(protocol_error))
            return {"outcome": "protocol_error", "code": protocol_error.code, "message": protocol_error.message}
        self.rec.emit("client", "raw_request", "completed", "real_mcp", "Server answered with a JSON-RPC result",
                      method=method, data={"result": result})
        return {"outcome": "result", "is_error": False, "category": None, "text": "", "structured": result,
                "result": result}

    async def close(self) -> None:
        if self._task and not self._task.done():
            await self._queue.put(None)
            try:
                await asyncio.wait_for(self._task, timeout=5)
            except (asyncio.TimeoutError, Exception):  # noqa: BLE001
                self._task.cancel()
        self.connected = False
