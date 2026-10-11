import time
from typing import Any, Literal

from pydantic import BaseModel

Component = Literal["user", "host", "llm", "client", "transport", "server", "tool"]
Status = Literal["started", "completed", "failed", "skipped"]
Kind = Literal["real_mcp", "host_internal", "simulated", "playback", "legacy"]
Direction = Literal["request", "response", "notification", "internal"]


class ErrorInfo(BaseModel):
    layer: Literal["protocol", "tool", "host", "transport"]
    category: str  # e.g. unknown_tool, invalid_arguments, tool_exception, policy_rejection, method_not_found
    code: int | None = None
    message: str
    reached_server: bool


class Event(BaseModel):
    id: str
    run_id: str
    scenario_id: str | None
    seq: int
    component: Component
    operation: str
    status: Status
    kind: Kind
    direction: Direction | None = None
    method: str | None = None
    request: dict[str, Any] | None = None   # raw JSON-RPC request/notification as seen on the wire
    response: dict[str, Any] | None = None  # raw JSON-RPC response as seen on the wire
    data: dict[str, Any] | None = None      # non-protocol payloads: simulated LLM IO, server-side events, summaries
    message: str
    error: ErrorInfo | None = None
    latency_ms: float | None = None         # measured, real events only
    ts: float


def now() -> float:
    return time.time()
