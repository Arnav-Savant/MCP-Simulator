import functools
import json
import sys
import threading

from mcp.server.mcpserver import MCPServer

from tools.catalog import register_tools

PREFIX = "MCPLAB_EVENT "
_lock = threading.Lock()
_n = 0


def emit(op: str, **data) -> None:
    """Server-side event side channel: one JSON line on stderr. stdout is reserved for JSON-RPC."""
    global _n
    with _lock:
        _n += 1
        line = PREFIX + json.dumps({"n": _n, "op": op, **data}, default=str)
        print(line, file=sys.stderr, flush=True)


def traced(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        emit("handler_start", tool=fn.__name__, arguments=kwargs)
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            emit("handler_failed", tool=fn.__name__, error_type=type(exc).__name__, detail=str(exc))
            raise
        emit("handler_end", tool=fn.__name__)
        return result

    return wrapper


class TracedMCPServer(MCPServer):
    async def call_tool(self, name, arguments, *args, **kwargs):
        emit("received", tool=name, arguments=arguments)
        try:
            result = await super().call_tool(name, arguments, *args, **kwargs)
        except Exception as exc:
            emit("failed", tool=name, error_type=type(exc).__name__, detail=str(exc)[:300])
            raise
        emit("completed", tool=name)
        return result


def build_server() -> TracedMCPServer:
    server = TracedMCPServer("mcp-lab-server")
    register_tools(server, wrap=traced)
    return server
