import asyncio

from events.recorder import Recorder


class Run:
    """A run's real events plus a playback cursor. Pacing is visual only; events are already recorded."""

    def __init__(self, run_id: str, scenario_id: str | None, delay_ms: int, paused: bool):
        self.run_id, self.scenario_id = run_id, scenario_id
        self.delay_ms, self.paused = delay_ms, paused
        self.cursor = 0
        self.closed = False
        self._tick = asyncio.Event()
        self._waiters: list[asyncio.Future] = []
        self.recorder = Recorder(run_id, scenario_id, on_emit=self._tick.set)
        self._player = asyncio.create_task(self._play())

    def _wake(self) -> None:
        for fut in self._waiters:
            if not fut.done():
                fut.set_result(None)
        self._waiters.clear()

    def _release(self, n: int = 1) -> None:
        self.cursor = min(self.cursor + n, len(self.recorder.events))
        self._wake()

    async def _play(self) -> None:
        while not self.closed:
            if not self.paused and self.cursor < len(self.recorder.events):
                self._release()
                await asyncio.sleep(self.delay_ms / 1000 if self.delay_ms else 0)
            else:
                self._tick.clear()
                if self.closed or (not self.paused and self.cursor < len(self.recorder.events)):
                    continue
                await self._tick.wait()

    def poke(self) -> None:
        self._tick.set()
        self._wake()

    def step(self) -> None:
        self._release(1)
        self._tick.set()

    def pause(self) -> None:
        self.paused = True
        self.poke()

    def resume(self) -> None:
        self.paused = False
        self.poke()

    def set_delay(self, ms: int) -> None:
        self.delay_ms = max(0, ms)
        self.poke()

    def close(self) -> None:
        self.closed = True
        self._tick.set()
        self._wake()

    async def released_events(self, start: int = 0):
        i = start
        while True:
            while i < self.cursor:
                yield self.recorder.events[i]
                i += 1
            if self.closed:
                return
            fut = asyncio.get_running_loop().create_future()
            self._waiters.append(fut)
            await fut

    def state(self) -> dict:
        total = len(self.recorder.events)
        if not self.recorder.finished:
            status = "running" if self.scenario_id else "idle"
        else:
            status = "complete" if self.cursor >= total else "finished"
        return {"run_id": self.run_id, "scenario_id": self.scenario_id, "status": status, "total": total,
                "released": self.cursor, "paused": self.paused, "delay_ms": self.delay_ms}
