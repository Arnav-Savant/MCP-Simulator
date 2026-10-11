import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from client.lab_client import ClientError
from events.model import Event
from host.policy import Policy
from host.session import Session
from scenarios.definitions import SCENARIOS, get_scenario
from schemas.api import (CallRequest, ComponentInfo, ConnectRequest, PlaybackRequest, RawRequest, RunCreate,
                         RunState)
from schemas.components import COMPONENT_META

session = Session()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await session.reset()
    yield
    await session.close()


app = FastAPI(title="MCP Lab", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])


def _idle() -> None:
    if session.busy:
        raise HTTPException(409, "A scenario is running. Wait for it to finish or reset.")


@app.get("/health")
async def health():
    return {"ok": True}


@app.get("/scenarios")
async def scenarios():
    return [s.model_dump() for s in SCENARIOS]


@app.get("/state", response_model=RunState)
async def state():
    return session.run.state()


@app.get("/events", response_model=list[Event])
async def events():
    return session.run.recorder.events[: session.run.cursor]


@app.get("/stream")
async def stream():
    run = session.run

    async def gen():
        yield {"event": "state", "data": json.dumps(run.state())}
        async for ev in run.released_events():
            yield {"event": "mcp_event", "id": str(ev.seq), "data": ev.model_dump_json()}
            yield {"event": "state", "data": json.dumps(run.state())}

    return EventSourceResponse(gen())


@app.get("/mcp/tools")
async def tools():
    return session.client.tools or []


@app.post("/mcp/connect")
async def connect(body: ConnectRequest):
    _idle()
    try:
        return await session.host.connect(body.mode)
    except ClientError as exc:
        raise HTTPException(502, str(exc))


@app.post("/mcp/discover")
async def discover():
    _idle()
    try:
        return await session.host.discover()
    except ClientError as exc:
        raise HTTPException(409, str(exc))


@app.post("/mcp/tools/{name}/call")
async def call(name: str, body: CallRequest):
    _idle()
    try:
        return await session.host.invoke(name, body.arguments, Policy())
    except ClientError as exc:
        raise HTTPException(409, str(exc))


@app.post("/mcp/raw")
async def raw(body: RawRequest):
    _idle()
    try:
        return await session.host.raw_request(body.method, body.params, body.with_envelope)
    except ClientError as exc:
        raise HTTPException(409, str(exc))


@app.post("/runs", response_model=RunState)
async def create_run(body: RunCreate):
    scenario = get_scenario(body.scenario_id)
    if scenario is None:
        raise HTTPException(404, f"Unknown scenario '{body.scenario_id}'")
    await session.start_scenario(scenario, body.delay_ms, body.paused)
    return session.run.state()


@app.post("/runs/current/{action}", response_model=RunState)
async def control(action: str):
    run = session.run
    if action == "pause":
        run.pause()
    elif action == "resume":
        run.resume()
    elif action == "step":
        run.step()
    else:
        raise HTTPException(404, "action must be pause, resume or step")
    return run.state()


@app.post("/reset", response_model=RunState)
async def reset():
    await session.reset()
    return session.run.state()


@app.post("/playback", response_model=RunState)
async def playback(body: PlaybackRequest):
    session.run.set_delay(body.delay_ms)
    return session.run.state()


@app.get("/components", response_model=list[ComponentInfo])
async def components():
    released = session.run.recorder.events[: session.run.cursor]
    out = []
    for name, meta in COMPONENT_META.items():
        mine = [e for e in released if e.component == name]
        ops: dict[str, int] = {}
        for e in mine:
            ops[e.operation] = ops.get(e.operation, 0) + 1
        last = mine[-1] if mine else None
        out.append(ComponentInfo(
            name=name, title=meta["title"], implementation=meta["implementation"],
            responsibility=meta["responsibility"],
            state="idle" if last is None else f"last: {last.operation} ({last.status})",
            event_count=len(mine), operations=ops, last_event_id=last.id if last else None))
    return out
