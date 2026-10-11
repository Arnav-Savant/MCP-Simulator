from typing import Any

from pydantic import BaseModel


class ConnectRequest(BaseModel):
    mode: str = "auto"  # "auto" = modern server/discover (falls back to initialize); "legacy" = initialize handshake


class CallRequest(BaseModel):
    arguments: dict[str, Any] = {}


class RawRequest(BaseModel):
    method: str
    params: dict[str, Any] = {}
    with_envelope: bool = True


class RunCreate(BaseModel):
    scenario_id: str
    delay_ms: int = 500
    paused: bool = False


class PlaybackRequest(BaseModel):
    delay_ms: int


class RunState(BaseModel):
    run_id: str
    scenario_id: str | None
    status: str
    total: int
    released: int
    paused: bool
    delay_ms: int


class ComponentInfo(BaseModel):
    name: str
    title: str
    implementation: str
    responsibility: str
    state: str
    event_count: int
    operations: dict[str, int]
    last_event_id: str | None
