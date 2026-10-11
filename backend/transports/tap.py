from typing import Callable

from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.message import SessionMessage

OnMessage = Callable[[str, SessionMessage], None]


class _TapRead:
    def __init__(self, inner, on_message: OnMessage):
        self._inner, self._cb = inner, on_message

    def _seen(self, item):
        if isinstance(item, SessionMessage):
            self._cb("<-", item)
        return item

    async def receive(self):
        return self._seen(await self._inner.receive())

    async def aclose(self):
        await self._inner.aclose()

    def __aiter__(self):
        return self

    async def __anext__(self):
        return self._seen(await self._inner.__anext__())

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._inner.aclose()


class _TapWrite:
    def __init__(self, inner, on_message: OnMessage):
        self._inner, self._cb = inner, on_message

    async def send(self, item, /):
        self._cb("->", item)
        await self._inner.send(item)

    async def aclose(self):
        await self._inner.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self._inner.aclose()


class TapTransport:
    """Wraps the SDK stdio transport and reports every JSON-RPC message in both directions."""

    def __init__(self, params: StdioServerParameters, errlog, on_message: OnMessage):
        self._cm = stdio_client(params, errlog=errlog)
        self._on_message = on_message

    async def __aenter__(self):
        read, write = await self._cm.__aenter__()
        return _TapRead(read, self._on_message), _TapWrite(write, self._on_message)

    async def __aexit__(self, *exc):
        return await self._cm.__aexit__(*exc)
