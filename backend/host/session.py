import asyncio
from contextlib import suppress

from client.lab_client import LabClient
from events.run import Run
from host.host import Host
from simulation.sim_llm import SimulatedLLM


class Session:
    def __init__(self):
        self._counter = 0
        self.run: Run | None = None
        self.client: LabClient | None = None
        self.host: Host | None = None
        self._task: asyncio.Task | None = None

    @property
    def busy(self) -> bool:
        return self._task is not None and not self._task.done()

    async def _teardown(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task
        if self.client:
            await self.client.close()
        if self.run:
            self.run.close()

    async def reset(self, scenario_id: str | None = None, delay_ms: int = 0, paused: bool = False) -> None:
        await self._teardown()
        self._counter += 1
        self.run = Run(f"run-{self._counter}", scenario_id, delay_ms, paused)
        self.client = LabClient(self.run.recorder)
        self.host = Host(self.client, SimulatedLLM(), self.run.recorder)

    async def start_scenario(self, scenario, delay_ms: int, paused: bool) -> None:
        await self.reset(scenario.id, delay_ms, paused)
        self._task = asyncio.create_task(self._execute(scenario))

    async def _execute(self, scenario) -> None:
        run = self.run
        try:
            await self.host.run(scenario)
        finally:
            run.recorder.finished = True
            run.poke()

    async def close(self) -> None:
        await self._teardown()
